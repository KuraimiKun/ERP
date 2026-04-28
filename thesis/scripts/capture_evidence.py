"""Capture evidence artefacts for the thesis article.

Produces (relative to f:/erpdjango/thesis/):
  results/shuffle_test.csv             -- real vs shuffled-label AUC, all 4 models
  results/late_payment_iterations.csv  -- iteration history (manual, hand-typed)
  results/feature_importance_*.csv     -- per-classifier importances
  figures/cm_<model>.png               -- confusion matrices (3 classifiers)
  figures/calibration_<model>.png      -- calibration curves (3 classifiers)
  figures/feature_importance_late_payment.png
  figures/prophet_backtest_fast.png
  figures/prophet_backtest_slow.png

Run from repo root with the venv python:
  & f:\\erpdjango\\venv\\Scripts\\python.exe thesis\\scripts\\capture_evidence.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import django

# ─── Django setup ───────────────────────────────────────────────────────────
REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "erpproject.settings")
django.setup()

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.calibration import calibration_curve
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
from sklearn.metrics import (
    confusion_matrix,
    roc_auc_score,
)
from sklearn.model_selection import StratifiedKFold
from sklearn.preprocessing import StandardScaler

from tenants.models import TenantDatabase
from tenants.routers import add_tenant_database, TenantDatabaseContext
from erp.models.core import Company

from erp.ai.services.crm import LeadScorer
from erp.ai.services.finance import LatePaymentPredictor
from erp.ai.services.hr import AttritionPredictor
from erp.ai.services.demand import DemandForecaster
from erp.ai.services.base import shuffle_label_auc

# ─── Output paths ──────────────────────────────────────────────────────────
THESIS_DIR = REPO_ROOT / "thesis"
RESULTS_DIR = THESIS_DIR / "results"
FIGURES_DIR = THESIS_DIR / "figures"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)
FIGURES_DIR.mkdir(parents=True, exist_ok=True)

# ─── Tenant config ─────────────────────────────────────────────────────────
TENANT_NAME = "erp_tenant_797cca0a123242c9"
COMPANY_ID = 1


def _weights(y_tr: np.ndarray) -> np.ndarray:
    r = float(y_tr.mean()) if len(y_tr) else 0.5
    return np.where(y_tr == 1, 1.0 / max(r, 0.01), 1.0 / max(1 - r, 0.01))


def _oof_predictions(estimator, X, y, *, scale=False, weights=False, n_splits=5, seed=42):
    """Return out-of-fold predicted probabilities (length == len(y))."""
    kf = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=seed)
    oof = np.zeros(len(y), dtype=float)
    for tr, te in kf.split(X, y):
        Xtr, Xte = X[tr], X[te]
        if scale:
            sc = StandardScaler().fit(Xtr)
            Xtr = sc.transform(Xtr)
            Xte = sc.transform(Xte)
        est = clone(estimator)
        fit_kw = {}
        if weights:
            fit_kw["sample_weight"] = _weights(y[tr])
        try:
            est.fit(Xtr, y[tr], **fit_kw)
        except TypeError:
            est.fit(Xtr, y[tr])
        oof[te] = est.predict_proba(Xte)[:, 1]
    return oof


def _plot_confusion(cm: np.ndarray, title: str, path: Path):
    fig, ax = plt.subplots(figsize=(3.4, 3.0))
    im = ax.imshow(cm, cmap="Blues")
    ax.set_xticks([0, 1])
    ax.set_yticks([0, 1])
    ax.set_xticklabels(["Pred 0", "Pred 1"])
    ax.set_yticklabels(["True 0", "True 1"])
    for i in range(2):
        for j in range(2):
            ax.text(j, i, str(cm[i, j]), ha="center", va="center",
                    color="white" if cm[i, j] > cm.max() / 2 else "black")
    ax.set_title(title)
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def _plot_calibration(y_true, y_prob, title: str, path: Path):
    frac_pos, mean_pred = calibration_curve(y_true, y_prob, n_bins=10, strategy="quantile")
    fig, ax = plt.subplots(figsize=(3.6, 3.4))
    ax.plot([0, 1], [0, 1], "k--", linewidth=1, label="perfect")
    ax.plot(mean_pred, frac_pos, "o-", label="model")
    ax.set_xlabel("Mean predicted probability")
    ax.set_ylabel("Fraction of positives")
    ax.set_title(title)
    ax.legend(loc="best", fontsize=8)
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def _plot_feature_importance(names, importances, title: str, path: Path, top=15):
    order = np.argsort(importances)[::-1][:top]
    names = [names[i] for i in order]
    vals = [importances[i] for i in order]
    fig, ax = plt.subplots(figsize=(5.0, max(2.5, 0.28 * len(names) + 1)))
    ax.barh(range(len(names))[::-1], vals)
    ax.set_yticks(range(len(names))[::-1])
    ax.set_yticklabels(names, fontsize=8)
    ax.set_xlabel("Importance")
    ax.set_title(title)
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


# ─── Main ──────────────────────────────────────────────────────────────────
def main():
    td = TenantDatabase.objects.get(name=TENANT_NAME)
    db = add_tenant_database(td)
    company = Company.objects.using(db).get(pk=COMPANY_ID)

    shuffle_rows = []
    importance_rows_global = []

    with TenantDatabaseContext(db):
        # ──────── Lead scoring ────────
        print("\n[1/4] Lead scoring")
        scorer = LeadScorer(company)
        df = scorer._build_dataset()
        X = df[scorer.FEATURE_COLS].values
        y = df["label"].values
        clf = GradientBoostingClassifier(
            n_estimators=400, max_depth=4, learning_rate=0.05, subsample=0.8,
            min_samples_leaf=10, random_state=42, max_features="sqrt",
            validation_fraction=0.1, n_iter_no_change=30,
        )
        sc = StandardScaler()
        Xs = sc.fit_transform(X)
        oof = _oof_predictions(clf, Xs, y, scale=False, weights=True)
        real_auc = roc_auc_score(y, oof)
        sh = shuffle_label_auc(clf, Xs, y, n_repeats=5, sample_weight_fn=_weights)
        shuffle_rows.append({"model": "lead_scoring", "real_auc_oof": round(real_auc, 4),
                             "shuffled_auc": round(sh, 4) if sh else None,
                             "samples": int(len(y)), "positive_rate": round(float(y.mean()), 4)})
        cm = confusion_matrix(y, (oof > 0.5).astype(int))
        _plot_confusion(cm, "Lead scoring (OOF, threshold=0.5)", FIGURES_DIR / "cm_lead_scoring.png")
        _plot_calibration(y, oof, "Lead scoring calibration", FIGURES_DIR / "calibration_lead_scoring.png")
        # importance from refit on full data
        clf_full = clone(clf).fit(Xs, y, sample_weight=_weights(y))
        imp = clf_full.feature_importances_
        pd.DataFrame({"feature": scorer.FEATURE_COLS, "importance": imp.round(4)}) \
            .sort_values("importance", ascending=False) \
            .to_csv(RESULTS_DIR / "feature_importance_lead_scoring.csv", index=False)
        _plot_feature_importance(scorer.FEATURE_COLS, imp, "Lead scoring – feature importance",
                                 FIGURES_DIR / "feature_importance_lead_scoring.png")

        # ──────── Attrition ────────
        print("\n[2/4] Attrition")
        att = AttritionPredictor(company)
        df = att._build_dataset()
        X = df[att.FEATURE_COLS].fillna(0).values
        y = df["left"].values
        sc = StandardScaler()
        Xs = sc.fit_transform(X)
        clf = RandomForestClassifier(
            n_estimators=500, max_depth=10, min_samples_leaf=5,
            class_weight="balanced", random_state=42, max_features="sqrt",
        )
        oof = _oof_predictions(clf, Xs, y, scale=False, weights=False)
        real_auc = roc_auc_score(y, oof)
        sh = shuffle_label_auc(clf, Xs, y, n_repeats=5)
        shuffle_rows.append({"model": "attrition", "real_auc_oof": round(real_auc, 4),
                             "shuffled_auc": round(sh, 4) if sh else None,
                             "samples": int(len(y)), "positive_rate": round(float(y.mean()), 4)})
        cm = confusion_matrix(y, (oof > 0.5).astype(int))
        _plot_confusion(cm, "Attrition (OOF, threshold=0.5)", FIGURES_DIR / "cm_attrition.png")
        _plot_calibration(y, oof, "Attrition calibration", FIGURES_DIR / "calibration_attrition.png")
        clf_full = clone(clf).fit(Xs, y)
        imp = clf_full.feature_importances_
        pd.DataFrame({"feature": att.FEATURE_COLS, "importance": imp.round(4)}) \
            .sort_values("importance", ascending=False) \
            .to_csv(RESULTS_DIR / "feature_importance_attrition.csv", index=False)
        _plot_feature_importance(att.FEATURE_COLS, imp, "Attrition – feature importance",
                                 FIGURES_DIR / "feature_importance_attrition.png")

        # ──────── Late payment ────────
        print("\n[3/4] Late payment")
        lp = LatePaymentPredictor(company)
        df = lp._build_dataset()
        X = df[lp.FEATURE_COLS].values
        y = df["late"].values
        clf = GradientBoostingClassifier(
            n_estimators=500, max_depth=6, learning_rate=0.05, subsample=0.8,
            min_samples_leaf=15, random_state=42, max_features="sqrt",
            validation_fraction=0.1, n_iter_no_change=30, tol=1e-4,
        )
        oof = _oof_predictions(clf, X, y, scale=False, weights=True)
        real_auc = roc_auc_score(y, oof)
        sh = shuffle_label_auc(clf, X, y, n_repeats=5, sample_weight_fn=_weights)
        shuffle_rows.append({"model": "late_payment", "real_auc_oof": round(real_auc, 4),
                             "shuffled_auc": round(sh, 4) if sh else None,
                             "samples": int(len(y)), "positive_rate": round(float(y.mean()), 4)})
        cm = confusion_matrix(y, (oof > 0.5).astype(int))
        _plot_confusion(cm, "Late payment (OOF, threshold=0.5)", FIGURES_DIR / "cm_late_payment.png")
        _plot_calibration(y, oof, "Late payment calibration", FIGURES_DIR / "calibration_late_payment.png")
        clf_full = clone(clf).fit(X, y, sample_weight=_weights(y))
        imp = clf_full.feature_importances_
        pd.DataFrame({"feature": lp.FEATURE_COLS, "importance": imp.round(4)}) \
            .sort_values("importance", ascending=False) \
            .to_csv(RESULTS_DIR / "feature_importance_late_payment.csv", index=False)
        _plot_feature_importance(lp.FEATURE_COLS, imp,
                                 "Late payment – feature importance",
                                 FIGURES_DIR / "feature_importance_late_payment.png")

        # ──────── Demand: backtest one fast + one slow SKU ────────
        print("\n[4/4] Demand (Prophet backtest)")
        from erp.models.services import Product
        from erp.models.inventory import Warehouse, StockMovement
        from django.db.models import Count

        # Pick the most active and one of the least-active SKUs in WH-MAIN
        wh = Warehouse.objects.using(db).filter(company=company, code="WH-MAIN").first()
        if wh is None:
            wh = Warehouse.objects.using(db).filter(company=company, is_active=True).first()

        movement_counts = (
            StockMovement.objects.using(db)
            .filter(company=company, warehouse=wh, movement_type__in=["sale", "out", "transfer_out"])
            .values("product_id")
            .annotate(n=Count("id"))
            .order_by("-n")
        )
        rows = list(movement_counts)
        if rows:
            fast_id = rows[0]["product_id"]
            # slow: pick one with at least 30 nonzero days but few movements
            slow_candidates = [r for r in rows if r["n"] >= 30]
            slow_id = (slow_candidates[-1]["product_id"]
                       if slow_candidates else rows[-1]["product_id"])
        else:
            fast_id = slow_id = None

        forecaster = DemandForecaster(company)

        def _backtest_plot(product_id, label, out_path):
            if product_id is None:
                print(f"  skip {label}: no product")
                return
            product = Product.objects.using(db).get(pk=product_id)
            df_demand = forecaster._get_demand_df(product, wh)
            nonzero = int((df_demand["y"] > 0).sum())
            if nonzero < forecaster.min_samples:
                print(f"  skip {label} ({product.sku}): only {nonzero} nonzero days")
                return
            try:
                from prophet import Prophet
            except ImportError:
                print("  prophet not installed; skipping demand plot")
                return
            # Time-split: train on first 80%, predict last 20%
            split = int(len(df_demand) * 0.8)
            train, test = df_demand.iloc[:split], df_demand.iloc[split:]
            m = Prophet(
                seasonality_mode="additive",
                daily_seasonality=False,
                weekly_seasonality=True,
                yearly_seasonality=False,
                changepoint_prior_scale=0.15,
                seasonality_prior_scale=5.0,
                n_changepoints=min(20, max(5, len(train) // 10)),
                interval_width=0.80,
            )
            m.add_seasonality(name="monthly", period=30.5, fourier_order=3)
            with open(os.devnull, "w") as devnull:
                old = sys.stdout
                sys.stdout = devnull
                try:
                    m.fit(train)
                finally:
                    sys.stdout = old
            future = m.make_future_dataframe(periods=len(test))
            fc = m.predict(future)

            fig, ax = plt.subplots(figsize=(7, 3.2))
            ax.plot(df_demand["ds"], df_demand["y"], "k.", markersize=3, alpha=0.6, label="actual")
            ax.plot(fc["ds"], fc["yhat"].clip(lower=0), "b-", linewidth=1, label="forecast")
            ax.fill_between(fc["ds"], fc["yhat_lower"].clip(lower=0), fc["yhat_upper"].clip(lower=0),
                            color="blue", alpha=0.15, label="80% interval")
            split_date = train["ds"].iloc[-1]
            ax.axvline(split_date, color="red", linestyle="--", linewidth=1, label="train/test split")
            mae = float(np.mean(np.abs(fc["yhat"].iloc[split:].values - test["y"].values)))
            mean_demand = float(test["y"].mean()) or 1.0
            score = max(0.0, 1 - mae / mean_demand)
            ax.set_title(f"Prophet backtest – {label} SKU {product.sku} "
                         f"(MAE={mae:.2f}, score={score:.3f})")
            ax.set_xlabel("date")
            ax.set_ylabel("demand (units/day)")
            ax.legend(loc="upper left", fontsize=8)
            fig.autofmt_xdate()
            fig.tight_layout()
            fig.savefig(out_path, dpi=160)
            plt.close(fig)
            print(f"  wrote {out_path.name} (MAE={mae:.2f}, score={score:.3f})")

        _backtest_plot(fast_id, "fast", FIGURES_DIR / "prophet_backtest_fast.png")
        _backtest_plot(slow_id, "slow", FIGURES_DIR / "prophet_backtest_slow.png")

    # ──────── Save shuffle table ────────
    shuffle_df = pd.DataFrame(shuffle_rows)
    shuffle_df.to_csv(RESULTS_DIR / "shuffle_test.csv", index=False)
    print("\nShuffle test summary:")
    print(shuffle_df.to_string(index=False))

    # ──────── Late-payment iteration history (hand-typed from session record) ────────
    iters = pd.DataFrame([
        {"iteration": 1, "label_definition": "delivery delay (estimated vs actual)",
         "auc_holdout": 0.63, "shuffled_auc": None,
         "note": "wrong concept; model relied on logistics features"},
        {"iteration": 2, "label_definition": "hidden customer payer profile, unique cust IDs",
         "auc_holdout": 0.50, "shuffled_auc": 0.50,
         "note": "correct label but no aggregable history"},
        {"iteration": 3, "label_definition": "payer profile + 3000-bucket customer hashing",
         "auc_holdout": 0.80, "shuffled_auc": 0.50,
         "note": "customer-level features become identifiable"},
    ])
    iters.to_csv(RESULTS_DIR / "late_payment_iterations.csv", index=False)
    print("\nDone. Artefacts under:")
    print(f"  {RESULTS_DIR}")
    print(f"  {FIGURES_DIR}")


if __name__ == "__main__":
    main()
