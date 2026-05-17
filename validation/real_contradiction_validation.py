"""
Real Data Contradiction Detection Validation.

Data sources (NO mock data):
  - ClinVar classifications : data/processed/epilepsy_variants_all.csv
  - gnomAD frequencies      : live gnomAD GraphQL API (cached 30 days)

Test design:
  True Positives  — Real ClinVar Benign/LB variants presented with
                    ML=Pathogenic → genuine ML-vs-ClinVar contradiction
  True Positives  — Real ClinVar Pathogenic/LP variants presented with
                    ML=Benign     → genuine ML-vs-ClinVar contradiction
  True Negatives  — Real ClinVar variant where ML agrees with ClinVar
                    → no contradiction expected

We are testing the ContradictionDetector logic against real expert data.
The ML prediction is parameterised to create / avoid contradictions;
the ClinVar classification and gnomAD frequency are always real.
"""

import sys
import json
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

from backend.confidence_resolver import ContradictionDetector
from backend.gnomad_fetcher import GnomADFetcher

DATA_FILE  = BASE_DIR / "data" / "processed" / "epilepsy_variants_all.csv"
OUTPUT_DIR = Path(__file__).parent / "results"
OUTPUT_DIR.mkdir(exist_ok=True)

EPILEPSY_GENES = [
    "SCN1A","SCN2A","SCN8A","KCNQ2",
    "TSC1", "TSC2", "CDKL5","STXBP1",
    "GABRA1","GABRG2","MECP2","SLC2A1",
    "CHD2","PCDH19",
]

MAX_PER_CLASS = 40   # 40 path + 40 benign = 80 contradiction cases + 80 controls
RANDOM_SEED   = 42


def _get_review_stars(review_status: str) -> int:
    r = str(review_status).lower()
    if "practice guideline"  in r: return 4
    if "expert panel"        in r: return 3
    if "multiple submitters" in r and "no conflicts" in r: return 2
    if "single submitter"    in r and "criteria provided" in r: return 1
    return 0


def _normalize_sig(sig: str) -> str:
    s = str(sig).lower()
    if "likely pathogenic" in s or "pathogenic/likely" in s: return "Likely Pathogenic"
    if "likely benign"     in s or "benign/likely"     in s: return "Likely Benign"
    if "pathogenic"        in s: return "Pathogenic"
    if "benign"            in s: return "Benign"
    return "VUS"


def load_variants() -> tuple:
    """Load and filter local ClinVar CSV, return (pathogenic_df, benign_df)."""
    print(f"Loading: {DATA_FILE}")
    df = pd.read_csv(DATA_FILE, low_memory=False)

    # GRCh38 + epilepsy genes + 2+ star review
    df = df[df["Assembly"] == "GRCh38"]
    df = df[df["GeneSymbol"].isin(EPILEPSY_GENES)]
    df = df[df["ReviewStatus"].str.contains(
        "multiple submitters.*no conflicts|expert panel|practice guideline",
        case=False, na=False, regex=True
    )]
    df = df[~df["ClinicalSignificance"].str.contains(
        "conflicting|uncertain|not provided|other", case=False, na=False
    )]
    df = df[df["PositionVCF"].notna() & df["ReferenceAlleleVCF"].notna() & df["AlternateAlleleVCF"].notna()]
    df = df[df["Chromosome"].notna()]
    df["ref_len"] = df["ReferenceAlleleVCF"].astype(str).str.len()
    df["alt_len"] = df["AlternateAlleleVCF"].astype(str).str.len()
    df = df[(df["ref_len"] <= 30) & (df["alt_len"] <= 30)]
    df["normalized_sig"] = df["ClinicalSignificance"].apply(_normalize_sig)
    df = df[df["normalized_sig"] != "VUS"]
    df = df.drop_duplicates("VariationID")

    path_df   = df[df["normalized_sig"].isin(["Pathogenic", "Likely Pathogenic"])]
    benign_df = df[df["normalized_sig"].isin(["Benign", "Likely Benign"])]
    print(f"  Available — pathogenic: {len(path_df):,}  benign: {len(benign_df):,}")
    return path_df, benign_df


def df_to_variant_list(df: pd.DataFrame, n: int) -> list:
    sample = df.sample(min(n, len(df)), random_state=RANDOM_SEED)
    out = []
    for _, row in sample.iterrows():
        out.append({
            "variation_id":     str(row.get("VariationID", "")),
            "gene":             str(row["GeneSymbol"]),
            "chromosome":       str(row["Chromosome"]),
            "position":         int(row["PositionVCF"]),
            "reference_allele": str(row["ReferenceAlleleVCF"]),
            "alternate_allele": str(row["AlternateAlleleVCF"]),
            "variant_name":     str(row["Name"])[:60],
            "variant_type":     str(row["Type"]),
            "clinical_significance": str(row["ClinicalSignificance"]),
            "review_stars":     _get_review_stars(row["ReviewStatus"]),
            "expected":         str(row["normalized_sig"]),
        })
    return out


def run():
    print("=" * 72)
    print("REAL DATA CONTRADICTION DETECTION VALIDATION")
    print("ClinVar export (local) + gnomAD API (live)")
    print("=" * 72 + "\n")

    path_df, benign_df = load_variants()
    detector = ContradictionDetector()
    gnomad   = GnomADFetcher()

    pathogenic_vars = df_to_variant_list(path_df,   MAX_PER_CLASS)
    benign_vars     = df_to_variant_list(benign_df, MAX_PER_CLASS)

    # ── Build test cases ──────────────────────────────────────────────────────
    # Contradiction cases: ML disagrees with real ClinVar expert classification
    # Control cases:       ML agrees with real ClinVar expert classification
    test_cases = []

    for v in benign_vars:
        # Contradiction: real ClinVar=Benign, ML says Pathogenic
        test_cases.append({**v,
            "ml_prediction": "Pathogenic", "pathogenic_prob": 0.82, "ml_confidence": 82.0,
            "expected_flag": True, "scenario": "ML=Path vs ClinVar=Benign"})

    for v in pathogenic_vars:
        # Contradiction: real ClinVar=Pathogenic, ML says Benign
        test_cases.append({**v,
            "ml_prediction": "Benign", "pathogenic_prob": 0.11, "ml_confidence": 89.0,
            "expected_flag": True, "scenario": "ML=Benign vs ClinVar=Pathogenic"})

    for v in pathogenic_vars:
        # Control: ML agrees with ClinVar=Pathogenic
        test_cases.append({**v,
            "ml_prediction": "Pathogenic", "pathogenic_prob": 0.85, "ml_confidence": 85.0,
            "expected_flag": False, "scenario": "ML agrees ClinVar=Pathogenic"})

    for v in benign_vars:
        # Control: ML agrees with ClinVar=Benign
        test_cases.append({**v,
            "ml_prediction": "Benign", "pathogenic_prob": 0.10, "ml_confidence": 90.0,
            "expected_flag": False, "scenario": "ML agrees ClinVar=Benign"})

    n_conflict = sum(t["expected_flag"] for t in test_cases)
    n_control  = sum(not t["expected_flag"] for t in test_cases)
    print(f"  Test cases: {len(test_cases)}  "
          f"(contradiction={n_conflict}, control={n_control})\n")
    print(f"  {'✓/✗':6} {'Gene':10} {'Expected':8} {'Detected':8} {'Sev':8}  Scenario")
    print("  " + "─" * 88)

    results = []
    TP = TN = FP = FN = 0

    for tc in test_cases:
        gdata = gnomad.get_variant_frequency(
            chromosome=tc["chromosome"],
            position=tc["position"],
            reference=tc["reference_allele"],
            alternate=tc["alternate_allele"],
            genome_version="GRCh38",
        )

        clinvar_data = {"variants": [{
            "clinical_significance": tc["clinical_significance"],
            "review_stars":          tc["review_stars"],
            "variant_name":          tc["variant_name"],
        }]}

        result = detector.detect_contradictions(
            ml_prediction=tc["ml_prediction"],
            ml_confidence=tc["ml_confidence"],
            pathogenic_prob=tc["pathogenic_prob"],
            clinvar_data=clinvar_data,
            gnomad_data=gdata,
            gene=tc["gene"],
            consequence=tc.get("variant_type", "missense_variant"),
        )

        detected  = result.get("has_contradictions", False)
        severity  = result.get("severity", "none")
        expected  = tc["expected_flag"]

        if   expected and     detected: TP += 1; status = "TP ✓"
        elif not expected and not detected: TN += 1; status = "TN ✓"
        elif expected and not detected: FN += 1; status = "FN ✗"
        else:                           FP += 1; status = "FP ✗"

        exp_str = "CONFLICT" if expected else "OK"
        det_str = "YES" if detected else "NO"
        print(f"  {status:6} {tc['gene']:10} {exp_str:8} {det_str:8} {str(severity):8}  {tc['scenario']}")

        results.append({
            "gene":           tc["gene"],
            "clinvar_sig":    tc["clinical_significance"],
            "ml_prediction":  tc["ml_prediction"],
            "scenario":       tc["scenario"],
            "expected_flag":  expected,
            "detected":       detected,
            "severity":       severity,
            "gnomad_af":      gdata.get("allele_frequency"),
        })

    total       = len(results)
    sensitivity = TP / (TP + FN) * 100 if (TP + FN) > 0 else 0
    specificity = TN / (TN + FP) * 100 if (TN + FP) > 0 else 0
    precision   = TP / (TP + FP) * 100 if (TP + FP) > 0 else 0
    f1          = (2 * precision * sensitivity / (precision + sensitivity)
                   if (precision + sensitivity) > 0 else 0)

    print("\n" + "=" * 72)
    print("RESULTS")
    print("=" * 72)
    print(f"  Total test cases : {total}")
    print(f"  TP={TP}  TN={TN}  FP={FP}  FN={FN}")
    print(f"  Sensitivity      : {sensitivity:.1f}%")
    print(f"  Specificity      : {specificity:.1f}%")
    print(f"  Precision        : {precision:.1f}%")
    print(f"  F1 Score         : {f1:.1f}%")

    _generate_figure(results, TP, TN, FP, FN,
                     sensitivity, specificity, precision, f1, total)

    output = {
        "data_source": "data/processed/epilepsy_variants_all.csv + gnomAD API",
        "total": total, "TP": TP, "TN": TN, "FP": FP, "FN": FN,
        "sensitivity": round(sensitivity, 2), "specificity": round(specificity, 2),
        "precision": round(precision, 2), "f1": round(f1, 2),
        "results": results,
    }
    out_json = OUTPUT_DIR / "real_contradiction_results.json"
    with open(out_json, "w") as f:
        json.dump(output, f, indent=2)
    print(f"\n  Results saved → {out_json}")
    return output


def _generate_figure(results, TP, TN, FP, FN,
                     sensitivity, specificity, precision, f1, total):
    fig, axes = plt.subplots(1, 3, figsize=(16, 6))
    fig.suptitle(
        "Contradiction Detection — Real ClinVar + gnomAD Evidence\n"
        f"(n={total} variants, {TP+FN} contradiction cases, {TN+FP} controls)",
        fontsize=12, fontweight="bold"
    )

    ax = axes[0]
    cm = np.array([[TP, FN], [FP, TN]])
    ax.imshow(cm, cmap="Blues", vmin=0)
    ax.set_xticks([0, 1]); ax.set_yticks([0, 1])
    ax.set_xticklabels(["Predicted\nConflict", "Predicted\nOK"], fontsize=10)
    ax.set_yticklabels(["Actually\nConflict", "Actually\nOK"],   fontsize=10)
    ax.set_title("Confusion Matrix\n(Real Data)", fontweight="bold")
    for i in range(2):
        for j in range(2):
            ax.text(j, i, str(cm[i, j]), ha="center", va="center",
                    fontsize=22, fontweight="bold",
                    color="white" if cm[i, j] > cm.max() / 1.5 else "black")

    ax2 = axes[1]
    metrics = {"Sensitivity": sensitivity, "Specificity": specificity,
               "Precision": precision, "F1 Score": f1}
    bars = ax2.bar(metrics.keys(), [v/100 for v in metrics.values()],
                   color=["#E53935","#43A047","#1976D2","#7B1FA2"], alpha=0.85)
    ax2.set_ylim(0, 1.2); ax2.set_ylabel("Rate")
    ax2.set_title("Detection Metrics\n(Real Variant Data)", fontweight="bold")
    ax2.axhline(0.8, color="gray", linestyle="--", alpha=0.5, label="80% threshold")
    ax2.legend(fontsize=8)
    for bar, val in zip(bars, metrics.values()):
        ax2.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.02,
                 f"{val:.1f}%", ha="center", fontsize=12, fontweight="bold")
    ax2.tick_params(axis="x", labelsize=9)

    ax3 = axes[2]
    scenarios = {}
    for r in results:
        sc = r["scenario"]
        if sc not in scenarios:
            scenarios[sc] = {"correct": 0, "total": 0}
        scenarios[sc]["total"] += 1
        if (r["expected_flag"] and r["detected"]) or \
           (not r["expected_flag"] and not r["detected"]):
            scenarios[sc]["correct"] += 1

    labels = list(scenarios.keys())
    accs   = [scenarios[s]["correct"] / scenarios[s]["total"] * 100 for s in labels]
    colors = ["#E53935","#FF7043","#43A047","#66BB6A"][:len(labels)]
    ax3.barh(range(len(labels)), accs, color=colors, alpha=0.85)
    ax3.set_yticks(range(len(labels)))
    ax3.set_yticklabels([l.replace(" vs ", "\nvs ") for l in labels], fontsize=8)
    ax3.set_xlim(0, 115); ax3.set_xlabel("Accuracy (%)")
    ax3.set_title("Per-Scenario Accuracy\n(Real Data)", fontweight="bold")
    for i, acc in enumerate(accs):
        ax3.text(acc + 1, i, f"{acc:.0f}%", va="center", fontsize=10, fontweight="bold")

    plt.tight_layout()
    out = OUTPUT_DIR / "real_contradiction_validation.png"
    plt.savefig(out, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  Figure saved  → {out}")


if __name__ == "__main__":
    run()
