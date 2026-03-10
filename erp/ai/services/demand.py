"""
Demand Forecasting Service

Uses Facebook Prophet for time-series forecasting of product demand
and dynamically updates ReorderRule safety_stock / reorder_point.
"""

import logging
import os
from decimal import Decimal

import pandas as pd
import numpy as np
from django.conf import settings
from django.db.models import Sum
from django.db.models.functions import TruncDate

from erp.models import StockMovement, ReorderRule
from erp.ai.models import MLModel, AIInsight
from .base import (
    get_or_create_registry, save_model_artefact, log_prediction,
)

logger = logging.getLogger('erp.ai.demand')

# Movement types that represent outbound demand
DEMAND_MOVEMENT_TYPES = [
    StockMovement.MovementType.SALES_ISSUE,
    StockMovement.MovementType.TRANSFER_OUT,
    StockMovement.MovementType.RETURN_OUT,
    StockMovement.MovementType.WRITE_OFF,
]


class DemandForecaster:
    """Per-product per-warehouse demand forecasting with Prophet."""

    def __init__(self, company):
        self.company = company
        self.min_samples = getattr(settings, 'ML_MIN_TRAINING_SAMPLES', 30)
        self.z_score = getattr(settings, 'ML_SAFETY_STOCK_Z', 1.65)
        # Suppress Prophet / cmdstanpy verbose stdout
        logging.getLogger('cmdstanpy').setLevel(logging.WARNING)
        logging.getLogger('prophet').setLevel(logging.WARNING)

    # ── Data preparation ────────────────────────────────────────────────

    def _get_demand_df(self, product, warehouse) -> pd.DataFrame:
        """Build a daily demand DataFrame from StockMovement."""
        qs = StockMovement.objects.filter(
            company=self.company,
            product=product,
            warehouse=warehouse,
            movement_type__in=DEMAND_MOVEMENT_TYPES,
        ).annotate(
            day=TruncDate('movement_date'),
        ).values('day').annotate(
            qty=Sum('quantity'),
        ).order_by('day')

        df = pd.DataFrame(list(qs))
        if df.empty:
            return df

        df = df.rename(columns={'day': 'ds', 'qty': 'y'})
        df['ds'] = pd.to_datetime(df['ds'])
        df['y'] = df['y'].astype(float).abs()  # ensure positive

        # Fill gaps with zero-demand days
        full_range = pd.date_range(df['ds'].min(), df['ds'].max(), freq='D')
        df = df.set_index('ds').reindex(full_range, fill_value=0).reset_index()
        df.columns = ['ds', 'y']
        return df

    # ── Forecasting ─────────────────────────────────────────────────────

    def forecast_product(self, product, warehouse, periods=30):
        """Generate a demand forecast for the next *periods* days.

        Returns a DataFrame with columns: ds, yhat, yhat_lower, yhat_upper
        or None when insufficient data.
        """
        df = self._get_demand_df(product, warehouse)
        if len(df) < self.min_samples:
            logger.info('Insufficient data for %s @ %s (%d < %d)',
                        product.sku, warehouse.code, len(df),
                        self.min_samples)
            return None

        try:
            from prophet import Prophet
        except ImportError:
            logger.error('prophet not installed – skipping demand forecast')
            return None

        m = Prophet(
            seasonality_mode='additive',
            daily_seasonality=False,
            weekly_seasonality=True,
            yearly_seasonality=False,
            changepoint_prior_scale=0.15,
            seasonality_prior_scale=5.0,
            n_changepoints=min(20, max(5, len(df) // 10)),
            interval_width=0.80,
        )
        # Add monthly seasonality for sub-annual patterns
        m.add_seasonality(name='monthly', period=30.5, fourier_order=3)
        with open(os.devnull, 'w') as devnull:
            import sys
            old_stdout = sys.stdout
            sys.stdout = devnull
            try:
                m.fit(df)
            finally:
                sys.stdout = old_stdout

        future = m.make_future_dataframe(periods=periods)
        forecast = m.predict(future)

        # Persist model reference
        registry = get_or_create_registry(
            self.company, MLModel.ModelType.DEMAND_FORECAST,
            f'Demand – {product.sku} @ {warehouse.code}',
        )
        registry.training_samples = len(df)
        registry.accuracy_score = self._evaluate(df, m)
        save_model_artefact(registry, m)

        result = forecast[['ds', 'yhat', 'yhat_lower', 'yhat_upper']].tail(periods)
        # Floor negative forecasts at 0 (demand can't be negative)
        result = result.copy()
        result['yhat'] = result['yhat'].clip(lower=0)
        result['yhat_lower'] = result['yhat_lower'].clip(lower=0)
        return result

    def _evaluate(self, df: pd.DataFrame, model) -> float:
        """Accuracy using cross-validation when data is large enough,
        otherwise falling back to a simple holdout split."""
        # Cross-validation for datasets with enough history
        if len(df) >= 90:
            try:
                from prophet.diagnostics import cross_validation, performance_metrics
                import sys
                import os
                with open(os.devnull, 'w') as devnull:
                    old_stdout = sys.stdout
                    sys.stdout = devnull
                    try:
                        cv = cross_validation(
                            model,
                            initial=f'{max(30, len(df) // 3)} days',
                            period=f'{max(7, len(df) // 15)} days',
                            horizon='14 days',
                        )
                    finally:
                        sys.stdout = old_stdout
                pm = performance_metrics(cv)
                mae = pm['mae'].mean()
                mean_demand = cv['y'].mean() or 1
                return max(0.0, min(1.0, 1 - mae / mean_demand))
            except Exception:
                pass  # fall through to simple holdout

        # Simple holdout evaluation
        split = int(len(df) * 0.8)
        if split < 5:
            return 0.0
        test = df.iloc[split:]
        pred = model.predict(test[['ds']])
        mae = np.mean(np.abs(pred['yhat'].values - test['y'].values))
        mean_demand = test['y'].mean() or 1
        return max(0.0, min(1.0, 1 - mae / mean_demand))

    # ── Reorder-point optimisation ──────────────────────────────────────

    def update_reorder_rule(self, rule: ReorderRule) -> dict | None:
        """Recalculate safety_stock & reorder_point from forecasted demand."""
        forecast = self.forecast_product(rule.product, rule.warehouse)
        if forecast is None:
            return None

        avg_daily = forecast['yhat'].clip(lower=0).mean()
        demand_std = ((forecast['yhat_upper'] - forecast['yhat_lower']) / 4).mean()
        lead_time = rule.lead_time_days or 1

        new_safety = self.z_score * demand_std * (lead_time ** 0.5)
        new_rop = (avg_daily * lead_time) + new_safety

        old_rop = float(rule.reorder_point)
        old_ss = float(rule.safety_stock)

        ReorderRule.objects.filter(pk=rule.pk).update(
            safety_stock=Decimal(str(round(new_safety, 2))),
            reorder_point=Decimal(str(round(new_rop, 2))),
        )

        # Log prediction
        registry = get_or_create_registry(
            self.company, MLModel.ModelType.DEMAND_FORECAST,
            f'Demand – {rule.product.sku}',
        )
        log_prediction(registry, 'ReorderRule', rule.pk, round(new_rop, 4), {
            'avg_daily_demand': round(avg_daily, 4),
            'demand_std': round(demand_std, 4),
            'lead_time_days': lead_time,
            'old_reorder_point': old_rop,
            'old_safety_stock': old_ss,
            'new_safety_stock': round(new_safety, 2),
        })

        logger.info('Updated ROP for %s@%s: %s → %s  SS: %s → %s',
                     rule.product.sku, rule.warehouse.code,
                     old_rop, round(new_rop, 2),
                     old_ss, round(new_safety, 2))

        return {
            'product': rule.product.sku,
            'warehouse': rule.warehouse.code,
            'old_reorder_point': old_rop,
            'new_reorder_point': round(new_rop, 2),
            'old_safety_stock': old_ss,
            'new_safety_stock': round(new_safety, 2),
            'avg_daily_demand': round(avg_daily, 4),
        }

    # ── Batch update ────────────────────────────────────────────────────

    def update_all_reorder_rules(self) -> list[dict]:
        """Re-optimise every active reorder rule for the company."""
        rules = ReorderRule.objects.filter(
            company=self.company, is_active=True,
        ).select_related('product', 'warehouse')

        results = []
        for rule in rules:
            try:
                result = self.update_reorder_rule(rule)
                if result:
                    results.append(result)
            except Exception as exc:
                logger.exception('Forecast failed for rule %s: %s', rule.pk, exc)

        # Create insight if significant changes detected
        big_changes = [r for r in results
                       if abs(r['new_reorder_point'] - r['old_reorder_point'])
                       / max(r['old_reorder_point'], 1) > 0.20]
        if big_changes:
            AIInsight.objects.create(
                company=self.company,
                category=AIInsight.Category.INVENTORY,
                severity=AIInsight.Severity.WARNING,
                title=f'{len(big_changes)} reorder points changed >20 %',
                description=(
                    'The demand forecasting model detected significant demand '
                    'shifts for the following products: '
                    + ', '.join(r['product'] for r in big_changes[:10])
                ),
                recommendation=(
                    'Review the updated reorder points in the Reorder Rules '
                    'list and confirm the new values.'
                ),
                action_url='/erp/reorder-rules/',
            )

        return results
