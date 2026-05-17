"""
System Architecture Diagram — Epilepsy Diagnostic Assistant.

Generates a clean, publication-ready diagram showing all components
and data flow for use in the paper and PPT.
"""

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
from pathlib import Path

OUTPUT_DIR = Path(__file__).parent / "results"
OUTPUT_DIR.mkdir(exist_ok=True)


def draw_box(ax, x, y, w, h, label, sublabel="", color="#1976D2",
             text_color="white", fontsize=9, radius=0.015):
    box = FancyBboxPatch((x, y), w, h,
                         boxstyle=f"round,pad=0.01,rounding_size={radius}",
                         facecolor=color, edgecolor="white",
                         linewidth=1.5, zorder=3)
    ax.add_patch(box)
    cy = y + h / 2
    if sublabel:
        ax.text(x + w/2, cy + h*0.12, label,
                ha="center", va="center", fontsize=fontsize,
                fontweight="bold", color=text_color, zorder=4)
        ax.text(x + w/2, cy - h*0.18, sublabel,
                ha="center", va="center", fontsize=fontsize - 1.5,
                color=text_color, alpha=0.9, zorder=4,
                style="italic")
    else:
        ax.text(x + w/2, cy, label,
                ha="center", va="center", fontsize=fontsize,
                fontweight="bold", color=text_color, zorder=4)


def arrow(ax, x1, y1, x2, y2, color="#455A64", label="", lw=1.5):
    ax.annotate("", xy=(x2, y2), xytext=(x1, y1),
                arrowprops=dict(arrowstyle="-|>", color=color,
                                lw=lw, mutation_scale=12),
                zorder=2)
    if label:
        mx, my = (x1+x2)/2, (y1+y2)/2
        ax.text(mx + 0.005, my, label, fontsize=7, color=color,
                va="center", style="italic")


def make_diagram():
    fig, ax = plt.subplots(figsize=(18, 11))
    ax.set_xlim(0, 1); ax.set_ylim(0, 1)
    ax.axis("off")
    fig.patch.set_facecolor("#F8F9FA")

    # ── Title ─────────────────────────────────────────────────────────────────
    ax.text(0.5, 0.97,
            "Epilepsy Diagnostic Assistant — System Architecture",
            ha="center", va="top", fontsize=15, fontweight="bold", color="#1A237E")
    ax.text(0.5, 0.935,
            "Confidence-Adaptive · Contradiction-Aware · ACMG-Automated · Explainable",
            ha="center", va="top", fontsize=10, color="#455A64", style="italic")

    # ══════════════════════════════════════════════════════════════════════════
    # ROW 1 — INPUT
    # ══════════════════════════════════════════════════════════════════════════
    draw_box(ax, 0.03, 0.80, 0.20, 0.09,
             "Variant Input",
             "Gene · Chromosome · Position\nRef/Alt · Consequence · Origin",
             color="#1565C0", fontsize=8.5)

    # ══════════════════════════════════════════════════════════════════════════
    # ROW 2 — ML + SHAP (left side)
    # ══════════════════════════════════════════════════════════════════════════
    draw_box(ax, 0.03, 0.62, 0.20, 0.10,
             "XGBoost Classifier",
             "93 features · 26 epilepsy genes\nAUC-ROC = 0.945",
             color="#283593", fontsize=8.5)

    draw_box(ax, 0.26, 0.62, 0.18, 0.10,
             "SHAP Explainer",
             "CalibratedClassifierCV unwrap\nFeature attribution → clinical text",
             color="#4527A0", fontsize=8.5)

    # ══════════════════════════════════════════════════════════════════════════
    # ROW 2 — External APIs (right side)
    # ══════════════════════════════════════════════════════════════════════════
    draw_box(ax, 0.47, 0.72, 0.15, 0.08,
             "ClinVar",
             "Variant significance\nReview stars · Conditions",
             color="#00695C", fontsize=8)

    draw_box(ax, 0.64, 0.72, 0.15, 0.08,
             "gnomAD",
             "Population allele frequency\nGraphQL API · 30-day cache",
             color="#2E7D32", fontsize=8)

    draw_box(ax, 0.81, 0.72, 0.16, 0.08,
             "PharmGKB",
             "Drug-gene interactions\nContraindications · Dosage",
             color="#1B5E20", fontsize=8)

    draw_box(ax, 0.47, 0.62, 0.50, 0.08,
             "PubMed RAG Retriever",
             "FAISS + PubMedBERT embeddings · Epilepsy-specific literature corpus",
             color="#388E3C", fontsize=8.5)

    # ══════════════════════════════════════════════════════════════════════════
    # ROW 3 — NOVEL FEATURES (highlighted band)
    # ══════════════════════════════════════════════════════════════════════════
    # Background band for novel features
    novel_band = FancyBboxPatch((0.01, 0.34), 0.98, 0.24,
                                 boxstyle="round,pad=0.01",
                                 facecolor="#FFF8E1", edgecolor="#F9A825",
                                 linewidth=2, linestyle="--", zorder=1)
    ax.add_patch(novel_band)
    ax.text(0.5, 0.595, "★  NOVEL CONTRIBUTIONS  ★",
            ha="center", va="bottom", fontsize=9, color="#F57F17",
            fontweight="bold")

    # ACMG Classifier
    draw_box(ax, 0.03, 0.43, 0.21, 0.12,
             "ACMG/AMP Classifier",
             "14 criteria automated\nPVS1·PS1·PS2·PM2·BA1·BS1·BP7…\n5-tier classification",
             color="#E65100", fontsize=8)

    # Confidence resolver
    draw_box(ax, 0.27, 0.43, 0.21, 0.12,
             "Confidence-Aware RAG",
             "ML prob 0.3–0.7 → extra retrieval\nEvidence weighting\n68.8% → 93.8% accuracy",
             color="#BF360C", fontsize=8)

    # Contradiction detector
    draw_box(ax, 0.51, 0.43, 0.21, 0.12,
             "Contradiction Detector",
             "ML vs ClinVar · ML vs gnomAD\nML vs Consequence · VUS flags\nSensitivity = 100%",
             color="#880E4F", fontsize=8)

    # Multi-source retriever
    draw_box(ax, 0.75, 0.43, 0.22, 0.12,
             "Multi-Source Retriever",
             "Evidence hierarchy:\nClinVar 40% · PharmGKB 30%\ngnomAD 10% · PubMed 20%",
             color="#4A148C", fontsize=8)

    # ══════════════════════════════════════════════════════════════════════════
    # ROW 4 — LLM Generator
    # ══════════════════════════════════════════════════════════════════════════
    draw_box(ax, 0.20, 0.23, 0.60, 0.09,
             "LLM Clinical Report Generator",
             "Groq API · Llama 3.3 70B · ACMG-aware prompt · "
             "Clinical language (no ML jargon exposed to user)",
             color="#4E342E", fontsize=8.5)

    # ══════════════════════════════════════════════════════════════════════════
    # ROW 5 — OUTPUTS
    # ══════════════════════════════════════════════════════════════════════════
    draw_box(ax, 0.03, 0.08, 0.17, 0.09,
             "Variant Report",
             "5-tier ACMG class\nML prediction + SHAP\ngnomAD frequency",
             color="#37474F", fontsize=8)

    draw_box(ax, 0.22, 0.08, 0.17, 0.09,
             "Treatment Plan",
             "First-line medications\nContraindications\nPharmGKB evidence",
             color="#37474F", fontsize=8)

    draw_box(ax, 0.41, 0.08, 0.17, 0.09,
             "Contradiction Alert",
             "Clinical safety warning\nEvidence conflict summary\nRecommended action",
             color="#B71C1C", fontsize=8)

    draw_box(ax, 0.60, 0.08, 0.17, 0.09,
             "PDF Report",
             "Structured clinical\ndocument for records",
             color="#37474F", fontsize=8)

    draw_box(ax, 0.79, 0.08, 0.18, 0.09,
             "Chat Follow-Up",
             "ACMG + SHAP context\npersisted across turns\nClinical Q&A",
             color="#37474F", fontsize=8)

    # ══════════════════════════════════════════════════════════════════════════
    # ARROWS
    # ══════════════════════════════════════════════════════════════════════════

    # Input → XGBoost
    arrow(ax, 0.13, 0.80, 0.13, 0.72)
    # Input → External APIs (horizontal)
    arrow(ax, 0.23, 0.845, 0.47, 0.76)

    # XGBoost → SHAP
    arrow(ax, 0.23, 0.67, 0.26, 0.67)
    # XGBoost → ACMG (ML prediction feeds ACMG)
    arrow(ax, 0.13, 0.62, 0.13, 0.55)
    # SHAP → ACMG
    arrow(ax, 0.35, 0.62, 0.17, 0.55)
    # SHAP → Confidence Resolver
    arrow(ax, 0.38, 0.67, 0.37, 0.55)

    # ClinVar → ACMG
    arrow(ax, 0.545, 0.72, 0.15, 0.52, color="#00695C")
    # gnomAD → ACMG
    arrow(ax, 0.715, 0.72, 0.17, 0.52, color="#2E7D32")
    # gnomAD → Confidence Resolver
    arrow(ax, 0.715, 0.72, 0.38, 0.55, color="#2E7D32")
    # gnomAD → Contradiction Detector
    arrow(ax, 0.715, 0.72, 0.62, 0.55, color="#2E7D32")
    # ClinVar → Contradiction Detector
    arrow(ax, 0.545, 0.72, 0.62, 0.55, color="#00695C")
    # PharmGKB → Multi-source
    arrow(ax, 0.875, 0.72, 0.875, 0.55)
    # PubMed RAG → Multi-source
    arrow(ax, 0.72, 0.62, 0.86, 0.55)

    # All novel modules → LLM
    arrow(ax, 0.14, 0.43, 0.38, 0.32)
    arrow(ax, 0.37, 0.43, 0.44, 0.32)
    arrow(ax, 0.61, 0.43, 0.53, 0.32)
    arrow(ax, 0.86, 0.43, 0.66, 0.32)

    # LLM → Outputs
    arrow(ax, 0.35, 0.23, 0.115, 0.17)
    arrow(ax, 0.42, 0.23, 0.305, 0.17)
    arrow(ax, 0.50, 0.23, 0.495, 0.17)
    arrow(ax, 0.58, 0.23, 0.685, 0.17)
    arrow(ax, 0.65, 0.23, 0.875, 0.17)

    # ══════════════════════════════════════════════════════════════════════════
    # LEGEND
    # ══════════════════════════════════════════════════════════════════════════
    legend_items = [
        mpatches.Patch(color="#283593", label="ML Classification (XGBoost)"),
        mpatches.Patch(color="#2E7D32", label="External Evidence APIs"),
        mpatches.Patch(color="#E65100", label="Novel: ACMG Auto-Classifier"),
        mpatches.Patch(color="#BF360C", label="Novel: Confidence-Aware RAG"),
        mpatches.Patch(color="#880E4F", label="Novel: Contradiction Detection"),
        mpatches.Patch(color="#4A148C", label="Novel: Multi-Source Retriever"),
        mpatches.Patch(color="#4E342E", label="LLM Report Generation"),
    ]
    ax.legend(handles=legend_items, loc="lower right",
              fontsize=8, framealpha=0.9,
              bbox_to_anchor=(0.99, 0.01),
              title="Component Types", title_fontsize=8)

    # Cache indicator
    ax.text(0.715, 0.695, "SQLite\nCache", ha="center", fontsize=7,
            color="#2E7D32", style="italic",
            bbox=dict(boxstyle="round", facecolor="#E8F5E9", edgecolor="#2E7D32",
                      alpha=0.7, pad=0.2))

    out_path = OUTPUT_DIR / "system_architecture.png"
    plt.savefig(out_path, dpi=180, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close()
    print(f"Architecture diagram saved to: {out_path}")


if __name__ == "__main__":
    make_diagram()
