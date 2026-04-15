"""
Explainable AI (XAI) Service

Provides SHAP and LIME explanations for all ML models in the ERP system:
1. SHAP TreeExplainer  – for tree-based models (GBM, Random Forest)
2. LIME TabularExplainer – for any sklearn classifier (fallback / comparison)

Supported model types:
- Late Payment Prediction    (GBM)  → SHAP + LIME
- Lead Scoring               (GBM)  → SHAP + LIME
- Employee Attrition          (RF)   → SHAP + LIME
- Expense Anomaly Detection  (IF)   → LIME only
"""

import io
import base64
import logging

import numpy as np
import pandas as pd
import shap
import lime
import lime.lime_tabular

from erp.ai.models import MLModel, ExplanationResult
from .base import load_model_artefact

logger = logging.getLogger('erp.ai.xai')

# Models that use tree-based classifiers (SHAP TreeExplainer compatible)
TREE_MODELS = {
    MLModel.ModelType.LATE_PAYMENT,
    MLModel.ModelType.LEAD_SCORING,
    MLModel.ModelType.ATTRITION,
}


class ExplainabilityService:
    """Generate SHAP and LIME explanations for trained ML models."""

    def __init__(self, company):
        self.company = company

    # ════════════════════════════════════════════════════════════════════════
    #  Public API
    # ════════════════════════════════════════════════════════════════════════

    def explain_prediction(
        self,
        model_type: str,
        entity_type: str,
        entity_id: int,
        method: str = 'shap',
    ) -> dict:
        """Generate an explanation for a single prediction.

        Args:
            model_type: One of MLModel.ModelType values.
            entity_type: 'Invoice', 'Lead', or 'Employee'.
            entity_id: Primary key of the entity.
            method: 'shap' or 'lime'.

        Returns:
            Dict with feature_contributions, base_value, prediction,
            and visualization data.
        """
        registry = self._get_registry(model_type)
        if not registry or not registry.artefact_path:
            return {'error': 'Model not trained yet'}

        artefact = load_model_artefact(registry)
        features, feature_names = self._build_feature_vector(
            model_type, entity_type, entity_id, artefact,
        )
        if features is None:
            return {'error': f'{entity_type} #{entity_id} not found'}

        if method == 'shap' and model_type in TREE_MODELS:
            result = self._shap_explain(artefact, features, feature_names,
                                        model_type)
        else:
            result = self._lime_explain(artefact, features, feature_names,
                                        model_type)

        # Persist the explanation
        self._save_explanation(
            registry=registry,
            entity_type=entity_type,
            entity_id=entity_id,
            method=method,
            result=result,
        )

        return result

    def global_feature_importance(self, model_type: str) -> dict:
        """Compute global SHAP feature importance for a model.

        Uses a background sample from the training dataset to compute
        mean |SHAP values| per feature.
        """
        registry = self._get_registry(model_type)
        if not registry or not registry.artefact_path:
            return {'error': 'Model not trained yet'}

        artefact = load_model_artefact(registry)
        background_df = self._get_background_data(model_type, artefact)

        if background_df is None or background_df.empty:
            return {'error': 'Insufficient data for global explanations'}

        feature_names = self._get_feature_names(model_type, artefact)
        X_bg = background_df[feature_names].fillna(0).values

        # Limit to 200 samples for performance
        if len(X_bg) > 200:
            indices = np.random.RandomState(42).choice(
                len(X_bg), 200, replace=False,
            )
            X_bg = X_bg[indices]

        classifier = artefact['classifier']

        # Apply scaler if present
        if 'scaler' in artefact:
            X_bg = artefact['scaler'].transform(X_bg)

        if model_type in TREE_MODELS:
            explainer = shap.TreeExplainer(classifier)
            shap_values = explainer.shap_values(X_bg)

            # For binary classification, shap_values is a list [neg_class, pos_class]
            if isinstance(shap_values, list):
                sv = np.array(shap_values[1])
            else:
                sv = np.array(shap_values)
                # Newer SHAP returns 3D (n_samples, n_features, n_classes)
                if sv.ndim == 3:
                    sv = sv[:, :, 1]  # positive class

            mean_abs_shap = np.abs(sv).mean(axis=0)
            importance = dict(zip(
                feature_names,
                mean_abs_shap.round(4).tolist(),
            ))
            # Sort by importance descending
            importance = dict(sorted(
                importance.items(), key=lambda x: x[1], reverse=True,
            ))

            # Generate summary plot as base64
            summary_plot_b64 = self._generate_summary_plot(
                sv, feature_names,
            )

            # Generate beeswarm data for Plotly
            beeswarm_data = self._generate_beeswarm_data(
                sv, X_bg, feature_names,
            )

            result = {
                'model_type': model_type,
                'method': 'shap',
                'feature_importance': importance,
                'total_samples': len(X_bg),
                'summary_plot': summary_plot_b64,
                'beeswarm_data': beeswarm_data,
                'base_value': self._extract_base_value(explainer.expected_value),
            }
        else:
            # Fallback: use sklearn feature_importances_
            importance = dict(zip(
                feature_names,
                classifier.feature_importances_.round(4).tolist(),
            ))
            importance = dict(sorted(
                importance.items(), key=lambda x: x[1], reverse=True,
            ))
            result = {
                'model_type': model_type,
                'method': 'builtin',
                'feature_importance': importance,
                'total_samples': 0,
            }

        return result

    def get_explanation_history(
        self,
        model_type: str | None = None,
        entity_type: str | None = None,
        entity_id: int | None = None,
        limit: int = 50,
    ) -> list[dict]:
        """Retrieve stored explanations with optional filters."""
        qs = ExplanationResult.objects.filter(
            model__company=self.company,
        ).select_related('model')

        if model_type:
            qs = qs.filter(model__model_type=model_type)
        if entity_type:
            qs = qs.filter(entity_type=entity_type)
        if entity_id:
            qs = qs.filter(entity_id=entity_id)

        results = []
        for exp in qs[:limit]:
            results.append({
                'id': exp.pk,
                'model_type': exp.model.model_type,
                'model_name': exp.model.name,
                'entity_type': exp.entity_type,
                'entity_id': exp.entity_id,
                'method': exp.method,
                'prediction_score': exp.prediction_score,
                'top_features': exp.top_features,
                'created_at': exp.created_at.isoformat(),
            })
        return results

    # ════════════════════════════════════════════════════════════════════════
    #  SHAP Explanation
    # ════════════════════════════════════════════════════════════════════════

    def _shap_explain(self, artefact, features, feature_names, model_type):
        """Generate SHAP explanation for a single instance."""
        classifier = artefact['classifier']

        # Apply scaler if present
        X = features.copy()
        if 'scaler' in artefact:
            X = artefact['scaler'].transform(X)

        explainer = shap.TreeExplainer(classifier)
        shap_values = explainer.shap_values(X)

        # For binary classifiers, take the positive class
        if isinstance(shap_values, list):
            sv = shap_values[1][0]
        else:
            sv = np.array(shap_values)
            # Newer SHAP returns 3D (n_samples, n_features, n_classes)
            if sv.ndim == 3:
                sv = sv[0, :, 1]
            else:
                sv = sv[0]

        base_value = self._extract_base_value(explainer.expected_value)

        # Get prediction
        prediction = float(classifier.predict_proba(X)[0][1])

        # Build feature contributions
        contributions = {}
        for name, shap_val, feat_val in zip(feature_names, sv,
                                             features[0]):
            contributions[name] = {
                'shap_value': round(float(shap_val), 6),
                'feature_value': round(float(feat_val), 4),
                'direction': 'increases' if shap_val > 0 else 'decreases',
            }

        # Sort by absolute SHAP value
        sorted_contrib = dict(sorted(
            contributions.items(),
            key=lambda x: abs(x[1]['shap_value']),
            reverse=True,
        ))

        # Top features for quick display
        top_features = []
        for name, data in list(sorted_contrib.items())[:5]:
            top_features.append({
                'feature': name,
                'shap_value': data['shap_value'],
                'feature_value': data['feature_value'],
                'direction': data['direction'],
                'impact': self._human_readable_impact(
                    name, data['shap_value'], data['feature_value'],
                ),
            })

        # Waterfall plot data (for Plotly rendering on frontend)
        waterfall_data = self._build_waterfall_data(
            sorted_contrib, base_value, prediction,
        )

        return {
            'method': 'shap',
            'prediction': round(prediction, 4),
            'base_value': round(base_value, 4),
            'contributions': sorted_contrib,
            'top_features': top_features,
            'waterfall_data': waterfall_data,
            'feature_count': len(feature_names),
        }

    # ════════════════════════════════════════════════════════════════════════
    #  LIME Explanation
    # ════════════════════════════════════════════════════════════════════════

    def _lime_explain(self, artefact, features, feature_names, model_type):
        """Generate LIME explanation for a single instance."""
        classifier = artefact['classifier']

        # Build background data for LIME
        background_df = self._get_background_data(model_type, artefact)
        if background_df is None or background_df.empty:
            return {'error': 'Insufficient background data for LIME'}

        X_bg = background_df[feature_names].fillna(0).values

        # Apply scaler if present
        X = features.copy()
        if 'scaler' in artefact:
            X_bg = artefact['scaler'].transform(X_bg)
            X = artefact['scaler'].transform(X)

        # Determine prediction function
        if hasattr(classifier, 'predict_proba'):
            predict_fn = classifier.predict_proba
            mode = 'classification'
        else:
            predict_fn = classifier.decision_function
            mode = 'regression'

        explainer = lime.lime_tabular.LimeTabularExplainer(
            training_data=X_bg,
            feature_names=feature_names,
            mode=mode,
            random_state=42,
        )

        explanation = explainer.explain_instance(
            X[0],
            predict_fn,
            num_features=len(feature_names),
        )

        # Get prediction
        if hasattr(classifier, 'predict_proba'):
            prediction = float(classifier.predict_proba(X)[0][1])
        else:
            prediction = float(classifier.decision_function(X)[0])

        # Build contributions from LIME
        lime_weights = explanation.as_list()
        contributions = {}
        for feat_desc, weight in lime_weights:
            # LIME returns feature descriptions like "feature_name <= 0.5"
            # Map them back to original feature names
            matched_name = self._match_lime_feature(feat_desc, feature_names)
            feat_idx = feature_names.index(matched_name) if matched_name in feature_names else -1
            feat_val = float(features[0][feat_idx]) if feat_idx >= 0 else 0.0
            contributions[matched_name or feat_desc] = {
                'lime_weight': round(float(weight), 6),
                'feature_value': round(feat_val, 4),
                'direction': 'increases' if weight > 0 else 'decreases',
                'description': feat_desc,
            }

        sorted_contrib = dict(sorted(
            contributions.items(),
            key=lambda x: abs(x[1]['lime_weight']),
            reverse=True,
        ))

        top_features = []
        for name, data in list(sorted_contrib.items())[:5]:
            top_features.append({
                'feature': name,
                'lime_weight': data['lime_weight'],
                'feature_value': data['feature_value'],
                'direction': data['direction'],
                'impact': self._human_readable_impact(
                    name, data['lime_weight'], data['feature_value'],
                ),
            })

        return {
            'method': 'lime',
            'prediction': round(prediction, 4),
            'intercept': round(float(explanation.intercept[1]), 4)
            if hasattr(explanation, 'intercept') and len(explanation.intercept) > 1
            else 0.0,
            'contributions': sorted_contrib,
            'top_features': top_features,
            'feature_count': len(feature_names),
            'score': round(float(explanation.score), 4)
            if hasattr(explanation, 'score') else None,
        }

    # ════════════════════════════════════════════════════════════════════════
    #  Helpers
    # ════════════════════════════════════════════════════════════════════════

    @staticmethod
    def _extract_base_value(expected_value) -> float:
        """Safely extract the positive-class base value from SHAP."""
        ev = np.array(expected_value)
        if ev.ndim == 0:
            return float(ev)
        if len(ev) >= 2:
            return float(ev[1])
        return float(ev[0])

    def _get_registry(self, model_type: str) -> MLModel | None:
        return MLModel.objects.filter(
            company=self.company,
            model_type=model_type,
            is_active=True,
        ).order_by('-version').first()

    def _get_feature_names(self, model_type: str, artefact: dict) -> list:
        """Extract feature column names from the artefact."""
        if 'feature_cols' in artefact:
            return artefact['feature_cols']
        # Fallback: check registry parameters
        registry = self._get_registry(model_type)
        if registry and registry.parameters.get('feature_cols'):
            return registry.parameters['feature_cols']
        # Fallback: read FEATURE_COLS from the service class directly
        service_map = {
            MLModel.ModelType.LATE_PAYMENT: 'erp.ai.services.finance.LatePaymentPredictor',
            MLModel.ModelType.LEAD_SCORING: 'erp.ai.services.crm.LeadScorer',
            MLModel.ModelType.ATTRITION: 'erp.ai.services.hr.AttritionPredictor',
        }
        if model_type in service_map:
            module_path, cls_name = service_map[model_type].rsplit('.', 1)
            import importlib
            mod = importlib.import_module(module_path)
            cls = getattr(mod, cls_name)
            if hasattr(cls, 'FEATURE_COLS'):
                return cls.FEATURE_COLS
        return []

    def _build_feature_vector(
        self, model_type, entity_type, entity_id, artefact,
    ) -> tuple[np.ndarray | None, list]:
        """Build features for a specific entity using the existing service."""
        feature_names = self._get_feature_names(model_type, artefact)

        if model_type == MLModel.ModelType.LATE_PAYMENT:
            return self._features_late_payment(entity_id, artefact)
        elif model_type == MLModel.ModelType.LEAD_SCORING:
            return self._features_lead_scoring(entity_id, artefact)
        elif model_type == MLModel.ModelType.ATTRITION:
            return self._features_attrition(entity_id, artefact)
        elif model_type == MLModel.ModelType.EXPENSE_ANOMALY:
            return self._features_expense_anomaly(entity_id, artefact)

        return None, feature_names

    def _features_late_payment(self, invoice_id, artefact):
        """Build features for an invoice using LatePaymentPredictor logic."""
        from erp.ai.services.finance import LatePaymentPredictor

        from erp.models import Invoice
        try:
            invoice = Invoice.objects.select_related('customer').get(
                pk=invoice_id, company=self.company,
            )
        except Invoice.DoesNotExist:
            return None, []

        predictor = LatePaymentPredictor(self.company)
        predictor._load()
        if predictor._model is None:
            return None, []

        # Reuse the predict method's feature construction logic
        features = predictor._build_single_feature_vector(invoice)
        if features is None:
            # Fallback: call predict to warm up, then re-extract
            predictor.predict(invoice)
            return None, []

        return features, predictor.FEATURE_COLS

    def _features_lead_scoring(self, lead_id, artefact):
        """Build features for a lead using LeadScorer logic."""
        from erp.ai.services.crm import LeadScorer

        from erp.models import Lead
        try:
            lead = Lead.objects.get(pk=lead_id, company=self.company)
        except Lead.DoesNotExist:
            return None, []

        scorer = LeadScorer(self.company)
        scorer._load()
        if scorer._model is None:
            return None, []

        features = scorer._build_single_feature_vector(lead)
        if features is None:
            return None, []

        return features, scorer.FEATURE_COLS

    def _features_attrition(self, employee_id, artefact):
        """Build features for an employee using AttritionPredictor logic."""
        from erp.ai.services.hr import AttritionPredictor

        from erp.models import Employee
        try:
            employee = Employee.objects.select_related('department').get(
                pk=employee_id, company=self.company,
            )
        except Employee.DoesNotExist:
            return None, []

        predictor = AttritionPredictor(self.company)
        predictor._load()
        if predictor._model is None:
            return None, []

        features = predictor._build_single_feature_vector(employee)
        if features is None:
            return None, []

        return features, predictor.FEATURE_COLS

    def _features_expense_anomaly(self, expense_id, artefact):
        """Build features for an expense."""
        from erp.models import Expense

        try:
            expense = Expense.objects.select_related('category').get(
                pk=expense_id, company=self.company,
            )
        except Expense.DoesNotExist:
            return None, []

        feature_cols = [
            'amount', 'amount_log', 'month', 'day_of_week', 'is_weekend',
            'category_code', 'amount_vs_cat_z', 'amount_vs_cat_ratio',
            'amount_vs_emp_z', 'emp_count', 'amount_percentile',
        ]

        amount = float(expense.total_amount)
        month = expense.expense_date.month if expense.expense_date else 1
        dow = expense.expense_date.weekday() if expense.expense_date else 0

        # Simplified feature vector (category/employee z-scores approximated)
        features = np.array([[
            amount,
            np.log1p(amount),
            month,
            dow,
            1 if dow >= 5 else 0,
            0,   # category_code (simplified)
            0.0, # amount_vs_cat_z
            1.0, # amount_vs_cat_ratio
            0.0, # amount_vs_emp_z
            1,   # emp_count
            0.5, # amount_percentile
        ]])

        return features, feature_cols

    def _get_background_data(self, model_type, artefact) -> pd.DataFrame | None:
        """Build a background dataset for SHAP/LIME from DB records."""
        if model_type == MLModel.ModelType.LATE_PAYMENT:
            from erp.ai.services.finance import LatePaymentPredictor
            predictor = LatePaymentPredictor(self.company)
            return predictor._build_dataset()
        elif model_type == MLModel.ModelType.LEAD_SCORING:
            from erp.ai.services.crm import LeadScorer
            scorer = LeadScorer(self.company)
            return scorer._build_dataset()
        elif model_type == MLModel.ModelType.ATTRITION:
            from erp.ai.services.hr import AttritionPredictor
            predictor = AttritionPredictor(self.company)
            return predictor._build_dataset()

        return None

    def _match_lime_feature(self, desc: str, feature_names: list) -> str:
        """Map a LIME feature description back to the original feature name."""
        for name in feature_names:
            if name in desc:
                return name
        # If no match, return the description itself
        return desc.split(' ')[0] if ' ' in desc else desc

    def _build_waterfall_data(self, contributions, base_value, prediction):
        """Build data structure for a Plotly waterfall chart."""
        items = list(contributions.items())[:10]  # top 10 features
        labels = ['Base Value']
        values = [base_value]
        measures = ['absolute']

        for name, data in items:
            shap_val = data.get('shap_value', data.get('lime_weight', 0))
            labels.append(name)
            values.append(shap_val)
            measures.append('relative')

        labels.append('Prediction')
        values.append(prediction)
        measures.append('total')

        return {
            'labels': labels,
            'values': [round(v, 4) for v in values],
            'measures': measures,
        }

    def _generate_summary_plot(self, shap_values, feature_names):
        """Generate a SHAP summary bar plot as base64 PNG."""
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt

        mean_abs = np.abs(shap_values).mean(axis=0)
        sorted_idx = np.argsort(mean_abs).tolist()

        fig, ax = plt.subplots(figsize=(10, max(6, len(feature_names) * 0.35)))
        names = [feature_names[i] for i in sorted_idx]
        vals = [float(mean_abs[i]) for i in sorted_idx]

        colors = plt.cm.RdYlBu_r(np.linspace(0.2, 0.8, len(names)))
        ax.barh(range(len(names)), vals, color=colors)
        ax.set_yticks(range(len(names)))
        ax.set_yticklabels(names, fontsize=9)
        ax.set_xlabel('Mean |SHAP Value|', fontsize=11)
        ax.set_title('Global Feature Importance (SHAP)', fontsize=13)
        plt.tight_layout()

        buf = io.BytesIO()
        fig.savefig(buf, format='png', dpi=100, bbox_inches='tight')
        plt.close(fig)
        buf.seek(0)
        return base64.b64encode(buf.read()).decode('utf-8')

    def _generate_beeswarm_data(self, shap_values, X, feature_names):
        """Build data for an interactive beeswarm plot (Plotly on frontend)."""
        mean_abs = np.abs(shap_values).mean(axis=0)
        sorted_idx = np.argsort(mean_abs)[::-1][:15]  # top 15

        data = []
        for idx in sorted_idx:
            data.append({
                'feature': feature_names[idx],
                'shap_values': shap_values[:, idx].round(4).tolist(),
                'feature_values': X[:, idx].round(4).tolist(),
                'mean_abs_shap': round(float(mean_abs[idx]), 4),
            })
        return data

    def _human_readable_impact(self, feature_name, weight, value):
        """Generate a human-readable sentence explaining a feature's impact."""
        direction = 'increases' if weight > 0 else 'decreases'
        strength = abs(weight)

        if strength > 0.3:
            intensity = 'strongly'
        elif strength > 0.1:
            intensity = 'moderately'
        else:
            intensity = 'slightly'

        # Clean up feature name for display
        display_name = feature_name.replace('_', ' ').title()

        return (
            f'{display_name} = {value:.2f} {intensity} {direction} '
            f'the prediction (impact: {weight:+.4f})'
        )

    def _save_explanation(self, registry, entity_type, entity_id,
                          method, result):
        """Persist an explanation result to the database."""
        if 'error' in result:
            return

        ExplanationResult.objects.create(
            model=registry,
            entity_type=entity_type,
            entity_id=entity_id,
            method=method,
            prediction_score=result.get('prediction', 0),
            base_value=result.get('base_value', 0),
            contributions=result.get('contributions', {}),
            top_features=result.get('top_features', []),
            waterfall_data=result.get('waterfall_data'),
        )
