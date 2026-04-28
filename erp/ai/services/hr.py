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
from sklearn.preprocessing import StandardScaler
from django.conf import settings
from django.db.models import Count, Avg, Q, Max
from django.utils import timezone

from erp.models import Employee, LeaveRequest, Attendance, Payroll
from erp.ai.models import MLModel, AIInsight
from .base import (
    get_or_create_registry,
    save_model_artefact,
    load_model_artefact,
    log_prediction,
    create_or_update_insight,
    evaluate_classifier,
    shuffle_label_auc,
)

logger = logging.getLogger("erp.ai.hr")


class AttritionPredictor:
    """Predict which employees are most likely to leave."""

    FEATURE_COLS = [
        "tenure_days",
        "salary",
        "leave_frequency",
        "employment_type_code",
        "department_turnover_rate",
        "has_reports_to",
        "leave_balance_ratio",
        "avg_overtime_hours",
        "salary_vs_dept_avg",
        "attendance_rate",
        "avg_gross_pay",
        "comp_vs_dept_avg",
        "absence_rate",
    ]

    def __init__(self, company):
        self.company = company
        self.min_samples = getattr(settings, "ML_MIN_TRAINING_SAMPLES", 30)
        self._model = None
        self._scaler = None
        self._registry = None

    # ── Dataset ─────────────────────────────────────────────────────────

    def _build_dataset(self) -> pd.DataFrame:
        """Build labelled dataset from active + terminated employees."""
        employees = Employee.objects.filter(
            company=self.company,
            employment_status__in=["active", "terminated", "resigned"],
        ).values(
            "id",
            "employment_status",
            "hire_date",
            "termination_date",
            "basic_salary",
            "employment_type",
            "department_id",
            "reports_to_id",
            "annual_leave_balance",
            "sick_leave_balance",
        )
        df = pd.DataFrame(list(employees))
        if df.empty or len(df) < self.min_samples:
            return pd.DataFrame()

        # Label: 1 = left (terminated / resigned), 0 = still active
        df["left"] = df["employment_status"].isin(["terminated", "resigned"]).astype(int)

        # Deterministic RNG for any random draws inside this builder so
        # retrains are reproducible (previously np.random.normal was called
        # without a seed, causing AUC jitter between runs).
        rng = np.random.default_rng(42)

        now = timezone.now().date()
        # ── Snapshot date & fixed observation window ─────────────────────
        # Every behavioural feature (attendance, payroll, leave) is computed
        # in a fixed-length window ending at this snapshot. This is critical:
        # without it, terminated employees get systematically smaller
        # attendance/payroll record counts (since data generation stops at
        # termination_date), turning record-count features into a near-perfect
        # proxy for the label (we previously saw AUC ≈ 1.00 from this leak).
        #
        # For active employees we anchor the snapshot at the latest available
        # data date in the company (NOT today). Otherwise — when training on
        # a static historical dataset — actives get a window where no records
        # exist, while leavers' windows DO contain records, and the mere
        # presence-of-data becomes a perfect class indicator.
        latest_att = (
            Attendance.objects.filter(employee__company=self.company)
            .aggregate(d=Max("date"))["d"]
        )
        active_snapshot = pd.Timestamp(latest_att) if latest_att else pd.Timestamp(now)
        df["snapshot_date"] = pd.to_datetime(
            df["termination_date"].fillna(active_snapshot)
        ).dt.tz_localize(None)
        window_days = getattr(settings, "ML_ATTRITION_WINDOW_DAYS", 90)
        df["window_start"] = df["snapshot_date"] - pd.Timedelta(days=window_days)
        # Tenure measured at snapshot date (for active employees this is
        # today, for leavers it is their last day) — what a model would
        # realistically see at prediction time.
        df["tenure_days"] = (
            df["snapshot_date"] - pd.to_datetime(df["hire_date"])
        ).dt.days.fillna(0).astype(int).clip(lower=0)

        df["salary"] = df["basic_salary"].astype(float)

        # ── Leave frequency in the per-employee window ───────────────────
        leave_rows = pd.DataFrame(
            list(
                LeaveRequest.objects.filter(
                    employee__company=self.company,
                    employee_id__in=df["id"].tolist(),
                ).values("employee_id", "created_at")
            )
        )
        if not leave_rows.empty:
            leave_rows["created_at"] = pd.to_datetime(leave_rows["created_at"]).dt.tz_localize(None)
            win = df[["id", "window_start", "snapshot_date"]].rename(columns={"id": "employee_id"})
            leave_rows = leave_rows.merge(win, on="employee_id", how="left")
            leave_rows = leave_rows[
                (leave_rows["created_at"] >= leave_rows["window_start"])
                & (leave_rows["created_at"] <= leave_rows["snapshot_date"])
            ]
            leave_counts = leave_rows.groupby("employee_id").size().to_dict()
        else:
            leave_counts = {}
        df["leave_frequency"] = df["id"].map(leave_counts).fillna(0).astype(int)

        # Employment type code
        emp_types = {"full_time": 0, "part_time": 1, "contract": 2, "intern": 3, "freelance": 4}
        df["employment_type_code"] = df["employment_type"].map(emp_types).fillna(0).astype(int)

        # Department turnover rate — **leave-one-out** to avoid target
        # leakage.  For each row, compute the fraction of OTHER employees
        # in the same department who left.  Using the full aggregate that
        # includes the current row lets a tree trivially recover the label
        # for small / homogeneous departments.
        dept_stats = (
            df.groupby("department_id").agg(dept_total=("id", "count"), dept_left=("left", "sum")).reset_index()
        )
        df = df.merge(dept_stats, on="department_id", how="left")
        df["department_turnover_rate"] = (
            (df["dept_left"] - df["left"]) / (df["dept_total"] - 1).clip(lower=1)
        ).fillna(0).clip(0, 1)
        df = df.drop(columns=["dept_total", "dept_left"])

        df["has_reports_to"] = df["reports_to_id"].notna().astype(int)
        df["leave_balance_ratio"] = (
            (df["annual_leave_balance"].fillna(0).astype(float) + df["sick_leave_balance"].fillna(0).astype(float)) / 60
        ).clip(0, 1)

        # ── Attendance features (windowed) ──────────────────────────────
        att_rows = pd.DataFrame(
            list(
                Attendance.objects.filter(
                    employee__company=self.company,
                    employee_id__in=df["id"].tolist(),
                ).values("employee_id", "date", "is_present", "overtime_hours")
            )
        )
        if not att_rows.empty:
            att_rows["date"] = pd.to_datetime(att_rows["date"])
            win = df[["id", "window_start", "snapshot_date"]].rename(columns={"id": "employee_id"})
            att_rows = att_rows.merge(win, on="employee_id", how="left")
            att_rows = att_rows[
                (att_rows["date"] >= att_rows["window_start"])
                & (att_rows["date"] <= att_rows["snapshot_date"])
            ]
            att_rows["overtime_hours"] = att_rows["overtime_hours"].astype(float)
            agg = att_rows.groupby("employee_id").agg(
                total_days=("date", "count"),
                present_days=("is_present", "sum"),
                avg_ot=("overtime_hours", "mean"),
            )
            ot_dict = agg["avg_ot"].to_dict()
            att_dict = (agg["present_days"] / agg["total_days"].clip(lower=1)).to_dict()
        else:
            ot_dict = {}
            att_dict = {}

        df["avg_overtime_hours"] = df["id"].map(ot_dict).astype(float)
        ot_known = df["avg_overtime_hours"].dropna()
        ot_missing = df["avg_overtime_hours"].isna()
        if len(ot_known) > 0 and ot_missing.any():
            ot_mu, ot_sig = ot_known.mean(), max(ot_known.std(), 0.01)
            df.loc[ot_missing, "avg_overtime_hours"] = rng.normal(
                ot_mu, ot_sig, size=ot_missing.sum()
            ).clip(min=0)
        else:
            df["avg_overtime_hours"] = df["avg_overtime_hours"].fillna(0)

        # Salary relative to department average
        dept_salary = (df.groupby("department_id")["salary"].transform("mean")).clip(lower=1)
        df["salary_vs_dept_avg"] = df["salary"] / dept_salary

        df["attendance_rate"] = df["id"].map(att_dict).astype(float)
        att_known = df["attendance_rate"].dropna()
        att_missing = df["attendance_rate"].isna()
        if len(att_known) > 0 and att_missing.any():
            att_mu, att_sig = att_known.mean(), max(att_known.std(), 0.01)
            df["attendance_rate"] = df["attendance_rate"].copy()
            df.loc[att_missing, "attendance_rate"] = rng.normal(
                att_mu, att_sig, size=att_missing.sum()
            ).clip(0, 1)
        else:
            df["attendance_rate"] = df["attendance_rate"].fillna(0.9)

        # ── Payroll features (windowed) ─────────────────────────────────
        pr_rows = pd.DataFrame(
            list(
                Payroll.objects.filter(
                    employee__company=self.company,
                    employee_id__in=df["id"].tolist(),
                ).values("employee_id", "period_end", "gross_salary")
            )
        )
        if not pr_rows.empty and "period_end" in pr_rows.columns:
            pr_rows["period_end"] = pd.to_datetime(pr_rows["period_end"])
            win = df[["id", "window_start", "snapshot_date"]].rename(columns={"id": "employee_id"})
            pr_rows = pr_rows.merge(win, on="employee_id", how="left")
            pr_rows = pr_rows[
                (pr_rows["period_end"] >= pr_rows["window_start"])
                & (pr_rows["period_end"] <= pr_rows["snapshot_date"])
            ]
            pr_rows["gross_salary"] = pr_rows["gross_salary"].astype(float)
            pr_agg = pr_rows.groupby("employee_id").agg(avg_gross=("gross_salary", "mean"))
            avg_gross_dict = pr_agg["avg_gross"].to_dict()
        else:
            avg_gross_dict = {}

        df["avg_gross_pay"] = df["id"].map(avg_gross_dict).fillna(df["salary"]).astype(float)

        # Total compensation vs department average
        dept_comp = (df.groupby("department_id")["avg_gross_pay"].transform("mean")).clip(lower=1)
        df["comp_vs_dept_avg"] = df["avg_gross_pay"] / dept_comp

        # Absence rate (complement of attendance_rate, scaled)
        df["absence_rate"] = (1 - df["attendance_rate"]).clip(0, 1)

        # Drop helper columns before returning
        df = df.drop(columns=["snapshot_date", "window_start"], errors="ignore")
        return df

    # ── Training ────────────────────────────────────────────────────────

    def train(self, shuffle_labels: bool = False) -> dict:
        df = self._build_dataset()
        if df.empty:
            return {"status": "skipped", "reason": "insufficient_data"}

        X = df[self.FEATURE_COLS].fillna(0).values
        y = df["left"].values

        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)

        clf = RandomForestClassifier(
            n_estimators=500,
            max_depth=10,
            min_samples_leaf=5,
            class_weight="balanced",
            random_state=42,
            max_features="sqrt",
        )

        # ── Stratified K-fold evaluation with baseline ──────────────────
        cv_metrics = evaluate_classifier(clf, X_scaled, y)
        shuffle_auc = shuffle_label_auc(clf, X_scaled, y) if not shuffle_labels else None

        # If caller wants the shuffle sanity check, run with shuffled
        # labels and return early without persisting anything.
        if shuffle_labels:
            shuffled = shuffle_label_auc(clf, X_scaled, y, n_repeats=5)
            return {
                "status": "shuffle_check",
                "shuffled_auc": shuffled,
                "samples": len(df),
                "note": "AUC > 0.55 with shuffled labels indicates target leakage.",
            }

        # Final model refit on full data for production use.
        clf.fit(X_scaled, y)

        # Feature importance (from fitted forest) for interpretability.
        feat_imp = dict(zip(self.FEATURE_COLS, np.round(clf.feature_importances_, 4).tolist()))

        auc = cv_metrics.get("auc_mean") or 0.0

        registry = get_or_create_registry(
            self.company,
            MLModel.ModelType.ATTRITION,
            "Employee Attrition Predictor",
        )
        registry.training_samples = len(df)
        registry.accuracy_score = auc
        registry.parameters = {
            "feature_cols": self.FEATURE_COLS,
            "feature_importance": feat_imp,
            "cv_metrics": cv_metrics,
            "shuffled_label_auc": shuffle_auc,
        }
        save_model_artefact(
            registry,
            {
                "classifier": clf,
                "scaler": scaler,
                "feature_cols": self.FEATURE_COLS,
            },
        )

        self._model = clf
        self._scaler = scaler
        self._registry = registry

        logger.info("Attrition model trained: AUC=%.4f samples=%d", auc, len(df))
        return {
            "status": "trained",
            "auc": round(auc, 4),
            "samples": len(df),
            "feature_importance": feat_imp,
            "cv_metrics": cv_metrics,
            "shuffled_label_auc": shuffle_auc,
        }

    # ── Prediction ──────────────────────────────────────────────────────

    def _load(self):
        if self._model is not None:
            return
        self._registry = get_or_create_registry(
            self.company,
            MLModel.ModelType.ATTRITION,
            "Employee Attrition Predictor",
        )
        if not self._registry.artefact_path:
            self.train()
            return
        artefact = load_model_artefact(self._registry)
        self._model = artefact["classifier"]
        self._scaler = artefact["scaler"]

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
            company=self.company,
            department=employee.department,
        )
        dept_total = dept_employees.count() or 1
        dept_left = dept_employees.filter(
            employment_status__in=["terminated", "resigned"],
        ).count()
        dept_turnover = dept_left / dept_total

        emp_types = {"full_time": 0, "part_time": 1, "contract": 2, "intern": 3, "freelance": 4}

        avg_ot_val = Attendance.objects.filter(
            employee=employee,
        ).aggregate(avg_ot=Avg("overtime_hours"))["avg_ot"]
        if avg_ot_val is None:
            avg_ot_val = (
                Attendance.objects.filter(
                    employee__company=self.company,
                ).aggregate(avg_ot=Avg("overtime_hours"))["avg_ot"]
                or 0
            )
        avg_ot = float(avg_ot_val)

        dept_avg_salary = dept_employees.aggregate(avg_sal=Avg("basic_salary"))["avg_sal"] or 1
        salary_vs_dept = float(employee.basic_salary) / max(float(dept_avg_salary), 1)

        att_data = Attendance.objects.filter(
            employee=employee,
        ).aggregate(
            total=Count("id"),
            present=Count("id", filter=Q(is_present=True)),
        )
        if att_data["total"]:
            att_rate = att_data["present"] / max(att_data["total"], 1)
        else:
            co_att = Attendance.objects.filter(
                employee__company=self.company,
            ).aggregate(
                total=Count("id"),
                present=Count("id", filter=Q(is_present=True)),
            )
            att_rate = co_att["present"] / max(co_att["total"], 1) if co_att["total"] else 0.9

        payroll_agg = Payroll.objects.filter(
            employee=employee,
        ).aggregate(cnt=Count("id"), avg_gross=Avg("gross_salary"))
        avg_gross_pay = float(payroll_agg["avg_gross"] or employee.basic_salary)

        dept_avg_comp = Payroll.objects.filter(
            employee__company=self.company,
            employee__department=employee.department,
        ).aggregate(avg_g=Avg("gross_salary"))["avg_g"]
        comp_vs_dept = avg_gross_pay / max(float(dept_avg_comp or avg_gross_pay), 1)

        absence_rate = max(0.0, min(1.0, 1 - att_rate))

        return np.array(
            [
                [
                    tenure,
                    float(employee.basic_salary),
                    leave_freq,
                    emp_types.get(employee.employment_type, 0),
                    dept_turnover,
                    1 if employee.reports_to else 0,
                    (float(employee.annual_leave_balance or 0) + float(employee.sick_leave_balance or 0)) / 60,
                    float(avg_ot),
                    salary_vs_dept,
                    att_rate,
                    avg_gross_pay,
                    comp_vs_dept,
                    absence_rate,
                ]
            ]
        )

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

        log_prediction(
            self._registry,
            "Employee",
            employee.pk,
            prob,
            {
                "employee_id": employee.employee_id,
                "name": employee.full_name,
            },
        )

        return prob

    def score_all_active_employees(self) -> list[dict]:
        """Score every active employee and flag high-risk ones."""
        self._load()
        if self._model is None:
            return []

        employees = Employee.objects.filter(
            company=self.company,
            employment_status="active",
        ).select_related("department")

        results = []
        high_risk = []
        for emp in employees:
            try:
                risk = self.predict(emp)
                level = "high" if risk > 0.7 else "medium" if risk > 0.4 else "low"
                result = {
                    "employee_id": emp.pk,
                    "employee_number": emp.employee_id,
                    "name": emp.full_name,
                    "department": emp.department.name if emp.department else "",
                    "risk_score": round(risk, 4),
                    "risk_level": level,
                }
                results.append(result)
                if level == "high":
                    high_risk.append(result)
            except Exception as exc:
                logger.exception("Attrition scoring failed for %d: %s", emp.pk, exc)

        if high_risk:
            title = f"{len(high_risk)} employees at high attrition risk"
            create_or_update_insight(
                company=self.company,
                category=AIInsight.Category.HR,
                severity=AIInsight.Severity.WARNING,
                title=title,
                description=(
                    "The attrition model flagged: "
                    + ", ".join(f"{e['name']} ({e['department']})" for e in high_risk[:10])
                ),
                recommendation=(
                    "Consider retention interviews, compensation reviews, "
                    "or workload adjustments for flagged employees."
                ),
                action_url="/erp/employees/",
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
        ).values(
            "employee_id",
            "employee__first_name",
            "employee__last_name",
            "employee__employee_id",
            "check_in",
            "check_out",
            "hours_worked",
            "is_late",
        )

        df = pd.DataFrame(list(records))
        if df.empty:
            return []

        # Use pre-calculated hours_worked; fall back to 0
        df["hours"] = pd.to_numeric(df["hours_worked"], errors="coerce").fillna(0).clip(0, 24)

        # Per-employee statistics
        emp_stats = (
            df.groupby("employee_id")
            .agg(
                avg_hours=("hours", "mean"),
                std_hours=("hours", "std"),
                total_days=("hours", "count"),
                late_arrivals=("is_late", "sum"),
            )
            .reset_index()
        )

        # Company-wide baseline
        company_avg = emp_stats["avg_hours"].mean()
        company_std = emp_stats["avg_hours"].std() or 1

        anomalies = []
        for _, row in emp_stats.iterrows():
            z_score = abs(row["avg_hours"] - company_avg) / company_std
            late_ratio = row["late_arrivals"] / max(row["total_days"], 1)
            if z_score > 1.5 or late_ratio > 0.25:
                emp_info = df[df["employee_id"] == row["employee_id"]].iloc[0]
                anomalies.append(
                    {
                        "employee_id": int(row["employee_id"]),
                        "employee_number": emp_info.get("employee__employee_id", ""),
                        "name": f"{emp_info['employee__first_name']} {emp_info['employee__last_name']}",
                        "avg_hours": round(row["avg_hours"], 2),
                        "company_avg_hours": round(company_avg, 2),
                        "z_score": round(z_score, 2),
                        "late_arrivals": int(row["late_arrivals"]),
                        "total_days": int(row["total_days"]),
                    }
                )

        if anomalies:
            title = f"{len(anomalies)} attendance anomalies detected"
            create_or_update_insight(
                company=self.company,
                category=AIInsight.Category.HR,
                severity=AIInsight.Severity.INFO,
                title=title,
                description=(
                    "Unusual attendance patterns detected for: " + ", ".join(a["name"] for a in anomalies[:10])
                ),
                recommendation="Review attendance records for these employees.",
                action_url="/erp/attendance/",
            )

        return anomalies
