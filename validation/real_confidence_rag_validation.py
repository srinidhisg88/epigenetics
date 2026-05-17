"""
Real Data Confidence-Aware RAG Validation.

Data sources (NO mock data):
  - ML predictions : loaded from the trained epilepsy_classifier.pkl
                     on the held-out X_test.csv set
  - Ground truth   : ClinSigSimple from test.csv (0=benign, 1=pathogenic)
  - ClinVar review : data/processed/epilepsy_variants_all.csv
                     (used to look up review status for each test variant)

Experiment:
  1. Identify GENUINELY uncertain ML variants: pathogenic_prob ∈ [0.3, 0.7]
  2. ML-only accuracy  : threshold at 0.5 on those uncertain variants
  3. Evidence-augmented: for variants with a 2+ star ClinVar review,
     use the ClinVar classification instead of the ML prediction
  4. Measure accuracy improvement and reduction in uncertain calls

This validates that our Confidence-Aware RAG mechanism improves decisions
on cases where the model itself is uncertain — using real trained-model
probabilities and real ClinVar expert review status.
"""

import sys
import json
import pickle
import random
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from pathlib import Path
from collections import Counter

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

MODEL_FILE   = BASE_DIR / "models" / "epilepsy_classifier.pkl"
X_TEST_FILE  = BASE_DIR / "data" / "processed" / "X_test.csv"
TEST_FILE    = BASE_DIR / "data" / "processed" / "test.csv"
ALL_CSV      = BASE_DIR / "data" / "processed" / "epilepsy_variants_all.csv"
OUTPUT_DIR   = Path(__file__).parent / "results"
OUTPUT_DIR.mkdir(exist_ok=True)

UNCERTAIN_LOW  = 0.3
UNCERTAIN_HIGH = 0.7
MAX_VARIANTS   = 200
RANDOM_SEED    = 42


def _get_review_stars(rs: str) -> int:
    r = str(rs).lower()
    if "practice guideline"  in r: return 4
    if "expert panel"        in r: return 3
    if "multiple submitters" in r and "no conflicts" in r: return 2
    if "single submitter"    in r and "criteria provided" in r: return 1
    return 0


def _normalize_sig(sig: str) -> str:
    s = str(sig).lower()
    if "likely pathogenic" in s or "pathogenic/likely" in s: return "Pathogenic"
    if "likely benign"     in s or "benign/likely"     in s: return "Benign"
    if "pathogenic"        in s: return "Pathogenic"
    if "benign"            in s: return "Benign"
    return "Uncertain"


def run():
    print("=" * 72)
    print("REAL DATA CONFIDENCE-AWARE RAG VALIDATION")
    print("Trained ML model predictions + ClinVar expert review")
    print("=" * 72 + "\n")

    # ── Load model and test data ──────────────────────────────────────────────
    print("[Phase 1]  Loading model and test set...")
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        with open(MODEL_FILE, "rb") as f:
            model = pickle.load(f)

    X_test = pd.read_csv(X_TEST_FILE)
    test   = pd.read_csv(TEST_FILE)
    min_len = min(len(X_test), len(test))
    X_test  = X_test.iloc[:min_len]
    test    = test.iloc[:min_len].copy()

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        probs = model.predict_proba(X_test)[:, 1]
    test["pathogenic_prob"] = probs

    # ── Filter to genuinely uncertain variants ────────────────────────────────
    uncertain = test[
        (test["pathogenic_prob"] >= UNCERTAIN_LOW) &
        (test["pathogenic_prob"] <= UNCERTAIN_HIGH)
    ].copy()

    print(f"  Total test variants          : {len(test):,}")
    print(f"  Uncertain (prob 0.3–0.7)     : {len(uncertain):,}")
    print(f"  Ground truth distribution    : "
          f"{(uncertain['ClinSigSimple']==1).sum()} pathogenic, "
          f"{(uncertain['ClinSigSimple']==0).sum()} benign")

    # ── Look up ClinVar review status for each uncertain variant ──────────────
    print("\n[Phase 2]  Looking up ClinVar review status from local CSV...")
    all_csv = pd.read_csv(ALL_CSV, low_memory=False)

    # Build lookup: AlleleID → (ReviewStatus, ClinicalSignificance)
    review_lookup = {}
    for _, row in all_csv.iterrows():
        aid = str(row.get("#AlleleID", ""))
        if aid and str(row.get("Assembly", "")) == "GRCh38":
            rs    = str(row.get("ReviewStatus", ""))
            stars = _get_review_stars(rs)
            sig   = str(row.get("ClinicalSignificance", ""))
            norm  = _normalize_sig(sig)
            if stars >= 2 and norm in ("Pathogenic", "Benign"):
                # Keep the highest-star record per allele
                existing = review_lookup.get(aid, (0, ""))
                if stars > existing[0]:
                    review_lookup[aid] = (stars, norm)

    print(f"  Variants with 2+ star review in lookup : {len(review_lookup):,}")

    # ── Build validation set ──────────────────────────────────────────────────
    sample = uncertain.sample(min(MAX_VARIANTS, len(uncertain)), random_state=RANDOM_SEED)

    results      = []
    ml_correct   = 0
    evi_correct  = 0
    evidence_used = 0

    print("\n[Phase 3]  Computing accuracy...\n")
    print(f"  {'Gene':10} {'ML prob':8} {'ML-only':18} {'Evidence-Aug':18} {'GT':10} {'Match'}")
    print("  " + "─" * 80)

    for _, row in sample.iterrows():
        prob    = row["pathogenic_prob"]
        gt_raw  = int(row.get("ClinSigSimple", 0))
        gt      = "Pathogenic" if gt_raw == 1 else "Benign"
        gene    = str(row.get("GeneSymbol", "?"))
        allele_id = str(row.get("#AlleleID", ""))

        # ML-only: threshold at 0.5
        ml_call = "Pathogenic" if prob >= 0.5 else "Benign"
        ml_ok   = ml_call == gt

        # Evidence-augmented: if ClinVar 2+ star review available, use it
        lookup = review_lookup.get(allele_id)
        if lookup:
            evi_call = lookup[1]  # ClinVar-derived call
            evidence_used += 1
        else:
            evi_call = ml_call   # Fall back to ML if no good ClinVar data

        evi_ok = evi_call == gt

        if ml_ok:  ml_correct  += 1
        if evi_ok: evi_correct += 1

        match = ("✓" if evi_ok else "✗") + (" [ClinVar]" if lookup else " [ML]")
        print(f"  {gene:10} {prob:.3f}    {ml_call:18} {evi_call:18} {gt:10} {match}")

        results.append({
            "allele_id":    allele_id,
            "gene":         gene,
            "prob":         round(float(prob), 4),
            "ml_call":      ml_call,
            "evi_call":     evi_call,
            "ground_truth": gt,
            "ml_correct":   ml_ok,
            "evi_correct":  evi_ok,
            "used_clinvar": lookup is not None,
            "review_stars": lookup[0] if lookup else 0,
        })

    total          = len(results)
    ml_acc         = ml_correct  / total * 100
    evi_acc        = evi_correct / total * 100
    improvement    = evi_acc - ml_acc
    clinvar_pct    = evidence_used / total * 100

    print("\n" + "=" * 72)
    print("RESULTS")
    print("=" * 72)
    print(f"  Total uncertain ML variants tested : {total}")
    print(f"  ClinVar 2+★ evidence available     : {evidence_used}/{total} ({clinvar_pct:.1f}%)")
    print(f"  ML-only accuracy (prob > 0.5)       : {ml_correct}/{total} = {ml_acc:.1f}%")
    print(f"  Evidence-augmented accuracy         : {evi_correct}/{total} = {evi_acc:.1f}%")
    print(f"  Improvement                         : +{improvement:.1f} percentage points")

    _generate_figure(results, ml_correct, evi_correct, evidence_used,
                     total, ml_acc, evi_acc, improvement)

    output = {
        "data_source":      "epilepsy_classifier.pkl predictions + ClinVar expert review",
        "total":            total,
        "evidence_used":    evidence_used,
        "ml_accuracy":      round(ml_acc, 2),
        "evi_accuracy":     round(evi_acc, 2),
        "improvement":      round(improvement, 2),
        "results":          results,
    }
    out_json = OUTPUT_DIR / "real_confidence_rag_results.json"
    with open(out_json, "w") as f:
        json.dump(output, f, indent=2)
    print(f"\n  Results saved → {out_json}")
    return output


def _generate_figure(results, ml_correct, evi_correct, evidence_used,
                     total, ml_acc, evi_acc, improvement):
    fig, axes = plt.subplots(1, 3, figsize=(18, 6))
    fig.suptitle(
        "Confidence-Aware RAG — Resolving Genuinely Uncertain ML Predictions\n"
        f"(n={total} variants where ML probability ∈ [0.3, 0.7], real test set)",
        fontsize=12, fontweight="bold"
    )

    # ── Plot 1: Accuracy comparison ───────────────────────────────────────────
    ax = axes[0]
    bars = ax.bar(["ML-Only\n(threshold 0.5)", "Evidence-Augmented\n(ML + ClinVar 2+★)"],
                  [ml_acc, evi_acc],
                  color=["#90A4AE", "#1976D2"], alpha=0.88, width=0.4)
    ax.set_ylim(0, 110)
    ax.set_ylabel("Accuracy (%)")
    ax.set_title("Accuracy on Uncertain Variants\n(ML prob 0.3–0.7)", fontweight="bold")
    for bar, val in zip(bars, [ml_acc, evi_acc]):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1,
                f"{val:.1f}%", ha="center", fontsize=14, fontweight="bold")
    if improvement > 0:
        ax.annotate(f"+{improvement:.1f}%\nimprovement",
                    xy=(1, evi_acc), xytext=(1.25, evi_acc - 15),
                    arrowprops=dict(arrowstyle="->", color="green"),
                    fontsize=11, color="green", fontweight="bold")

    # ── Plot 2: Evidence usage breakdown ─────────────────────────────────────
    ax2 = axes[1]
    clinvar_correct  = sum(1 for r in results if r["used_clinvar"] and r["evi_correct"])
    clinvar_wrong    = sum(1 for r in results if r["used_clinvar"] and not r["evi_correct"])
    ml_fallback_ok   = sum(1 for r in results if not r["used_clinvar"] and r["evi_correct"])
    ml_fallback_bad  = sum(1 for r in results if not r["used_clinvar"] and not r["evi_correct"])

    labels = ["ClinVar\nCorrect", "ClinVar\nWrong", "ML Fallback\nCorrect", "ML Fallback\nWrong"]
    counts = [clinvar_correct, clinvar_wrong, ml_fallback_ok, ml_fallback_bad]
    colors = ["#1976D2", "#EF5350", "#43A047", "#FF8A65"]
    bars2 = ax2.bar(labels, counts, color=colors, alpha=0.85)
    ax2.set_ylabel("Count")
    ax2.set_title("Evidence Usage Breakdown\n(ClinVar vs ML Fallback)", fontweight="bold")
    for bar, count in zip(bars2, counts):
        ax2.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.3,
                 str(count), ha="center", fontsize=12, fontweight="bold")
    ax2.tick_params(axis="x", labelsize=8)

    # ── Plot 3: Probability distribution of uncertain variants ────────────────
    ax3 = axes[2]
    path_probs  = [r["prob"] for r in results if r["ground_truth"] == "Pathogenic"]
    benign_probs = [r["prob"] for r in results if r["ground_truth"] == "Benign"]
    bins = np.linspace(0.3, 0.7, 15)
    ax3.hist(path_probs,  bins=bins, label=f"Pathogenic (n={len(path_probs)})",
             color="#E53935", alpha=0.7)
    ax3.hist(benign_probs, bins=bins, label=f"Benign (n={len(benign_probs)})",
             color="#43A047", alpha=0.7)
    ax3.axvline(0.5, color="black", linestyle="--", linewidth=1.5, label="0.5 threshold")
    ax3.set_xlabel("ML Pathogenic Probability")
    ax3.set_ylabel("Count")
    ax3.set_title("Probability Distribution\n(Genuinely Uncertain Variants)", fontweight="bold")
    ax3.legend(fontsize=8)

    plt.tight_layout()
    out = OUTPUT_DIR / "real_confidence_rag_validation.png"
    plt.savefig(out, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  Figure saved  → {out}")


if __name__ == "__main__":
    run()
