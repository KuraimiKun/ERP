"""Render the two thesis plots requested:

    1. Spearman correlation (global SHAP vs Tenant A) vs data volume.
    2. SHAP |value| variance vs data volume (uncertainty quantification).

Inputs:  thesis/results/sparsity_experiment/metrics_summary.json
Outputs: thesis/results/sparsity_experiment/figures/
            spearman_vs_data_volume.png
            shap_variance_vs_data_volume.png

Run:
    f:/erpdjango/venv/Scripts/python.exe thesis/scripts/plot_sparsity_summary.py
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
RESULTS = REPO_ROOT / "thesis" / "results" / "sparsity_experiment"
FIG_DIR = RESULTS / "figures"
FIG_DIR.mkdir(parents=True, exist_ok=True)


def _load() -> pd.DataFrame:
    data = json.loads((RESULTS / "metrics_summary.json").read_text())
    rows = [
        {
            "tenant": name,
            "label": name.split("_", 1)[0],
            "n_rows": v["n_rows"],
            "spearman": v["spearman_shap_vs_A"],
            "shap_variance": v["shap_abs_variance"],
        }
        for name, v in data.items()
    ]
    return pd.DataFrame(rows).sort_values("n_rows").reset_index(drop=True)


def plot_spearman(df: pd.DataFrame) -> Path:
    out = FIG_DIR / "spearman_vs_data_volume.png"
    fig, ax = plt.subplots(figsize=(8.5, 5.2))
    ax.plot(df["n_rows"], df["spearman"], marker="o", linewidth=2.4,
            color="#1f4e79", markersize=9, markerfacecolor="#1f4e79",
            markeredgecolor="white", markeredgewidth=1.5)
    ax.set_xscale("log")
    ax.set_ylim(0.0, 1.05)
    ax.set_xlabel("Tenant data volume — number of training rows (log scale)",
                  fontsize=11)
    ax.set_ylabel("Spearman rank correlation of global SHAP\nvs Tenant A (data-rich reference)",
                  fontsize=11)
    ax.set_title("Global Explanation Agreement Degrades with Data Sparsity",
                 fontsize=12.5, weight="bold", pad=14)
    ax.axhline(1.0, ls="--", color="#888", alpha=0.6, label="Perfect agreement (ρ = 1.0)")
    ax.axhline(0.7, ls=":", color="#c0504d", alpha=0.6, label="Reliability threshold (ρ = 0.7)")
    ax.grid(True, which="both", alpha=0.3)
    for _, r in df.iterrows():
        ax.annotate(f"{r['label']}\nn={int(r['n_rows']):,}\nρ={r['spearman']:.2f}",
                    (r["n_rows"], r["spearman"]),
                    textcoords="offset points", xytext=(10, -22 if r["label"] == "A" else 8),
                    fontsize=9, color="#333")
    ax.legend(loc="lower right", fontsize=9, framealpha=0.9)
    fig.tight_layout()
    fig.savefig(out, dpi=160)
    plt.close(fig)
    return out


def plot_shap_variance(df: pd.DataFrame) -> Path:
    out = FIG_DIR / "shap_variance_vs_data_volume.png"
    fig, ax = plt.subplots(figsize=(8.5, 5.2))
    ax.plot(df["n_rows"], df["shap_variance"], marker="s", linewidth=2.4,
            color="#7f1d1d", markersize=9, markerfacecolor="#7f1d1d",
            markeredgecolor="white", markeredgewidth=1.5)
    ax.set_xscale("log")
    ax.set_xlabel("Tenant data volume — number of training rows (log scale)",
                  fontsize=11)
    ax.set_ylabel("Variance of |SHAP values| across predictions\n(higher = more volatile explanations)",
                  fontsize=11)
    ax.set_title("Explanation Volatility Increases as Data Sparsity Grows",
                 fontsize=12.5, weight="bold", pad=14)
    ax.grid(True, which="both", alpha=0.3)

    a_var = df.loc[df["label"] == "A", "shap_variance"].iloc[0]
    ax.axhline(a_var, ls="--", color="#888", alpha=0.6,
               label=f"Tenant A baseline (var = {a_var:.3f})")
    for _, r in df.iterrows():
        ax.annotate(f"{r['label']}\nvar={r['shap_variance']:.3f}",
                    (r["n_rows"], r["shap_variance"]),
                    textcoords="offset points", xytext=(10, 8),
                    fontsize=9, color="#333")
    ax.legend(loc="upper right", fontsize=9, framealpha=0.9)
    fig.tight_layout()
    fig.savefig(out, dpi=160)
    plt.close(fig)
    return out


def main() -> None:
    df = _load()
    p1 = plot_spearman(df)
    p2 = plot_shap_variance(df)
    print(f"Wrote: {p1}")
    print(f"Wrote: {p2}")


if __name__ == "__main__":
    main()
