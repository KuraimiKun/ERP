"""Cross-task replication of the sparsity experiment on the IBM HR Employee
Attrition dataset.

Pipeline mirrors ``sparsity_simulator.py`` (Late Payment / Olist) so results
are directly comparable: stratified slicing into 5 simulated tenants, identical
Gradient Boosting hyperparameters, identical SHAP/LIME/Spearman/Jaccard
stability metrics, identical figure layouts.

Dataset
-------
``datasets/WA_Fn-UseC_-HR-Employee-Attrition.csv`` (Kaggle IBM HR Analytics
Employee Attrition & Performance, 1{,}470 rows, ``Attrition`` binary target).

Run
---
    f:/erpdjango/venv/Scripts/python.exe thesis/scripts/hr_attrition_simulator.py
"""
from __future__ import annotations

import json
import warnings
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import shap
import seaborn as sns
from lime.lime_tabular import LimeTabularExplainer
from scipy.stats import entropy, spearmanr
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.metrics import f1_score, roc_auc_score
from sklearn.model_selection import train_test_split

warnings.filterwarnings("ignore")

SEED = 42
np.random.seed(SEED)

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = REPO_ROOT / "datasets"
OUT_DIR = REPO_ROOT / "thesis" / "results" / "hr_attrition_experiment"
FIG_DIR = OUT_DIR / "figures"
OUT_DIR.mkdir(parents=True, exist_ok=True)
FIG_DIR.mkdir(parents=True, exist_ok=True)

# Tier sizes constrained by the dataset's total volume (1,470 rows). The
# largest tenant therefore receives ~1{,}000 rows and the cold-start tenant
# receives 30 rows; the log-scaled volume axis is preserved.
TENANTS = [
    ("A_data_rich", 1_000),
    ("B_medium", 500),
    ("C_sparse", 200),
    ("D_very_sparse", 100),
    ("E_cold_start", 30),
]

TARGET = "attrition"

# Columns that are constants in this corpus or pure identifiers; excluded from
# the feature matrix because they carry zero information about the target.
DROP_COLS = ["EmployeeCount", "StandardHours", "Over18", "EmployeeNumber"]

CATEGORICAL_COLS = [
    "BusinessTravel",
    "Department",
    "EducationField",
    "Gender",
    "JobRole",
    "MaritalStatus",
    "OverTime",
]


def build_hr_dataset() -> tuple[pd.DataFrame, list[str]]:
    """Load IBM HR Attrition and one-hot encode categorical columns.

    Every feature in this corpus is a static HR-snapshot attribute observable
    at scoring time (no future event leaks into the feature matrix), so the
    leakage-avoidance concern that drove the Late Payment redesign does not
    apply here.
    """
    df = pd.read_csv(DATA_DIR / "WA_Fn-UseC_-HR-Employee-Attrition.csv")
    df[TARGET] = (df["Attrition"] == "Yes").astype(int)
    df = df.drop(columns=["Attrition"] + DROP_COLS)
    df = pd.get_dummies(df, columns=CATEGORICAL_COLS, drop_first=True)
    feature_cols = [c for c in df.columns if c != TARGET]
    # Cast booleans from get_dummies to int for numeric consistency
    for c in feature_cols:
        if df[c].dtype == bool:
            df[c] = df[c].astype(int)
    df = df.replace([np.inf, -np.inf], np.nan).dropna()
    return df.reset_index(drop=True), feature_cols


def stratified_slice(df: pd.DataFrame, n: int, seed: int) -> pd.DataFrame:
    if n >= len(df):
        return df.sample(frac=1.0, random_state=seed).reset_index(drop=True)
    pos = df[df[TARGET] == 1]
    neg = df[df[TARGET] == 0]
    ratio = len(pos) / len(df)
    n_pos = max(1, int(round(n * ratio)))
    n_neg = max(1, n - n_pos)
    n_pos = min(n_pos, len(pos))
    n_neg = min(n_neg, len(neg))
    return (
        pd.concat(
            [
                pos.sample(n=n_pos, random_state=seed),
                neg.sample(n=n_neg, random_state=seed),
            ]
        )
        .sample(frac=1.0, random_state=seed)
        .reset_index(drop=True)
    )


def train_one(slice_df: pd.DataFrame, feature_cols: list[str], seed: int = SEED):
    X = slice_df[feature_cols].values.astype(float)
    y = slice_df[TARGET].values.astype(int)
    stratify = y if (y.sum() >= 2 and (len(y) - y.sum()) >= 2) else None
    X_tr, X_te, y_tr, y_te = train_test_split(
        X, y, test_size=0.2, random_state=seed, stratify=stratify
    )
    model = GradientBoostingClassifier(
        n_estimators=200,
        max_depth=3,
        learning_rate=0.05,
        random_state=seed,
    )
    model.fit(X_tr, y_tr)
    proba = model.predict_proba(X_te)[:, 1]
    pred = (proba >= 0.5).astype(int)
    try:
        auc = roc_auc_score(y_te, proba)
    except ValueError:
        auc = float("nan")
    f1 = f1_score(y_te, pred, zero_division=0)
    return model, X_tr, X_te, y_tr, y_te, auc, f1


def global_shap(model, X_te: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    explainer = shap.TreeExplainer(model)
    vals = explainer.shap_values(X_te)
    if isinstance(vals, list):
        vals = vals[1] if len(vals) > 1 else vals[0]
    vals = np.asarray(vals)
    return np.abs(vals).mean(axis=0), vals


def global_lime(
    model,
    X_tr: np.ndarray,
    X_te: np.ndarray,
    feature_names: list[str],
    n_samples: int = 100,
    seed: int = SEED,
) -> np.ndarray:
    n = min(n_samples, len(X_te))
    rng = np.random.RandomState(seed)
    idx = rng.choice(len(X_te), size=n, replace=False)
    explainer = LimeTabularExplainer(
        X_tr,
        feature_names=feature_names,
        class_names=["stay", "leave"],
        discretize_continuous=True,
        random_state=seed,
    )
    agg = np.zeros(len(feature_names))
    for i in idx:
        exp = explainer.explain_instance(
            X_te[i],
            model.predict_proba,
            num_features=len(feature_names),
            num_samples=500,
        )
        for feat_idx, w in exp.as_map()[1]:
            agg[feat_idx] += abs(w)
    return agg / n


def lime_jaccard_stability(
    model,
    X_tr: np.ndarray,
    X_test_instances: np.ndarray,
    feature_names: list[str],
    n_repeats: int = 5,
    top_k: int = 5,
    seed_base: int = 100,
) -> float:
    jaccards: list[float] = []
    for x in X_test_instances:
        feature_sets: list[set[int]] = []
        for r in range(n_repeats):
            explainer = LimeTabularExplainer(
                X_tr,
                feature_names=feature_names,
                class_names=["stay", "leave"],
                discretize_continuous=True,
                random_state=seed_base + r,
            )
            exp = explainer.explain_instance(
                x,
                model.predict_proba,
                num_features=top_k,
                num_samples=500,
            )
            top = {fi for fi, _ in exp.as_map()[1][:top_k]}
            feature_sets.append(top)
        pair_scores = []
        for i in range(len(feature_sets)):
            for j in range(i + 1, len(feature_sets)):
                a, b = feature_sets[i], feature_sets[j]
                u = a | b
                pair_scores.append(len(a & b) / len(u) if u else 1.0)
        jaccards.append(float(np.mean(pair_scores)) if pair_scores else 1.0)
    return float(np.mean(jaccards)) if jaccards else float("nan")


def shap_entropy(shap_matrix: np.ndarray) -> float:
    abs_m = np.abs(shap_matrix)
    row_sums = abs_m.sum(axis=1, keepdims=True)
    row_sums[row_sums == 0] = 1.0
    probs = abs_m / row_sums
    ents = np.apply_along_axis(lambda p: entropy(p + 1e-12), 1, probs)
    return float(np.mean(ents))


def main() -> None:
    print("[1/5] Loading HR Attrition dataset ...")
    full, feature_cols = build_hr_dataset()
    pos_rate = full[TARGET].mean()
    print(f"      rows={len(full):,}  features={len(feature_cols)}  pos_rate={pos_rate:.3f}")

    print("[2/5] Training reference model on FULL dataset ...")
    ref_model, _, ref_Xte, _, _, ref_auc, ref_f1 = train_one(full, feature_cols)
    ref_shap_mean, _ = global_shap(ref_model, ref_Xte[: min(500, len(ref_Xte))])
    ref_ranking = pd.Series(ref_shap_mean, index=feature_cols).sort_values(ascending=False)
    top5 = ref_ranking.head(5)
    pct = (top5 / top5.sum() * 100).round(1)
    heuristic = {
        "model": "hr_attrition_gradient_boosting",
        "trained_on_full_rows": int(len(full)),
        "reference_auc": round(float(ref_auc), 4),
        "reference_f1": round(float(ref_f1), 4),
        "top_features": [
            {
                "feature": feat,
                "mean_abs_shap": float(ref_ranking[feat]),
                "relative_contribution_pct": float(pct[feat]),
            }
            for feat in top5.index
        ],
    }
    (OUT_DIR / "cold_start_heuristic.json").write_text(json.dumps(heuristic, indent=2))
    print(f"      reference AUC={ref_auc:.3f} F1={ref_f1:.3f}")

    print("[3/5] Slicing tenants ...")
    tenant_data: dict[str, pd.DataFrame] = {}
    for name, n in TENANTS:
        sl = stratified_slice(full, n, SEED)
        sl.to_csv(OUT_DIR / f"tenant_{name}_n{n}.csv", index=False)
        tenant_data[name] = sl
        print(f"      tenant {name}: rows={len(sl):,} pos_rate={sl[TARGET].mean():.3f}")

    shared_pool = stratified_slice(full, min(500, len(full)), SEED + 1)
    shared_eval = shared_pool[feature_cols].values[:5].astype(float)

    print("[4/5] Per-tenant training + SHAP/LIME/stability ...")
    results: dict[str, dict] = {}
    shap_globals: dict[str, pd.Series] = {}
    stability_rows: list[dict] = []

    for name, n in TENANTS:
        sl = tenant_data[name]
        model, X_tr, X_te, y_tr, y_te, auc, f1 = train_one(sl, feature_cols)

        shap_sample = X_te[: min(200, len(X_te))]
        shap_mean, shap_raw = global_shap(model, shap_sample)
        shap_series = pd.Series(shap_mean, index=feature_cols)
        shap_globals[name] = shap_series

        lime_n = min(30, len(X_te)) if n >= 100 else min(15, len(X_te))
        lime_mean = global_lime(model, X_tr, X_te, feature_cols, n_samples=lime_n)
        lime_series = pd.Series(lime_mean, index=feature_cols)

        jaccard = lime_jaccard_stability(model, X_tr, shared_eval, feature_cols)
        ent = shap_entropy(shap_raw)
        var = float(np.var(np.abs(shap_raw)))

        results[name] = {
            "n_rows": int(len(sl)),
            "auc_roc": round(float(auc), 4),
            "f1": round(float(f1), 4),
            "shap_top5": shap_series.sort_values(ascending=False).head(5).round(5).to_dict(),
            "lime_top5": lime_series.sort_values(ascending=False).head(5).round(5).to_dict(),
            "shap_entropy_mean": round(ent, 4),
            "shap_abs_variance": round(var, 6),
            "lime_local_jaccard_top5": round(jaccard, 4),
        }
        stability_rows.append(
            {
                "tenant": name,
                "n_rows": len(sl),
                "auc": auc,
                "f1": f1,
                "shap_entropy": ent,
                "shap_abs_variance": var,
                "lime_jaccard": jaccard,
            }
        )
        print(
            f"      {name:>15} n={len(sl):>5}  AUC={auc:.3f}  F1={f1:.3f}  "
            f"|SHAP|var={var:.4f}  Jaccard={jaccard:.3f}"
        )

    ref_name = "A_data_rich"
    ref_rank = shap_globals[ref_name]
    for row in stability_rows:
        t = shap_globals[row["tenant"]]
        rho, _ = spearmanr(ref_rank.values, t.values)
        row["spearman_shap_vs_A"] = float(rho)
        results[row["tenant"]]["spearman_shap_vs_A"] = round(float(rho), 4)

    (OUT_DIR / "metrics_summary.json").write_text(json.dumps(results, indent=2))
    pd.DataFrame(stability_rows).to_csv(OUT_DIR / "stability_metrics.csv", index=False)

    print("[5/5] Figures ...")
    sns.set_style("whitegrid")
    stab_df = pd.DataFrame(stability_rows).sort_values("n_rows")

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.plot(stab_df["n_rows"], stab_df["spearman_shap_vs_A"], marker="o", linewidth=2, color="#1f77b4")
    ax.set_xscale("log")
    ax.set_xlabel("Tenant data volume (rows, log scale)")
    ax.set_ylabel(r"Spearman $\rho$ of global SHAP vs Tenant A")
    ax.set_title("HR Attrition: Global Explanation Stability vs Data Volume")
    ax.axhline(0.7, ls="--", color="red", alpha=0.5, label=r"$\rho = 0.70$ reliability bound")
    ax.axhline(1.0, ls=":", color="gray", alpha=0.5)
    ax.legend(loc="lower right")
    for _, r in stab_df.iterrows():
        ax.annotate(r["tenant"].split("_")[0], (r["n_rows"], r["spearman_shap_vs_A"]),
                    textcoords="offset points", xytext=(5, 5))
    fig.tight_layout()
    fig.savefig(FIG_DIR / "hr_spearman_shap_degradation.png", dpi=150)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.plot(stab_df["n_rows"], stab_df["shap_abs_variance"], marker="^", linewidth=2, color="#9467bd")
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel("Tenant data volume (rows, log scale)")
    ax.set_ylabel("SHAP absolute-value variance (log scale)")
    ax.set_title("HR Attrition: SHAP Attribution Variance vs Data Volume")
    fig.tight_layout()
    fig.savefig(FIG_DIR / "hr_shap_variance_vs_volume.png", dpi=150)
    plt.close(fig)

    print("\nDone. Artifacts written to:", OUT_DIR)


if __name__ == "__main__":
    main()
