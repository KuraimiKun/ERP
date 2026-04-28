"""Regenerate the stale XAI / leakage figures using current models.

Outputs (overwrites old files in thesis/figures/):
  xai_shap_global_lead_scoring_beeswarm.png
  xai_shap_global_attrition_beeswarm.png
  xai_shap_global_late_payment_beeswarm.png
  xai_instance_waterfall_example.png       (late-payment, one row)
  xai_shap_vs_lime_side_by_side.png        (late-payment, same row)
  xai_model_auc_comparison.png             (real vs shuffled, 4 models)
  xai_leakage_summary_dashboard.png        (4-panel: shuffle gap, iteration,
                                            calibration, importance top-5)

Reads thesis/results/shuffle_test.csv + late_payment_iterations.csv produced
by capture_evidence.py. Run from repo root:

  & f:\\erpdjango\\venv\\Scripts\\python.exe thesis\\scripts\\regenerate_xai.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import django

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "erpproject.settings")
django.setup()

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import shap
from sklearn.base import clone
from sklearn.calibration import calibration_curve
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
from sklearn.preprocessing import StandardScaler

from tenants.models import TenantDatabase
from tenants.routers import TenantDatabaseContext, add_tenant_database
from erp.models.core import Company

from erp.ai.services.crm import LeadScorer
from erp.ai.services.finance import LatePaymentPredictor
from erp.ai.services.hr import AttritionPredictor

THESIS_DIR = REPO_ROOT / "thesis"
RESULTS_DIR = THESIS_DIR / "results"
FIGURES_DIR = THESIS_DIR / "figures"

TENANT_NAME = "erp_tenant_797cca0a123242c9"
COMPANY_ID = 1


def _weights(y_tr: np.ndarray) -> np.ndarray:
    r = float(y_tr.mean()) if len(y_tr) else 0.5
    return np.where(y_tr == 1, 1.0 / max(r, 0.01), 1.0 / max(1 - r, 0.01))


def _fit_lead(company):
    s = LeadScorer(company)
    df = s._build_dataset()
    X = df[s.FEATURE_COLS].values.astype(float)
    y = df["label"].values.astype(int)
    sc = StandardScaler().fit(X)
    Xs = sc.transform(X)
    clf = GradientBoostingClassifier(
        n_estimators=400, max_depth=4, learning_rate=0.05, subsample=0.8,
        min_samples_leaf=10, random_state=42, max_features="sqrt",
        validation_fraction=0.1, n_iter_no_change=30,
    ).fit(Xs, y, sample_weight=_weights(y))
    return clf, Xs, y, list(s.FEATURE_COLS)


def _fit_attrition(company):
    a = AttritionPredictor(company)
    df = a._build_dataset()
    X = df[a.FEATURE_COLS].fillna(0).values.astype(float)
    y = df["left"].values.astype(int)
    sc = StandardScaler().fit(X)
    Xs = sc.transform(X)
    clf = RandomForestClassifier(
        n_estimators=500, max_depth=10, min_samples_leaf=5,
        class_weight="balanced", random_state=42, max_features="sqrt",
    ).fit(Xs, y)
    return clf, Xs, y, list(a.FEATURE_COLS)


def _fit_late(company):
    lp = LatePaymentPredictor(company)
    df = lp._build_dataset()
    X = df[lp.FEATURE_COLS].values.astype(float)
    y = df["late"].values.astype(int)
    clf = GradientBoostingClassifier(
        n_estimators=500, max_depth=6, learning_rate=0.05, subsample=0.8,
        min_samples_leaf=15, random_state=42, max_features="sqrt",
        validation_fraction=0.1, n_iter_no_change=30, tol=1e-4,
    ).fit(X, y, sample_weight=_weights(y))
    return clf, X, y, list(lp.FEATURE_COLS)


def _shap_values_pos(clf, X_sample, feature_names):
    """Return SHAP values for positive class as 2-D ndarray, plus Explanation."""
    explainer = shap.TreeExplainer(clf)
    sv = explainer(X_sample)
    # sklearn classifier: sv may be Explanation with .values shape (n, f, 2) or (n, f)
    if sv.values.ndim == 3:
        vals = sv.values[..., 1]
        base = sv.base_values[..., 1] if sv.base_values.ndim == 2 else sv.base_values[1]
        sv = shap.Explanation(values=vals, base_values=base, data=sv.data,
                              feature_names=feature_names)
    else:
        sv = shap.Explanation(values=sv.values, base_values=sv.base_values,
                              data=sv.data, feature_names=feature_names)
    return sv


def beeswarm(clf, X, names, title, out_path, sample=400):
    rs = np.random.RandomState(42)
    idx = rs.choice(len(X), size=min(sample, len(X)), replace=False)
    Xs = X[idx]
    sv = _shap_values_pos(clf, Xs, names)
    plt.figure(figsize=(7, max(4, 0.28 * len(names) + 1)))
    shap.plots.beeswarm(sv, max_display=min(15, len(names)), show=False)
    plt.title(title, fontsize=11)
    plt.tight_layout()
    plt.savefig(out_path, dpi=160, bbox_inches="tight")
    plt.close("all")
    print(f"  wrote {out_path.name}")


def waterfall_example(clf, X, names, out_path, target_class_label="late=1"):
    rs = np.random.RandomState(7)
    # pick a row with high predicted prob to make it informative
    proba = clf.predict_proba(X)[:, 1]
    candidates = np.argsort(-proba)[:50]
    row = int(rs.choice(candidates))
    sv = _shap_values_pos(clf, X[row:row + 1], names)
    plt.figure(figsize=(7, 5))
    shap.plots.waterfall(sv[0], max_display=12, show=False)
    plt.title(f"Local explanation – {target_class_label} (p={proba[row]:.2f})",
              fontsize=11)
    plt.tight_layout()
    plt.savefig(out_path, dpi=160, bbox_inches="tight")
    plt.close("all")
    print(f"  wrote {out_path.name}  (row={row}, p={proba[row]:.3f})")
    return row, proba[row]


def shap_vs_lime(clf, X, y, names, row, p, out_path):
    from lime.lime_tabular import LimeTabularExplainer

    # SHAP local
    sv = _shap_values_pos(clf, X[row:row + 1], names)
    shap_vals = sv.values[0]

    # LIME local
    lime_exp = LimeTabularExplainer(
        training_data=X, feature_names=names, class_names=["on_time", "late"],
        discretize_continuous=True, random_state=42,
    )
    exp = lime_exp.explain_instance(
        X[row], clf.predict_proba, num_features=10, num_samples=2000,
    )
    lime_pairs = exp.as_list(label=1)  # [(feat_desc, weight), ...]

    # Side-by-side bars
    fig, axes = plt.subplots(1, 2, figsize=(11, 5.5))
    # SHAP top 10 by |value|
    order = np.argsort(np.abs(shap_vals))[::-1][:10][::-1]
    s_names = [names[i] for i in order]
    s_vals = shap_vals[order]
    colors_s = ["#d62728" if v > 0 else "#1f77b4" for v in s_vals]
    axes[0].barh(range(len(s_names)), s_vals, color=colors_s)
    axes[0].set_yticks(range(len(s_names)))
    axes[0].set_yticklabels(s_names, fontsize=9)
    axes[0].axvline(0, color="k", linewidth=0.5)
    axes[0].set_title(f"SHAP (TreeExplainer) – p={p:.2f}", fontsize=11)
    axes[0].set_xlabel("contribution to log-odds")

    # LIME bars (already sorted)
    l_names = [d for d, _ in lime_pairs][::-1]
    l_vals = [w for _, w in lime_pairs][::-1]
    colors_l = ["#d62728" if v > 0 else "#1f77b4" for v in l_vals]
    axes[1].barh(range(len(l_names)), l_vals, color=colors_l)
    axes[1].set_yticks(range(len(l_names)))
    axes[1].set_yticklabels(l_names, fontsize=8)
    axes[1].axvline(0, color="k", linewidth=0.5)
    axes[1].set_title("LIME (tabular, 2000 samples)", fontsize=11)
    axes[1].set_xlabel("contribution to P(late=1)")

    fig.suptitle("SHAP vs LIME – same late-payment instance", fontsize=12)
    fig.tight_layout()
    fig.savefig(out_path, dpi=160, bbox_inches="tight")
    plt.close(fig)
    print(f"  wrote {out_path.name}")


def auc_comparison(out_path):
    df = pd.read_csv(RESULTS_DIR / "shuffle_test.csv")
    # Append demand row (Prophet has no AUC – use score from main run)
    # Show only the 3 classifiers (AUC is meaningful) – demand handled separately.
    fig, ax = plt.subplots(figsize=(7, 4))
    x = np.arange(len(df))
    w = 0.36
    ax.bar(x - w / 2, df["real_auc_oof"], w, label="real AUC (5-fold OOF)",
           color="#2ca02c")
    ax.bar(x + w / 2, df["shuffled_auc"].fillna(0), w,
           label="shuffled-label AUC", color="#888888")
    ax.axhline(0.5, color="k", linestyle="--", linewidth=0.8, label="chance")
    ax.set_xticks(x)
    ax.set_xticklabels(df["model"], rotation=0)
    ax.set_ylabel("AUC")
    ax.set_ylim(0, 1.05)
    ax.set_title("Real vs shuffled-label AUC – leakage gate")
    for i, (r, s) in enumerate(zip(df["real_auc_oof"], df["shuffled_auc"].fillna(0))):
        ax.text(i - w / 2, r + 0.02, f"{r:.3f}", ha="center", fontsize=8)
        ax.text(i + w / 2, s + 0.02, f"{s:.3f}", ha="center", fontsize=8)
    ax.legend(loc="lower right", fontsize=9)
    fig.tight_layout()
    fig.savefig(out_path, dpi=160)
    plt.close(fig)
    print(f"  wrote {out_path.name}")


def leakage_dashboard(clf_lp, X_lp, y_lp, names_lp, out_path):
    shuffle = pd.read_csv(RESULTS_DIR / "shuffle_test.csv")
    iters = pd.read_csv(RESULTS_DIR / "late_payment_iterations.csv")

    fig, axes = plt.subplots(2, 2, figsize=(11, 8))

    # (a) Shuffle gap per model
    ax = axes[0, 0]
    x = np.arange(len(shuffle))
    gap = shuffle["real_auc_oof"] - shuffle["shuffled_auc"].fillna(0.5)
    bars = ax.bar(x, gap, color=["#2ca02c" if g > 0.05 else "#d62728" for g in gap])
    ax.set_xticks(x)
    ax.set_xticklabels(shuffle["model"], rotation=15, fontsize=9)
    ax.set_ylabel("real − shuffled AUC")
    ax.set_title("(a) Leakage gap per model")
    ax.axhline(0.05, color="k", linestyle="--", linewidth=0.8)
    for i, g in enumerate(gap):
        ax.text(i, g + 0.01, f"{g:.3f}", ha="center", fontsize=8)

    # (b) Late-payment iteration history
    ax = axes[0, 1]
    ax.plot(iters["iteration"], iters["auc_holdout"], "o-", label="real AUC",
            color="#1f77b4")
    ax.plot(iters["iteration"], iters["shuffled_auc"].fillna(np.nan), "s--",
            label="shuffled AUC", color="#888888")
    ax.axhline(0.5, color="k", linestyle=":", linewidth=0.8)
    ax.set_xticks(iters["iteration"])
    ax.set_ylim(0.4, 1.0)
    ax.set_xlabel("iteration")
    ax.set_ylabel("AUC")
    ax.set_title("(b) Late-payment label redesign")
    ax.legend(fontsize=9)
    for _, r in iters.iterrows():
        ax.annotate(r["label_definition"][:32] + "…", (r["iteration"], r["auc_holdout"]),
                    xytext=(5, 5), textcoords="offset points", fontsize=7)

    # (c) Calibration of late-payment classifier (refit OOF would be better;
    # we use 5-fold here for speed.
    from sklearn.model_selection import StratifiedKFold
    kf = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    oof = np.zeros(len(y_lp))
    for tr, te in kf.split(X_lp, y_lp):
        c = clone(clf_lp)
        c.fit(X_lp[tr], y_lp[tr], sample_weight=_weights(y_lp[tr]))
        oof[te] = c.predict_proba(X_lp[te])[:, 1]
    frac, mean_pred = calibration_curve(y_lp, oof, n_bins=10, strategy="quantile")
    ax = axes[1, 0]
    ax.plot([0, 1], [0, 1], "k--", linewidth=0.8, label="perfect")
    ax.plot(mean_pred, frac, "o-", color="#1f77b4", label="late-payment")
    ax.set_xlabel("mean predicted probability")
    ax.set_ylabel("fraction of positives")
    ax.set_title("(c) Late-payment calibration (OOF)")
    ax.legend(fontsize=9)
    ax.grid(alpha=0.3)

    # (d) Top-5 importances late-payment
    imp = clf_lp.feature_importances_
    order = np.argsort(imp)[::-1][:8][::-1]
    ax = axes[1, 1]
    ax.barh(range(len(order)), imp[order], color="#1f77b4")
    ax.set_yticks(range(len(order)))
    ax.set_yticklabels([names_lp[i] for i in order], fontsize=9)
    ax.set_xlabel("importance")
    ax.set_title("(d) Top late-payment features")

    fig.suptitle("Leakage detection & late-payment redesign – evidence dashboard",
                 fontsize=13)
    fig.tight_layout(rect=[0, 0, 1, 0.96])
    fig.savefig(out_path, dpi=160)
    plt.close(fig)
    print(f"  wrote {out_path.name}")


def main():
    td = TenantDatabase.objects.get(name=TENANT_NAME)
    db = add_tenant_database(td)
    company = Company.objects.using(db).get(pk=COMPANY_ID)

    with TenantDatabaseContext(db):
        print("[1/3] Fitting models on full data ...")
        clf_l, X_l, y_l, names_l = _fit_lead(company)
        print(f"  lead: n={len(y_l)} pos={y_l.mean():.3f}")
        clf_a, X_a, y_a, names_a = _fit_attrition(company)
        print(f"  attrition: n={len(y_a)} pos={y_a.mean():.3f}")
        clf_p, X_p, y_p, names_p = _fit_late(company)
        print(f"  late: n={len(y_p)} pos={y_p.mean():.3f}")

        print("\n[2/3] SHAP beeswarms ...")
        beeswarm(clf_l, X_l, names_l, "SHAP – Lead scoring (global)",
                 FIGURES_DIR / "xai_shap_global_lead_scoring_beeswarm.png")
        beeswarm(clf_a, X_a, names_a, "SHAP – Attrition (global)",
                 FIGURES_DIR / "xai_shap_global_attrition_beeswarm.png")
        beeswarm(clf_p, X_p, names_p, "SHAP – Late payment (global)",
                 FIGURES_DIR / "xai_shap_global_late_payment_beeswarm.png")

        print("\n[3/3] Waterfall + SHAP-vs-LIME + AUC + dashboard ...")
        row, p = waterfall_example(clf_p, X_p, names_p,
                                   FIGURES_DIR / "xai_instance_waterfall_example.png")
        shap_vs_lime(clf_p, X_p, y_p, names_p, row, p,
                     FIGURES_DIR / "xai_shap_vs_lime_side_by_side.png")
        auc_comparison(FIGURES_DIR / "xai_model_auc_comparison.png")
        leakage_dashboard(clf_p, X_p, y_p, names_p,
                          FIGURES_DIR / "xai_leakage_summary_dashboard.png")

    print("\nDone.")


if __name__ == "__main__":
    main()
