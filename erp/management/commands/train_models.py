"""
Management command: train_models

Trains / evaluates all ML models for a given tenant using imported data.
Produces a summary report with metrics for each model.

Usage:
    python manage.py train_models --tenant kuraimitttt
    python manage.py train_models --tenant kuraimitttt --models lead_scoring,attrition
    python manage.py train_models --tenant kuraimitttt --evaluate
"""

import time
import json
import logging
from datetime import datetime
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.conf import settings

from tenants.models import TenantDatabase
from tenants.routers import add_tenant_database, TenantDatabaseContext

from erp.models import Company

logger = logging.getLogger('erp.ai')

# Registry of trainable / runnable models
MODEL_REGISTRY = [
    {
        'key': 'lead_scoring',
        'name': 'Lead Scoring (LogisticRegression)',
        'type': 'classifier',
        'metric': 'AUC-ROC',
    },
    {
        'key': 'late_payment',
        'name': 'Late Payment Prediction (GradientBoosting)',
        'type': 'classifier',
        'metric': 'AUC-ROC',
    },
    {
        'key': 'attrition',
        'name': 'Employee Attrition (RandomForest)',
        'type': 'classifier',
        'metric': 'AUC-ROC',
    },
    {
        'key': 'expense_anomaly',
        'name': 'Expense Anomaly Detection (IsolationForest)',
        'type': 'detector',
        'metric': 'anomalies_found',
    },
    {
        'key': 'attendance_anomaly',
        'name': 'Attendance Anomaly Detection (Z-Score)',
        'type': 'detector',
        'metric': 'anomalies_found',
    },
    {
        'key': 'demand_forecast',
        'name': 'Demand Forecasting (Prophet)',
        'type': 'forecaster',
        'metric': 'accuracy',
    },
    {
        'key': 'cash_flow',
        'name': 'Cash Flow Forecasting (Rule-based)',
        'type': 'forecaster',
        'metric': 'summary',
    },
    {
        'key': 'kpi_anomaly',
        'name': 'KPI Anomaly Detection (Z-Score)',
        'type': 'detector',
        'metric': 'alerts',
    },
]


class Command(BaseCommand):
    help = "Train and evaluate all ML models for a tenant."

    def add_arguments(self, parser):
        parser.add_argument(
            "--tenant", type=str, required=True,
            help="Tenant DB name.",
        )
        parser.add_argument(
            "--company-id", type=int, default=None,
            help="Company ID. Defaults to first company.",
        )
        parser.add_argument(
            "--models", type=str, default=None,
            help="Comma-separated list of model keys to train (default: all).",
        )
        parser.add_argument(
            "--evaluate", action="store_true",
            help="After training, run predictions/detection on live data.",
        )

    def handle(self, *args, **options):
        db_alias = self._activate_tenant(options["tenant"])
        with TenantDatabaseContext(db_alias):
            self._run(options, db_alias)

    def _activate_tenant(self, tenant_name):
        try:
            tenant_db = TenantDatabase.objects.get(name=tenant_name)
        except TenantDatabase.DoesNotExist:
            avail = list(TenantDatabase.objects.filter(status="active")
                         .values_list("name", flat=True))
            raise CommandError(f"Tenant '{tenant_name}' not found. Available: {avail}")
        return add_tenant_database(tenant_db)

    def _run(self, options, db_alias):
        self.db = db_alias

        # Resolve company
        if options["company_id"]:
            company = Company.objects.using(self.db).filter(id=options["company_id"]).first()
            if not company:
                raise CommandError(f"Company id={options['company_id']} not found.")
        else:
            company = Company.objects.using(self.db).first()
            if not company:
                raise CommandError("No company found in this tenant DB.")
        self.company = company
        self.stdout.write(self.style.HTTP_INFO(
            f"Company: {company.name} (id={company.id})"
        ))

        # Filter models if specified
        selected_keys = None
        if options["models"]:
            selected_keys = [k.strip() for k in options["models"].split(",")]

        do_evaluate = options.get("evaluate", False)

        # ── Run training pipeline ─────────────────────────────────────
        self.stdout.write("")
        self.stdout.write("=" * 70)
        self.stdout.write("  ML MODEL TRAINING PIPELINE")
        self.stdout.write("=" * 70)
        self.stdout.write("")

        results = {}
        for model_info in MODEL_REGISTRY:
            key = model_info['key']
            if selected_keys and key not in selected_keys:
                continue

            self.stdout.write(self.style.HTTP_INFO(
                f"[{key}] {model_info['name']}"
            ))
            self.stdout.write("-" * 50)

            t0 = time.time()
            try:
                result = self._train_model(key, do_evaluate)
                elapsed = time.time() - t0
                result['elapsed_seconds'] = round(elapsed, 2)
                results[key] = result
                self._print_result(key, model_info, result)
            except Exception as exc:
                elapsed = time.time() - t0
                results[key] = {'status': 'error', 'error': str(exc),
                                'elapsed_seconds': round(elapsed, 2)}
                self.stdout.write(self.style.ERROR(f"  ERROR: {exc}"))
                logger.exception("Training failed for %s", key)

            self.stdout.write("")

        # ── Summary Report ────────────────────────────────────────────
        self._print_summary(results)

        # Save report JSON
        report_dir = Path(settings.ML_MODEL_DIR) / str(company.id)
        report_dir.mkdir(parents=True, exist_ok=True)
        report_path = report_dir / "training_report.json"
        with open(report_path, "w") as f:
            json.dump({
                'company_id': company.id,
                'company_name': company.name,
                'timestamp': datetime.now().isoformat(),
                'results': results,
            }, f, indent=2, default=str)
        self.stdout.write(f"\nReport saved to: {report_path}")

    # ==================================================================
    #  Per-model training & evaluation
    # ==================================================================

    def _train_model(self, key: str, do_evaluate: bool) -> dict:
        """Train a single model and optionally evaluate."""

        if key == 'lead_scoring':
            return self._train_lead_scoring(do_evaluate)
        elif key == 'late_payment':
            return self._train_late_payment(do_evaluate)
        elif key == 'attrition':
            return self._train_attrition(do_evaluate)
        elif key == 'expense_anomaly':
            return self._run_expense_anomaly()
        elif key == 'attendance_anomaly':
            return self._run_attendance_anomaly()
        elif key == 'demand_forecast':
            return self._train_demand_forecast()
        elif key == 'cash_flow':
            return self._run_cash_flow()
        elif key == 'kpi_anomaly':
            return self._run_kpi_anomaly()
        else:
            return {'status': 'unknown_model'}

    # ── 1. Lead Scoring ─────────────────────────────────────────────────

    def _train_lead_scoring(self, do_evaluate: bool) -> dict:
        from erp.ai.services.crm import LeadScorer
        scorer = LeadScorer(self.company)
        result = scorer.train()

        if result.get('status') == 'trained' and do_evaluate:
            self.stdout.write("  Running evaluation on active leads …")
            scored = scorer.score_all_active_leads()
            result['evaluation'] = {
                'leads_scored': len(scored),
                'hot': sum(1 for s in scored if s['level'] == 'hot'),
                'warm': sum(1 for s in scored if s['level'] == 'warm'),
                'cold': sum(1 for s in scored if s['level'] == 'cold'),
            }
        return result

    # ── 2. Late Payment ─────────────────────────────────────────────────

    def _train_late_payment(self, do_evaluate: bool) -> dict:
        from erp.ai.services.finance import LatePaymentPredictor
        predictor = LatePaymentPredictor(self.company)
        result = predictor.train()

        if result.get('status') == 'trained' and do_evaluate:
            self.stdout.write("  Running evaluation on open invoices …")
            scored = predictor.score_all_open_invoices()
            result['evaluation'] = {
                'invoices_scored': len(scored),
                'high_risk': sum(1 for s in scored if s['risk_level'] == 'high'),
                'medium_risk': sum(1 for s in scored if s['risk_level'] == 'medium'),
                'low_risk': sum(1 for s in scored if s['risk_level'] == 'low'),
            }
        return result

    # ── 3. Attrition ────────────────────────────────────────────────────

    def _train_attrition(self, do_evaluate: bool) -> dict:
        from erp.ai.services.hr import AttritionPredictor
        predictor = AttritionPredictor(self.company)
        result = predictor.train()

        if result.get('status') == 'trained' and do_evaluate:
            self.stdout.write("  Running evaluation on active employees …")
            scored = predictor.score_all_active_employees()
            result['evaluation'] = {
                'employees_scored': len(scored),
                'high_risk': sum(1 for s in scored if s['risk_level'] == 'high'),
                'medium_risk': sum(1 for s in scored if s['risk_level'] == 'medium'),
                'low_risk': sum(1 for s in scored if s['risk_level'] == 'low'),
            }
        return result

    # ── 4. Expense Anomaly (unsupervised) ───────────────────────────────

    def _run_expense_anomaly(self) -> dict:
        from erp.ai.services.finance import ExpenseAnomalyDetector
        detector = ExpenseAnomalyDetector(self.company)
        anomalies = detector.detect()

        # Cross-reference with ground truth from dataset
        from erp.models import Expense
        import pandas as pd
        csv_path = Path(__file__).resolve().parents[3] / "datasets" / "expense_claims_dataset.csv"
        gt_anomalies = set()
        if csv_path.exists():
            df = pd.read_csv(csv_path)
            gt_anomalies = set(df[df['is_anomaly'] == 1]['expense_number'].tolist())

        detected_nums = set()
        for a in anomalies:
            detected_nums.add(a['expense_number'])

        # Calculate precision/recall vs ground truth
        if gt_anomalies:
            true_positives = len(detected_nums & gt_anomalies)
            precision = true_positives / max(len(detected_nums), 1)
            recall = true_positives / max(len(gt_anomalies), 1)
            f1 = (2 * precision * recall / max(precision + recall, 1e-9))
        else:
            precision = recall = f1 = None

        result = {
            'status': 'completed',
            'anomalies_found': len(anomalies),
            'top_anomalies': anomalies[:5],
        }
        if precision is not None:
            result['ground_truth'] = {
                'gt_anomalies': len(gt_anomalies),
                'detected': len(detected_nums),
                'true_positives': true_positives,
                'precision': round(precision, 4),
                'recall': round(recall, 4),
                'f1_score': round(f1, 4),
            }
        return result

    # ── 5. Attendance Anomaly ───────────────────────────────────────────

    def _run_attendance_anomaly(self) -> dict:
        from erp.ai.services.hr import AttendanceAnomalyDetector
        detector = AttendanceAnomalyDetector(self.company)
        anomalies = detector.detect(lookback_days=365)

        return {
            'status': 'completed',
            'anomalies_found': len(anomalies),
            'top_anomalies': anomalies[:5],
        }

    # ── 6. Demand Forecast ──────────────────────────────────────────────

    def _train_demand_forecast(self) -> dict:
        from erp.models import StockMovement
        count = StockMovement.objects.using(self.db).filter(
            company=self.company
        ).count()
        if count == 0:
            return {
                'status': 'skipped',
                'reason': 'no_stock_movements',
                'note': 'Demand forecasting requires StockMovement data. '
                        'Import product/inventory data to enable this model.',
            }

        from erp.ai.services.demand import DemandForecaster
        forecaster = DemandForecaster(self.company)
        results = forecaster.update_all_reorder_rules()
        return {
            'status': 'completed' if results else 'skipped',
            'rules_updated': len(results),
            'results': results[:5],
        }

    # ── 7. Cash Flow ────────────────────────────────────────────────────

    def _run_cash_flow(self) -> dict:
        from erp.ai.services.finance import CashFlowForecaster
        forecaster = CashFlowForecaster(self.company)
        result = forecaster.forecast(periods=90)

        return {
            'status': 'completed',
            'summary': result.get('summary', {}),
            'data_points': len(result.get('dates', [])),
        }

    # ── 8. KPI Anomaly ──────────────────────────────────────────────────

    def _run_kpi_anomaly(self) -> dict:
        from erp.ai.services.kpi import KPIAnomalyDetector
        detector = KPIAnomalyDetector(self.company)
        alerts = detector.run_all_checks()

        return {
            'status': 'completed',
            'alerts': alerts,
            'alert_count': len(alerts),
        }

    # ==================================================================
    #  Output helpers
    # ==================================================================

    def _print_result(self, key, model_info, result):
        status = result.get('status', 'unknown')
        elapsed = result.get('elapsed_seconds', 0)

        if status == 'trained':
            style = self.style.SUCCESS
            metric_val = result.get('auc', result.get('accuracy', ''))
            samples = result.get('samples', 0)
            self.stdout.write(style(
                f"  [OK] TRAINED | {model_info['metric']}: {metric_val} | "
                f"Samples: {samples} | Time: {elapsed}s"
            ))

            # Feature importance for classifiers
            feat_imp = result.get('feature_importance', {})
            if feat_imp:
                self.stdout.write("  Feature Importance:")
                sorted_fi = sorted(feat_imp.items(), key=lambda x: -x[1])
                for fname, fval in sorted_fi[:7]:
                    bar = "#" * int(fval * 40)
                    self.stdout.write(f"    {fname:30s} {fval:.4f} {bar}")

            # Class report
            class_report = result.get('class_report', {})
            if class_report:
                for cls_key in ['0', '1']:
                    if cls_key in class_report:
                        cr = class_report[cls_key]
                        label = 'On-time' if cls_key == '0' else 'Late'
                        self.stdout.write(
                            f"    {label:10s}: P={cr['precision']:.3f} "
                            f"R={cr['recall']:.3f} F1={cr['f1-score']:.3f} "
                            f"N={cr['support']}"
                        )

            # Evaluation results
            eval_data = result.get('evaluation', {})
            if eval_data:
                self.stdout.write("  Evaluation:")
                for ek, ev in eval_data.items():
                    self.stdout.write(f"    {ek}: {ev}")

        elif status == 'completed':
            style = self.style.SUCCESS
            msg = f"  [OK] COMPLETED | Time: {elapsed}s"

            anomalies = result.get('anomalies_found')
            if anomalies is not None:
                msg += f" | Anomalies: {anomalies}"

            alerts = result.get('alert_count')
            if alerts is not None:
                msg += f" | Alerts: {alerts}"

            self.stdout.write(style(msg))

            # Ground truth comparison
            gt = result.get('ground_truth')
            if gt:
                self.stdout.write("  Ground Truth Evaluation:")
                self.stdout.write(f"    Precision: {gt['precision']:.4f}")
                self.stdout.write(f"    Recall:    {gt['recall']:.4f}")
                self.stdout.write(f"    F1 Score:  {gt['f1_score']:.4f}")
                self.stdout.write(
                    f"    (TP={gt['true_positives']} out of "
                    f"{gt['gt_anomalies']} actual, "
                    f"{gt['detected']} detected)"
                )

            # Cash flow summary
            summary = result.get('summary', {})
            if summary:
                self.stdout.write("  Cash Flow Projections:")
                for period, data in summary.items():
                    self.stdout.write(
                        f"    {period}: In={data.get('inflows',0):>12,.2f} | "
                        f"Out={data.get('outflows',0):>12,.2f} | "
                        f"Net={data.get('net',0):>12,.2f}"
                    )

            # KPI alerts
            for alert in result.get('alerts', []):
                sev = alert.get('severity', 'info')
                check = alert.get('check', '')
                z = alert.get('z_score', 0)
                self.stdout.write(f"    [{sev.upper()}] {check}: z={z}")

        elif status == 'skipped':
            reason = result.get('reason', '')
            note = result.get('note', '')
            self.stdout.write(self.style.WARNING(
                f"  [SKIP] SKIPPED: {reason}"
            ))
            if note:
                self.stdout.write(f"    {note}")

        elif status == 'error':
            self.stdout.write(self.style.ERROR(
                f"  [FAIL] ERROR: {result.get('error', 'unknown')}"
            ))

    def _print_summary(self, results):
        self.stdout.write("")
        self.stdout.write("=" * 70)
        self.stdout.write("  TRAINING SUMMARY")
        self.stdout.write("=" * 70)

        trained = [k for k, v in results.items() if v.get('status') == 'trained']
        completed = [k for k, v in results.items() if v.get('status') == 'completed']
        skipped = [k for k, v in results.items() if v.get('status') == 'skipped']
        errors = [k for k, v in results.items() if v.get('status') == 'error']

        total_time = sum(v.get('elapsed_seconds', 0) for v in results.values())

        self.stdout.write(self.style.SUCCESS(f"  Trained:   {len(trained):>2}  {', '.join(trained)}"))
        self.stdout.write(self.style.SUCCESS(f"  Completed: {len(completed):>2}  {', '.join(completed)}"))
        if skipped:
            self.stdout.write(self.style.WARNING(f"  Skipped:   {len(skipped):>2}  {', '.join(skipped)}"))
        if errors:
            self.stdout.write(self.style.ERROR(f"  Errors:    {len(errors):>2}  {', '.join(errors)}"))
        self.stdout.write(f"  Total time: {total_time:.1f}s")
        self.stdout.write("")

        # Model performance table
        self.stdout.write("  Model Performance:")
        self.stdout.write(f"  {'Model':<35} {'Metric':<10} {'Score':<10} {'Samples':<10}")
        self.stdout.write("  " + "-" * 65)
        for info in MODEL_REGISTRY:
            k = info['key']
            if k not in results:
                continue
            r = results[k]
            if r.get('status') == 'trained':
                score = r.get('auc', r.get('accuracy', '-'))
                samples = r.get('samples', '-')
                self.stdout.write(
                    f"  {info['name']:<35} {info['metric']:<10} "
                    f"{score!s:<10} {samples!s:<10}"
                )
            elif r.get('status') == 'completed':
                anomalies = r.get('anomalies_found', r.get('alert_count', '-'))
                gt = r.get('ground_truth', {})
                f1 = gt.get('f1_score', '-')
                self.stdout.write(
                    f"  {info['name']:<35} {'F1/Count':<10} "
                    f"{f1!s:<10} {anomalies!s:<10}"
                )
