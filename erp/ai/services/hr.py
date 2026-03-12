"""
HR Analytics Service

1. Employee Attrition Risk Prediction
2. Attendance Anomaly Detection
"""

import logging
from datetime import timedelta

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import roc_auc_score
from sklearn.preprocessing import StandardScaler
from django.conf import settings
from django.db.models import Count, Avg, Q
from django.utils import timezone

from erp.models import Employee, LeaveRequest, Attendance, Payroll
from erp.ai.models import MLModel, AIInsight
from .base import (
    get_or_create_registry, save_model_artefact, load_model_artefact,
    log_prediction, create_or_update_insight,
)

logger = logging.getLogger('erp.ai.hr')


class AttritionPredictor:
    """Predict which employees are most likely to leave."""

    FEATURE_COLS = [
        'tenure_days', 'salary', 'leave_frequency',
        'employment_type_code', 'department_turnover_rate',
        'has_reports_to', 'leave_balance_ratio',
        'avg_overtime_hours', 'salary_vs_dept_avg',
        'attendance_rate', 'payroll_months',
        'avg_gross_pay', 'comp_vs_dept_avg', 'absence_rate',
    ]

    def __init__(self, company):
        self.company = company
        self.min_samples = getattr(settings, 'ML_MIN_TRAINING_SAMPLES', 30)
        self._model = None
        self._scaler = None
        self._registry = None

    # ── Dataset ─────────────────────────────────────────────────────────

    def _build_dataset(self) -> pd.DataFrame:
        """Build labelled dataset from active + terminated employees."""
        employees = Employee.objects.filter(
            company=self.company,
            employment_status__in=['active', 'terminated', 'resigned'],
        ).values(
            'id', 'employment_status', 'hire_date', 'termination_date',
            'basic_salary', 'employment_type', 'department_id',
            'reports_to_id', 'annual_leave_balance', 'sick_leave_balance',
        )
        df = pd.DataFrame(list(employees))
        if df.empty or len(df) < self.min_samples:
            return pd.DataFrame()

        # Label: 1 = left (terminated / resigned), 0 = still active
        df['left'] = df['employment_status'].isin(
            ['terminated', 'resigned']).astype(int)

        now = timezone.now().date()
        df['tenure_days'] = df.apply(
            lambda r: (
                (r['termination_date'] or now) - r['hire_date']
            ).days if r['hire_date'] else 0, axis=1)

        df['salary'] = df['basic_salary'].astype(float)

        # Leave frequency (requests in last year)
        one_year_ago = timezone.now() - timedelta(days=365)
        leave_counts = dict(
            LeaveRequest.objects.filter(
                employee__company=self.company,
                created_at__gte=one_year_ago,
            ).values('employee_id').annotate(cnt=Count('id')).values_list(
                'employee_id', 'cnt')
        )
        df['leave_frequency'] = df['id'].map(leave_counts).fillna(0).astype(int)

        # Employment type code
        emp_types = {'full_time': 0, 'part_time': 1, 'contract': 2,
                     'intern': 3, 'freelance': 4}
        df['employment_type_code'] = df['employment_type'].map(
            emp_types).fillna(0).astype(int)

        # Department turnover rate
        dept_stats = (
            df.groupby('department_id')
            .agg(dept_total=('id', 'count'), dept_left=('left', 'sum'))
            .reset_index()
        )
        dept_stats['department_turnover_rate'] = (
            dept_stats['dept_left'] / dept_stats['dept_total'].clip(lower=1)
        )
        df = df.merge(
            dept_stats[['department_id', 'department_turnover_rate']],
            on='department_id', how='left',
        )
        df['department_turnover_rate'] = df['department_turnover_rate'].fillna(0)

        df['has_reports_to'] = df['reports_to_id'].notna().astype(int)
        df['leave_balance_ratio'] = (
            (df['annual_leave_balance'].fillna(0).astype(float)
             + df['sick_leave_balance'].fillna(0).astype(float)) / 60
        ).clip(0, 1)

        # ── Additional features from Attendance & Payroll ───────────────
        # Average overtime hours from attendance records
        overtime_data = dict(
            Attendance.objects.filter(
                employee__company=self.company,
            ).values('employee_id').annotate(
                avg_ot=Avg('overtime_hours'),
            ).values_list('employee_id', 'avg_ot')
        )
        df['avg_overtime_hours'] = (
            df['id'].map(overtime_data).astype(float)
        )
        # Fill missing with draws from observed distribution (avoids
        # zero-variance leakage that arises when all missing rows get
        # the same constant).
        ot_known = df['avg_overtime_hours'].dropna()
        ot_missing = df['avg_overtime_hours'].isna()
        if len(ot_known) > 0 and ot_missing.any():
            ot_mu, ot_sig = ot_known.mean(), max(ot_known.std(), 0.01)
            df.loc[ot_missing, 'avg_overtime_hours'] = np.random.normal(
                ot_mu, ot_sig, size=ot_missing.sum(),
            ).clip(min=0)
        else:
            df['avg_overtime_hours'] = df['avg_overtime_hours'].fillna(0)

        # Salary relative to department average
        dept_salary = (
            df.groupby('department_id')['salary']
            .transform('mean')
        ).clip(lower=1)
        df['salary_vs_dept_avg'] = df['salary'] / dept_salary

        # Attendance rate (present days / total work days)
        att_stats = (
            Attendance.objects.filter(
                employee__company=self.company,
            ).values('employee_id').annotate(
                total_days=Count('id'),
                present_days=Count('id', filter=Q(is_present=True)),
            )
        )
        att_dict = {
            r['employee_id']: (
                r['present_days'] / max(r['total_days'], 1)
            ) for r in att_stats
        }
        df['attendance_rate'] = df['id'].map(att_dict).astype(float)
        # Fill missing with draws from observed distribution
        att_known = df['attendance_rate'].dropna()
        att_missing = df['attendance_rate'].isna()
        if len(att_known) > 0 and att_missing.any():
            att_mu, att_sig = att_known.mean(), max(att_known.std(), 0.01)
            df['attendance_rate'] = df['attendance_rate'].copy()
            df.loc[att_missing, 'attendance_rate'] = np.random.normal(
                att_mu, att_sig, size=att_missing.sum(),
            ).clip(0, 1)
        else:
            df['attendance_rate'] = df['attendance_rate'].fillna(0.9)

        # ── New features for richer signal ───────────────────────────
        # Payroll months (proxy for data richness / tenure confirmation)
        payroll_counts = dict(
            Payroll.objects.filter(
                employee__company=self.company,
            ).values('employee_id').annotate(cnt=Count('id')).values_list(
                'employee_id', 'cnt')
        )
        df['payroll_months'] = df['id'].map(payroll_counts).fillna(0).astype(int)

        # Average gross pay from payroll records
        payroll_avg = dict(
            Payroll.objects.filter(
                employee__company=self.company,
            ).values('employee_id').annotate(
                avg_gross=Avg('gross_salary'),
            ).values_list('employee_id', 'avg_gross')
        )
        df['avg_gross_pay'] = df['id'].map(payroll_avg).fillna(df['salary']).astype(float)

        # Total compensation vs department average
        dept_comp = (
            df.groupby('department_id')['avg_gross_pay']
            .transform('mean')
        ).clip(lower=1)
        df['comp_vs_dept_avg'] = df['avg_gross_pay'] / dept_comp

        # Absence rate (complement of attendance_rate, scaled)
        df['absence_rate'] = (1 - df['attendance_rate']).clip(0, 1)

        return df

    # ── Training ────────────────────────────────────────────────────────

    def train(self) -> dict:
        df = self._build_dataset()
        if df.empty:
            return {'status': 'skipped', 'reason': 'insufficient_data'}

        X = df[self.FEATURE_COLS].fillna(0).values
        y = df['left'].values

        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)

        X_train, X_test, y_train, y_test = train_test_split(
            X_scaled, y, test_size=0.2, random_state=42,
            stratify=y if len(set(y)) > 1 else None,
        )

        clf = RandomForestClassifier(
            n_estimators=500, max_depth=10, min_samples_leaf=5,
            class_weight='balanced', random_state=42,
            max_features='sqrt',
        )
        clf.fit(X_train, y_train)

        auc = 0.0
        if len(set(y_test)) > 1:
            auc = roc_auc_score(y_test, clf.predict_proba(X_test)[:, 1])

        registry = get_or_create_registry(
            self.company, MLModel.ModelType.ATTRITION,
            'Employee Attrition Predictor',
        )
        registry.training_samples = len(df)
        registry.accuracy_score = auc
        save_model_artefact(registry, {
            'classifier': clf, 'scaler': scaler,
            'feature_cols': self.FEATURE_COLS,
        })

        self._model = clf
        self._scaler = scaler
        self._registry = registry

        logger.info('Attrition model trained: AUC=%.4f samples=%d', auc, len(df))
        return {'status': 'trained', 'auc': round(auc, 4), 'samples': len(df)}

    # ── Prediction ──────────────────────────────────────────────────────

    def _load(self):
        if self._model is not None:
            return
        self._registry = get_or_create_registry(
            self.company, MLModel.ModelType.ATTRITION,
            'Employee Attrition Predictor',
        )
        if not self._registry.artefact_path:
            self.train()
            return
        artefact = load_model_artefact(self._registry)
        self._model = artefact['classifier']
        self._scaler = artefact['scaler']

    def _build_single_feature_vector(self, employee: Employee) -> np.ndarray | None:
        """Build the feature vector for a single employee.

        Returns a (1, n_features) numpy array matching FEATURE_COLS order,
        or None if features cannot be built.
        Used by both predict() and the XAI explainability service.
        """
        now = timezone.now().date()
        tenure = (now - employee.hire_date).days if employee.hire_date else 0
        leave_freq = LeaveRequest.objects.filter(
            employee=employee,
            created_at__gte=timezone.now() - timedelta(days=365),
        ).count()

        dept_employees = Employee.objects.filter(
            company=self.company, department=employee.department,
        )
        dept_total = dept_employees.count() or 1
        dept_left = dept_employees.filter(
            employment_status__in=['terminated', 'resigned'],
        ).count()
        dept_turnover = dept_left / dept_total

        emp_types = {'full_time': 0, 'part_time': 1, 'contract': 2,
                     'intern': 3, 'freelance': 4}

        avg_ot_val = Attendance.objects.filter(
            employee=employee,
        ).aggregate(avg_ot=Avg('overtime_hours'))['avg_ot']
        if avg_ot_val is None:
            avg_ot_val = Attendance.objects.filter(
                employee__company=self.company,
            ).aggregate(avg_ot=Avg('overtime_hours'))['avg_ot'] or 0
        avg_ot = float(avg_ot_val)

        dept_avg_salary = dept_employees.aggregate(
            avg_sal=Avg('basic_salary'))['avg_sal'] or 1
        salary_vs_dept = float(employee.basic_salary) / max(float(dept_avg_salary), 1)

        att_data = Attendance.objects.filter(
            employee=employee,
        ).aggregate(
            total=Count('id'),
            present=Count('id', filter=Q(is_present=True)),
        )
        if att_data['total']:
            att_rate = att_data['present'] / max(att_data['total'], 1)
        else:
            co_att = Attendance.objects.filter(
                employee__company=self.company,
            ).aggregate(
                total=Count('id'),
                present=Count('id', filter=Q(is_present=True)),
            )
            att_rate = (
                co_att['present'] / max(co_att['total'], 1)
                if co_att['total'] else 0.9
            )

        payroll_agg = Payroll.objects.filter(
            employee=employee,
        ).aggregate(cnt=Count('id'), avg_gross=Avg('gross_salary'))
        payroll_months = payroll_agg['cnt'] or 0
        avg_gross_pay = float(payroll_agg['avg_gross'] or employee.basic_salary)

        dept_avg_comp = Payroll.objects.filter(
            employee__company=self.company,
            employee__department=employee.department,
        ).aggregate(avg_g=Avg('gross_salary'))['avg_g']
        comp_vs_dept = avg_gross_pay / max(float(dept_avg_comp or avg_gross_pay), 1)

        absence_rate = max(0.0, min(1.0, 1 - att_rate))

        return np.array([[
            tenure,
            float(employee.basic_salary),
            leave_freq,
            emp_types.get(employee.employment_type, 0),
            dept_turnover,
            1 if employee.reports_to else 0,
            (float(employee.annual_leave_balance or 0)
             + float(employee.sick_leave_balance or 0)) / 60,
            float(avg_ot),
            salary_vs_dept,
            att_rate,
            payroll_months,
            avg_gross_pay,
            comp_vs_dept,
            absence_rate,
        ]])

    def predict(self, employee: Employee) -> float:
        """Return attrition probability 0–1 for an active employee."""
        self._load()
        if self._model is None:
            return 0.0

        features = self._build_single_feature_vector(employee)
        if features is None:
            return 0.0

        features_scaled = self._scaler.transform(features)
        prob = float(self._model.predict_proba(features_scaled)[0][1])

        log_prediction(self._registry, 'Employee', employee.pk, prob, {
            'employee_id': employee.employee_id,
            'name': employee.full_name,
        })

        return prob

    def score_all_active_employees(self) -> list[dict]:
        """Score every active employee and flag high-risk ones."""
        self._load()
        if self._model is None:
            return []

        employees = Employee.objects.filter(
            company=self.company, employment_status='active',
        ).select_related('department')

        results = []
        high_risk = []
        for emp in employees:
            try:
                risk = self.predict(emp)
                level = (
                    'high' if risk > 0.7
                    else 'medium' if risk > 0.4
                    else 'low'
                )
                result = {
                    'employee_id': emp.pk,
                    'employee_number': emp.employee_id,
                    'name': emp.full_name,
                    'department': emp.department.name if emp.department else '',
                    'risk_score': round(risk, 4),
                    'risk_level': level,
                }
                results.append(result)
                if level == 'high':
                    high_risk.append(result)
            except Exception as exc:
                logger.exception('Attrition scoring failed for %d: %s',
                                 emp.pk, exc)

        if high_risk:
            title = f'{len(high_risk)} employees at high attrition risk'
            create_or_update_insight(
                company=self.company,
                category=AIInsight.Category.HR,
                severity=AIInsight.Severity.WARNING,
                title=title,
                description=(
                    'The attrition model flagged: '
                    + ', '.join(f"{e['name']} ({e['department']})"
                                for e in high_risk[:10])
                ),
                recommendation=(
                    'Consider retention interviews, compensation reviews, '
                    'or workload adjustments for flagged employees.'
                ),
                action_url='/erp/employees/',
            )

        return results


# ════════════════════════════════════════════════════════════════════════════
# Attendance Anomaly Detection
# ════════════════════════════════════════════════════════════════════════════

class AttendanceAnomalyDetector:
    """Detect unusual patterns in attendance data using Z-scores."""

    def __init__(self, company):
        self.company = company

    def detect(self, lookback_days: int = 90) -> list[dict]:
        """Find employees whose recent attendance deviates significantly."""
        since = timezone.now() - timedelta(days=lookback_days)
        records = Attendance.objects.filter(
            employee__company=self.company,
            date__gte=since.date(),
        ).values('employee_id', 'employee__first_name',
                 'employee__last_name', 'employee__employee_id',
                 'check_in', 'check_out', 'hours_worked', 'is_late')

        df = pd.DataFrame(list(records))
        if df.empty:
            return []

        # Use pre-calculated hours_worked; fall back to 0
        df['hours'] = pd.to_numeric(df['hours_worked'], errors='coerce').fillna(0).clip(0, 24)

        # Per-employee statistics
        emp_stats = df.groupby('employee_id').agg(
            avg_hours=('hours', 'mean'),
            std_hours=('hours', 'std'),
            total_days=('hours', 'count'),
            late_arrivals=('is_late', 'sum'),
        ).reset_index()

        # Company-wide baseline
        company_avg = emp_stats['avg_hours'].mean()
        company_std = emp_stats['avg_hours'].std() or 1

        anomalies = []
        for _, row in emp_stats.iterrows():
            z_score = abs(row['avg_hours'] - company_avg) / company_std
            late_ratio = row['late_arrivals'] / max(row['total_days'], 1)
            if z_score > 1.5 or late_ratio > 0.25:
                emp_info = df[df['employee_id'] == row['employee_id']].iloc[0]
                anomalies.append({
                    'employee_id': int(row['employee_id']),
                    'employee_number': emp_info.get('employee__employee_id', ''),
                    'name': f"{emp_info['employee__first_name']} {emp_info['employee__last_name']}",
                    'avg_hours': round(row['avg_hours'], 2),
                    'company_avg_hours': round(company_avg, 2),
                    'z_score': round(z_score, 2),
                    'late_arrivals': int(row['late_arrivals']),
                    'total_days': int(row['total_days']),
                })

        if anomalies:
            title = f'{len(anomalies)} attendance anomalies detected'
            create_or_update_insight(
                company=self.company,
                category=AIInsight.Category.HR,
                severity=AIInsight.Severity.INFO,
                title=title,
                description=(
                    'Unusual attendance patterns detected for: '
                    + ', '.join(a['name'] for a in anomalies[:10])
                ),
                recommendation='Review attendance records for these employees.',
                action_url='/erp/attendance/',
            )

        return anomalies
