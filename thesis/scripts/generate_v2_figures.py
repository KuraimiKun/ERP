"""Generate all v2 thesis chapter figures from empirical metrics.

Outputs PNGs into thesis/figures/ that the .tex files include by name.
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

THESIS = Path(__file__).resolve().parent.parent
FIGS = THESIS / "figures"
FIGS.mkdir(exist_ok=True)
METRICS = json.loads(
    (THESIS / "results" / "sparsity_experiment" / "metrics_summary.json").read_text()
)

ORDER = ["A_data_rich", "B_medium", "C_sparse", "D_very_sparse", "E_cold_start"]
LABELS = ["A\n50,000", "B\n5,000", "C\n1,000", "D\n200", "E\n50"]
N = [METRICS[k]["n_rows"] for k in ORDER]
AUC = [METRICS[k]["auc_roc"] for k in ORDER]
F1 = [METRICS[k]["f1"] for k in ORDER]
SPEAR = [METRICS[k]["spearman_shap_vs_A"] for k in ORDER]
VAR = [METRICS[k]["shap_abs_variance"] for k in ORDER]
JACC = [METRICS[k]["lime_local_jaccard_top5"] for k in ORDER]

plt.rcParams.update({
    "font.family": "serif",
    "font.size": 11,
    "axes.titlesize": 12,
    "axes.labelsize": 11,
    "legend.fontsize": 10,
    "figure.dpi": 150,
})


def save(fig: plt.Figure, name: str) -> None:
    out = FIGS / name
    fig.savefig(out, bbox_inches="tight", dpi=200)
    plt.close(fig)
    print(f"[ok] {out.relative_to(THESIS)}")


# ---------------------------------------------------------------------------
# Figure 2.1 — SHAP vs LIME mechanistic comparison (conceptual)
# ---------------------------------------------------------------------------
def fig_2_1() -> None:
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 4.2))

    # SHAP — bar chart of Shapley contributions building toward f(x)
    feats = ["x_4", "x_3", "x_2", "x_1"]
    contribs = [0.18, -0.07, 0.22, 0.14]
    base = 0.30
    cum = base
    colors = ["#2E86AB" if c > 0 else "#C73E1D" for c in contribs]
    ax1.barh([0], [base], color="#888", height=0.4, label="E[f(x)]")
    for i, (c, col) in enumerate(zip(contribs, colors)):
        ax1.barh([i + 1], [c], left=cum if c > 0 else cum + c,
                 color=col, height=0.4)
        cum += c
    ax1.axvline(cum, color="black", linestyle="--", linewidth=1)
    ax1.text(cum + 0.01, len(contribs) + 0.6, f"f(x) = {cum:.2f}",
             fontsize=9, fontweight="bold")
    ax1.set_yticks(range(len(feats) + 1))
    ax1.set_yticklabels(["E[f(x)]"] + feats)
    ax1.set_xlim(0, 1.0)
    ax1.set_xlabel("Model output")
    ax1.set_title("SHAP — Shapley value decomposition\n"
                  r"$\phi_i$ = average marginal contribution over coalitions")
    ax1.grid(axis="x", alpha=0.3)

    # LIME — perturbation cloud + local linear surrogate
    rng = np.random.default_rng(42)
    xs = rng.uniform(-3, 3, 400)
    ys = rng.uniform(-3, 3, 400)
    # nonlinear decision boundary
    z = (xs**2 + ys**2 < 4).astype(int)
    ax2.scatter(xs[z == 0], ys[z == 0], s=8, color="#C73E1D", alpha=0.35,
                label="f(z)=0")
    ax2.scatter(xs[z == 1], ys[z == 1], s=8, color="#2E86AB", alpha=0.35,
                label="f(z)=1")
    # instance x
    ax2.scatter([1.4], [0.6], s=220, marker="*", color="black", zorder=5,
                label="instance x")
    # locality kernel pi_x (circle)
    circle = mpatches.Circle((1.4, 0.6), 1.1, fill=False, edgecolor="black",
                             linestyle=":", linewidth=1.5)
    ax2.add_patch(circle)
    # local linear surrogate g (line)
    xx = np.linspace(0.2, 2.6, 50)
    yy = 0.6 - 0.9 * (xx - 1.4)
    ax2.plot(xx, yy, color="black", linewidth=2, label="surrogate g(z')")
    ax2.set_xlim(-3, 3)
    ax2.set_ylim(-3, 3)
    ax2.set_xlabel("feature 1")
    ax2.set_ylabel("feature 2")
    ax2.set_title("LIME — local surrogate via weighted regression\n"
                  r"$\xi(x) = \arg\min_g \mathcal{L}(f,g,\pi_x) + \Omega(g)$")
    ax2.legend(loc="lower left", fontsize=8, framealpha=0.9)
    ax2.set_aspect("equal")

    fig.tight_layout()
    save(fig, "sparsity_fig_2_1_shap_vs_lime.png")


# ---------------------------------------------------------------------------
# Figure 2.2 — Theoretical Reliability Cliff
# ---------------------------------------------------------------------------
def fig_2_2() -> None:
    fig, ax = plt.subplots(figsize=(8, 4.5))
    n_grid = np.logspace(1.3, 4.9, 400)
    # smooth sigmoid-like reliability curve, transition centred at n=1000
    rho = 0.45 + 0.55 / (1 + np.exp(-1.4 * (np.log10(n_grid) - 3.0)))
    ax.plot(n_grid, rho, color="#1F4E79", linewidth=2.5,
            label=r"theoretical $\rho(n)$")
    ax.axhline(0.70, color="#C73E1D", linestyle="--", linewidth=1.5,
               label=r"reliability bound $\rho = 0.70$")
    ax.axvline(1000, color="black", linestyle=":", linewidth=1.5,
               label=r"hypothesised cliff $n = 1{,}000$")
    ax.fill_between(n_grid, 0, 1, where=(n_grid < 1000),
                    color="#C73E1D", alpha=0.07)
    ax.fill_between(n_grid, 0, 1, where=(n_grid >= 1000),
                    color="#2E86AB", alpha=0.07)
    ax.text(120, 0.92, "cold-start regime\n(unreliable XAI)",
            fontsize=9, color="#7A1C0E")
    ax.text(5500, 0.92, "data-mature regime\n(reliable XAI)",
            fontsize=9, color="#1F4E79")
    ax.set_xscale("log")
    ax.set_xlim(20, 80000)
    ax.set_ylim(0.3, 1.02)
    ax.set_xlabel(r"Tenant data volume $n$ (log scale)")
    ax.set_ylabel(r"Explanation fidelity (Spearman $\rho$ vs baseline)")
    ax.set_title("Conceptual Reliability Cliff")
    ax.grid(alpha=0.3, which="both")
    ax.legend(loc="lower right", framealpha=0.95)
    fig.tight_layout()
    save(fig, "sparsity_fig_2_2_reliability_cliff_theory.png")


# ---------------------------------------------------------------------------
# Figure 3.1 — Stratified slicing diagram
# ---------------------------------------------------------------------------
def fig_3_1() -> None:
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 6)
    ax.axis("off")

    # source dataset
    src = mpatches.FancyBboxPatch((0.2, 2.3), 1.9, 1.4,
                                  boxstyle="round,pad=0.08",
                                  facecolor="#1F4E79", edgecolor="black")
    ax.add_patch(src)
    ax.text(1.15, 3.0, "Olist\nN = 96,460", color="white",
            ha="center", va="center", fontsize=10, fontweight="bold")

    # global hold-out
    ho = mpatches.FancyBboxPatch((2.7, 4.2), 2.0, 1.0,
                                 boxstyle="round,pad=0.08",
                                 facecolor="#888888", edgecolor="black")
    ax.add_patch(ho)
    ax.text(3.7, 4.7, "Global hold-out\n20%  (evaluation)",
            color="white", ha="center", va="center", fontsize=9,
            fontweight="bold")

    # five tenant tiers
    tiers = [
        ("Tenant A\nn = 50,000\nData-Rich", "#2E86AB"),
        ("Tenant B\nn = 5,000\nMedium", "#3FA7D6"),
        ("Tenant C\nn = 1,000\nSparse", "#F4A261"),
        ("Tenant D\nn = 200\nVery Sparse", "#E76F51"),
        ("Tenant E\nn = 50\nCold-Start", "#C73E1D"),
    ]
    x0 = 5.1
    width = 0.85
    gap = 0.13
    for i, (txt, col) in enumerate(tiers):
        x = x0 + i * (width + gap)
        box = mpatches.FancyBboxPatch((x, 0.8), width, 3.4,
                                      boxstyle="round,pad=0.05",
                                      facecolor=col, edgecolor="black")
        ax.add_patch(box)
        ax.text(x + width / 2, 2.5, txt, color="white",
                ha="center", va="center", fontsize=8, fontweight="bold")
        # arrow source -> tenant
        ax.annotate("", xy=(x + width / 2, 4.2), xytext=(2.1, 3.0),
                    arrowprops=dict(arrowstyle="->", color="black",
                                    lw=0.8, alpha=0.45))

    # arrow source -> hold-out
    ax.annotate("", xy=(2.7, 4.7), xytext=(2.1, 3.4),
                arrowprops=dict(arrowstyle="->", color="black", lw=1.2))

    # arrow hold-out -> shared eval
    ax.text(5.0, 5.5, "Shared evaluation partition (identical across tiers)",
            ha="center", fontsize=9, style="italic", color="#444")
    ax.annotate("", xy=(8.6, 5.2), xytext=(4.7, 5.1),
                arrowprops=dict(arrowstyle="-", color="#444",
                                lw=0.8, linestyle="--"))

    ax.set_title("Stratified slicing of the base dataset into five simulated "
                 "tenant tiers", fontsize=11, fontweight="bold")
    fig.tight_layout()
    save(fig, "sparsity_fig_3_1_simulation_strategy.png")


# ---------------------------------------------------------------------------
# Figure 3.2 — Maturity-Aware AI Routing flowchart
# ---------------------------------------------------------------------------
def fig_3_2() -> None:
    fig, ax = plt.subplots(figsize=(9, 5.5))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 7)
    ax.axis("off")

    def box(x, y, w, h, txt, fc, tc="white", fs=9):
        p = mpatches.FancyBboxPatch((x, y), w, h,
                                    boxstyle="round,pad=0.08",
                                    facecolor=fc, edgecolor="black")
        ax.add_patch(p)
        ax.text(x + w / 2, y + h / 2, txt, color=tc, ha="center",
                va="center", fontsize=fs, fontweight="bold")

    def arrow(x1, y1, x2, y2, lbl=None):
        ax.annotate("", xy=(x2, y2), xytext=(x1, y1),
                    arrowprops=dict(arrowstyle="->", lw=1.4))
        if lbl:
            ax.text((x1 + x2) / 2 + 0.15, (y1 + y2) / 2, lbl,
                    fontsize=9, style="italic")

    box(3.3, 6.0, 3.4, 0.8, "invoice request\n(tenant t)", "#1F4E79")
    box(3.3, 4.4, 3.4, 0.9,
        "LatePaymentPredictor\n.predict_or_heuristic(invoice)", "#444444")
    # diamond decision
    diamond = mpatches.Polygon(
        [(5.0, 3.7), (6.6, 2.85), (5.0, 2.0), (3.4, 2.85)],
        facecolor="#F4A261", edgecolor="black")
    ax.add_patch(diamond)
    ax.text(5.0, 2.85, r"$n_t < 1{,}000$ ?", ha="center", va="center",
            fontsize=10, fontweight="bold", color="white")

    box(0.4, 0.5, 3.3, 1.1,
        "Global Heuristic\ncold_start_heuristic.json", "#C73E1D")
    box(6.3, 0.5, 3.3, 1.1,
        "Local SHAP / LIME\nper-tenant explanation", "#2E86AB")

    # arrows
    arrow(5.0, 6.0, 5.0, 5.3)
    arrow(5.0, 4.4, 5.0, 3.7)
    arrow(3.6, 2.6, 2.0, 1.6, "yes")
    arrow(6.4, 2.6, 8.0, 1.6, "no")

    ax.text(5.0, 0.05,
            r"Architectural gate: $\tau = $ COLD_START_INVOICE_THRESHOLD = 1000",
            ha="center", fontsize=9, style="italic", color="#444")

    ax.set_title("Maturity-Aware AI Routing architectural gate",
                 fontsize=11, fontweight="bold")
    fig.tight_layout()
    save(fig, "sparsity_fig_3_2_routing_architecture.png")


# ---------------------------------------------------------------------------
# Figure 4.1 — AUC and F1 degradation
# ---------------------------------------------------------------------------
def fig_4_1() -> None:
    fig, ax = plt.subplots(figsize=(8.5, 4.6))
    x = np.arange(len(ORDER))
    ax.plot(x, AUC, marker="o", linewidth=2.2, color="#1F4E79",
            label="AUC-ROC")
    ax.plot(x, F1, marker="s", linewidth=2.2, color="#C73E1D",
            label="F1-Score")
    ax.axhline(0.5, color="black", linestyle="--", linewidth=1.2,
               label="random-classifier baseline (AUC = 0.5)")
    for xi, (a, f) in enumerate(zip(AUC, F1)):
        ax.annotate(f"{a:.3f}", (xi, a), textcoords="offset points",
                    xytext=(0, 8), ha="center", fontsize=8, color="#1F4E79")
        ax.annotate(f"{f:.3f}", (xi, f), textcoords="offset points",
                    xytext=(0, -14), ha="center", fontsize=8, color="#C73E1D")
    ax.set_xticks(x)
    ax.set_xticklabels(LABELS)
    ax.set_xlabel("Tenant tier (n records)")
    ax.set_ylabel("Metric value")
    ax.set_ylim(-0.05, 0.9)
    ax.set_title("Predictive performance degradation across simulated "
                 "tenant tiers")
    ax.grid(alpha=0.3)
    ax.legend(loc="upper right")
    fig.tight_layout()
    save(fig, "sparsity_fig_4_1_predictive_degradation.png")


# ---------------------------------------------------------------------------
# Figure 4.2 — Empirical reliability cliff (dual axis)
# ---------------------------------------------------------------------------
def fig_4_2() -> None:
    fig, ax1 = plt.subplots(figsize=(9, 5))
    ax1.plot(N, SPEAR, marker="o", linewidth=2.2, color="#1F4E79",
             label=r"Spearman $\rho$ vs Tenant A")
    ax1.axhline(0.70, color="#1F4E79", linestyle="--", linewidth=1.2,
                alpha=0.7, label=r"$\rho = 0.70$ reliability bound")
    ax1.set_xscale("log")
    ax1.set_xlabel(r"Tenant data volume $n$ (log scale)")
    ax1.set_ylabel(r"Spearman rank correlation", color="#1F4E79")
    ax1.tick_params(axis="y", labelcolor="#1F4E79")
    ax1.set_ylim(0.4, 1.05)

    ax2 = ax1.twinx()
    ax2.plot(N, VAR, marker="s", linewidth=2.2, color="#C73E1D",
             label="SHAP absolute variance")
    ax2.set_ylabel("SHAP absolute variance", color="#C73E1D")
    ax2.tick_params(axis="y", labelcolor="#C73E1D")
    ax2.set_ylim(0, 0.22)

    # annotate cliff
    ax1.axvline(1000, color="black", linestyle=":", linewidth=1.5)
    ax1.text(1050, 0.42, "Reliability Cliff\n n = 1,000",
             fontsize=9, fontweight="bold")

    for xi, yi in zip(N, SPEAR):
        ax1.annotate(f"{yi:.3f}", (xi, yi), textcoords="offset points",
                     xytext=(6, 8), fontsize=8, color="#1F4E79")
    for xi, yi in zip(N, VAR):
        ax2.annotate(f"{yi:.3f}", (xi, yi), textcoords="offset points",
                     xytext=(6, -12), fontsize=8, color="#C73E1D")

    lines1, labs1 = ax1.get_legend_handles_labels()
    lines2, labs2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labs1 + labs2, loc="upper right",
               framealpha=0.95, fontsize=9)
    ax1.set_title("Joint degradation of SHAP rank fidelity and "
                  "attribution concentration")
    ax1.grid(alpha=0.3, which="both")
    fig.tight_layout()
    save(fig, "sparsity_fig_4_2_reliability_cliff.png")


if __name__ == "__main__":
    fig_2_1()
    fig_2_2()
    fig_3_1()
    fig_3_2()
    fig_4_1()
    fig_4_2()
    print("All figures written to", FIGS)
