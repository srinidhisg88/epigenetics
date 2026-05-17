"""
Real Data ACMG Validation.

Data sources (NO mock data):
  - ClinVar classifications  : data/processed/epilepsy_variants_all.csv
                                (local ClinVar export, filtered to 2+ star review)
  - gnomAD allele frequencies : live gnomAD GraphQL API (cached 30 days)

Validates our ACMGClassifier against expert ClinVar classifications
across 14 epilepsy genes and up to 200 variants.
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

from backend.acmg_classifier import ACMGClassifier
from backend.gnomad_fetcher import GnomADFetcher

DATA_FILE  = BASE_DIR / "data" / "processed" / "epilepsy_variants_all.csv"
OUTPUT_DIR = Path(__file__).parent / "results"
OUTPUT_DIR.mkdir(exist_ok=True)

EPILEPSY_GENES = [
    "SCN1A", "SCN2A", "SCN8A", "KCNQ2",
    "TSC1",  "TSC2",  "CDKL5", "STXBP1",
    "GABRA1","GABRG2","MECP2", "SLC2A1",
    "CHD2",  "PCDH19",
]

ACCEPTABLE = {
    "Pathogenic":        {"Pathogenic", "Likely Pathogenic"},
    "Likely Pathogenic": {"Pathogenic", "Likely Pathogenic"},
    "Benign":            {"Benign", "Likely Benign"},
    "Likely Benign":     {"Benign", "Likely Benign"},
}

MAX_PER_CLASS = 100   # up to 100 pathogenic + 100 benign = 200 total
RANDOM_SEED   = 42


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _get_review_stars(review_status: str) -> int:
    r = str(review_status).lower()
    if "practice guideline"  in r: return 4
    if "expert panel"        in r: return 3
    if "multiple submitters" in r and "no conflicts" in r: return 2
    if "single submitter"    in r and "criteria provided" in r: return 1
    return 0


def _normalize_sig(sig: str) -> str:
    s = str(sig).lower()
    if "likely pathogenic"      in s: return "Likely Pathogenic"
    if "pathogenic/likely"      in s: return "Likely Pathogenic"
    if "likely benign"          in s: return "Likely Benign"
    if "benign/likely"          in s: return "Likely Benign"
    if "pathogenic"             in s: return "Pathogenic"
    if "benign"                 in s: return "Benign"
    return "VUS"


def _infer_consequence(name: str, variant_type: str) -> str:
    """Parse consequence from HGVS Name and ClinVar Type fields."""
    n = str(name).lower()
    t = str(variant_type).lower()

    if "ter" in n or "?" in n and "stop" in n: return "stop_gained"
    if "(p." in n and "ter" in n:              return "stop_gained"
    if "frameshift" in n or "(p." in n and "fs" in n: return "frameshift_variant"
    if "fs)"   in n or "fs*" in n:             return "frameshift_variant"
    if "splice" in n:                          return "splice_site_variant"
    if "+1"    in n or "-1" in n:              return "splice_site_variant"
    if "del"   in n and "ins" not in n and t in ("deletion", "microsatellite", "indel"):
        return "frameshift_variant"
    if "dup"   in n:                           return "frameshift_variant"
    if "="     in n:                           return "synonymous_variant"
    if "(p."   in n and t == "single nucleotide variant":
        return "missense_variant"
    if t == "deletion":                        return "frameshift_variant"
    return "missense_variant"


def _infer_origin(origin_str: str) -> str:
    o = str(origin_str).lower()
    if "de novo" in o or "denovo" in o: return "de_novo"
    return "germline"


# ─────────────────────────────────────────────────────────────────────────────
# Load + filter local ClinVar data
# ─────────────────────────────────────────────────────────────────────────────

def load_variants() -> pd.DataFrame:
    print(f"Loading: {DATA_FILE}")
    df = pd.read_csv(DATA_FILE, low_memory=False)
    print(f"  Total rows: {len(df):,}")

    # GRCh38 only (needed for gnomAD v4 coordinates)
    df = df[df["Assembly"] == "GRCh38"]

    # Epilepsy genes only
    df = df[df["GeneSymbol"].isin(EPILEPSY_GENES)]

    # 2+ star review only
    df = df[df["ReviewStatus"].str.contains(
        "multiple submitters.*no conflicts|expert panel|practice guideline",
        case=False, na=False, regex=True
    )]

    # Skip conflicting interpretations
    df = df[~df["ClinicalSignificance"].str.contains(
        "conflicting|uncertain|not provided|other",
        case=False, na=False
    )]

    # Must have usable coordinates
    df = df[df["PositionVCF"].notna() & df["ReferenceAlleleVCF"].notna() & df["AlternateAlleleVCF"].notna()]
    df = df[df["Chromosome"].notna()]

    # Skip large alleles (gnomAD won't have them)
    df["ref_len"] = df["ReferenceAlleleVCF"].astype(str).str.len()
    df["alt_len"] = df["AlternateAlleleVCF"].astype(str).str.len()
    df = df[(df["ref_len"] <= 30) & (df["alt_len"] <= 30)]

    # Normalize significance
    df["normalized_sig"] = df["ClinicalSignificance"].apply(_normalize_sig)
    df = df[df["normalized_sig"] != "VUS"]

    print(f"  After filtering (GRCh38 + 2★ + epilepsy genes): {len(df):,}")
    print(f"  Pathogenic/LP: {(df['normalized_sig'].isin(['Pathogenic','Likely Pathogenic'])).sum():,}")
    print(f"  Benign/LB:     {(df['normalized_sig'].isin(['Benign','Likely Benign'])).sum():,}")
    return df


def sample_variants(df: pd.DataFrame) -> list:
    """Sample balanced set of pathogenic + benign variants, de-duplicated."""
    random.seed(RANDOM_SEED)

    path_df   = df[df["normalized_sig"].isin(["Pathogenic", "Likely Pathogenic"])]
    benign_df = df[df["normalized_sig"].isin(["Benign", "Likely Benign"])]

    # De-duplicate by VariationID
    path_df   = path_df.drop_duplicates("VariationID")
    benign_df = benign_df.drop_duplicates("VariationID")

    path_sample   = path_df.sample(min(MAX_PER_CLASS, len(path_df)),   random_state=RANDOM_SEED)
    benign_sample = benign_df.sample(min(MAX_PER_CLASS, len(benign_df)), random_state=RANDOM_SEED)

    combined = pd.concat([path_sample, benign_sample])
    print(f"\n  Sampled: {len(path_sample)} pathogenic/LP + {len(benign_sample)} benign/LB = {len(combined)} total")

    variants = []
    for _, row in combined.iterrows():
        variants.append({
            "variation_id":     str(row.get("VariationID", "")),
            "gene":             str(row["GeneSymbol"]),
            "chromosome":       str(row["Chromosome"]),
            "position":         int(row["PositionVCF"]),
            "reference_allele": str(row["ReferenceAlleleVCF"]),
            "alternate_allele": str(row["AlternateAlleleVCF"]),
            "variant_name":     str(row["Name"]),
            "variant_type":     str(row["Type"]),
            "consequence":      _infer_consequence(row["Name"], row["Type"]),
            "origin":           _infer_origin(str(row.get("Origin", "germline"))),
            "clinical_significance": str(row["ClinicalSignificance"]),
            "review_status":    str(row["ReviewStatus"]),
            "review_stars":     _get_review_stars(row["ReviewStatus"]),
            "expected":         str(row["normalized_sig"]),
        })
    return variants


# ─────────────────────────────────────────────────────────────────────────────
# Main validation
# ─────────────────────────────────────────────────────────────────────────────

def run():
    print("=" * 72)
    print("REAL DATA ACMG VALIDATION")
    print("ClinVar export (local) + gnomAD API (live)")
    print("=" * 72 + "\n")

    df       = load_variants()
    variants = sample_variants(df)

    clf    = ACMGClassifier()
    gnomad = GnomADFetcher()

    print("\nRunning ACMG classifier (querying gnomAD for each variant)...\n")
    print(f"  {'✓/✗':4} {'Gene':10} {'Consequence':22} "
          f"{'ClinVar (★)':18} {'ACMG Result':22} {'Score':>6}  gnomAD AF")
    print("  " + "─" * 105)

    results     = []
    tier_counts = Counter()
    correct     = 0
    gnomad_hits = 0

    for v in variants:
        # Real gnomAD query
        gdata = gnomad.get_variant_frequency(
            chromosome=v["chromosome"],
            position=v["position"],
            reference=v["reference_allele"],
            alternate=v["alternate_allele"],
            genome_version="GRCh38",
        )
        if gdata.get("found"):
            gnomad_hits += 1

        # Build ClinVar evidence from local data
        clinvar_data = {
            "variants": [{
                "clinical_significance": v["clinical_significance"],
                "review_stars":          v["review_stars"],
                "variant_name":          v["variant_name"],
            }]
        }

        # Run ACMG (no SHAP — not available in batch validation)
        r = clf.classify(
            gene=v["gene"],
            consequence=v["consequence"],
            origin=v["origin"],
            gnomad_data=gdata,
            clinvar_data=clinvar_data,
            shap_data=None,
            variant_type=v["variant_type"],
            reference_allele=v["reference_allele"],
            alternate_allele=v["alternate_allele"],
        )

        acmg_tier  = r["classification"]
        expected   = v["expected"]
        is_correct = acmg_tier in ACCEPTABLE.get(expected, {expected})

        tier_counts[acmg_tier] += 1
        if is_correct:
            correct += 1

        af     = gdata.get("allele_frequency")
        af_str = f"{af:.2e}" if af else "absent"
        status = "✓" if is_correct else "✗"
        stars  = v["review_stars"]

        print(f"  {status:4} {v['gene']:10} {v['consequence']:22} "
              f"{expected+' ('+str(stars)+'★)':18} "
              f"{acmg_tier:22} {r['total_score']:>+6d}  {af_str}")

        results.append({
            "variation_id":  v["variation_id"],
            "gene":          v["gene"],
            "variant_name":  v["variant_name"][:60],
            "consequence":   v["consequence"],
            "expected":      expected,
            "review_stars":  stars,
            "acmg_tier":     acmg_tier,
            "score":         r["total_score"],
            "criteria_met":  [c["code"] for c in r["criteria_met"]],
            "correct":       is_correct,
            "gnomad_af":     af,
            "gnomad_found":  gdata.get("found", False),
        })

    # ── Summary ───────────────────────────────────────────────────────────────
    total      = len(results)
    accuracy   = correct / total * 100 if total else 0

    path_res   = [r for r in results if r["expected"] in ("Pathogenic",    "Likely Pathogenic")]
    benign_res = [r for r in results if r["expected"] in ("Benign",        "Likely Benign")]
    path_acc   = sum(r["correct"] for r in path_res)   / len(path_res)   * 100 if path_res   else 0
    benign_acc = sum(r["correct"] for r in benign_res) / len(benign_res) * 100 if benign_res else 0

    print("\n" + "=" * 72)
    print("RESULTS")
    print("=" * 72)
    print(f"  Total variants (real ClinVar + gnomAD)  : {total}")
    print(f"  Overall accuracy                        : {correct}/{total} = {accuracy:.1f}%")
    print(f"  Pathogenic/LP accuracy                  : {sum(r['correct'] for r in path_res)}/{len(path_res)} = {path_acc:.1f}%")
    print(f"  Benign/LB accuracy                      : {sum(r['correct'] for r in benign_res)}/{len(benign_res)} = {benign_acc:.1f}%")
    print(f"  Variants with real gnomAD data           : {gnomad_hits}/{total}")
    print(f"\n  ACMG Tier Distribution:")
    for tier in ["Pathogenic","Likely Pathogenic","VUS","Likely Benign","Benign"]:
        n = tier_counts[tier]
        if n > 0:
            print(f"    {tier:22s}: {n:3d} ({n/total*100:.0f}%)")

    _generate_figure(results, tier_counts, correct, total,
                     path_acc, benign_acc, gnomad_hits)

    output = {
        "data_source":         "data/processed/epilepsy_variants_all.csv + gnomAD API",
        "total":               total,
        "correct":             correct,
        "accuracy":            round(accuracy, 2),
        "pathogenic_accuracy": round(path_acc, 2),
        "benign_accuracy":     round(benign_acc, 2),
        "gnomad_hits":         gnomad_hits,
        "tier_distribution":   dict(tier_counts),
        "results":             results,
    }
    out_json = OUTPUT_DIR / "real_acmg_results.json"
    with open(out_json, "w") as f:
        json.dump(output, f, indent=2)
    print(f"\n  Results saved → {out_json}")
    return output


# ─────────────────────────────────────────────────────────────────────────────
# Figure
# ─────────────────────────────────────────────────────────────────────────────

def _generate_figure(results, tier_counts, correct, total,
                     path_acc, benign_acc, gnomad_hits):
    fig, axes = plt.subplots(1, 3, figsize=(18, 6))
    fig.suptitle(
        "Automated ACMG/AMP Classifier — Validation on Real ClinVar Data\n"
        "(Local ClinVar export + live gnomAD API, n=" + str(total) + " variants)",
        fontsize=12, fontweight="bold"
    )

    path_res   = [r for r in results if r["expected"] in ("Pathogenic",    "Likely Pathogenic")]
    benign_res = [r for r in results if r["expected"] in ("Benign",        "Likely Benign")]
    tier_keys  = ["Pathogenic","Likely Pathogenic","VUS","Likely Benign","Benign"]

    # ── Plot 1: Tier distribution ─────────────────────────────────────────────
    ax = axes[0]
    path_tc  = {t: sum(1 for r in path_res   if r["acmg_tier"] == t) for t in tier_keys}
    benign_tc = {t: sum(1 for r in benign_res if r["acmg_tier"] == t) for t in tier_keys}
    x  = np.arange(len(tier_keys)); w = 0.35
    b1 = ax.bar(x - w/2, [path_tc[t]   for t in tier_keys], w,
                label="Expected Path/LP", color="#E53935", alpha=0.85)
    b2 = ax.bar(x + w/2, [benign_tc[t] for t in tier_keys], w,
                label="Expected Benign/LB", color="#43A047", alpha=0.85)
    ax.set_xticks(x)
    ax.set_xticklabels(["Pathogenic","Likely\nPath.","VUS","Likely\nBenign","Benign"], fontsize=8)
    ax.set_ylabel("Count"); ax.legend(fontsize=8)
    ax.set_title("ACMG Tier Distribution\n(Real ClinVar Variants)", fontweight="bold")
    ax.axvspan(-0.5, 1.5, alpha=0.05, color="#E53935")
    ax.axvspan(2.5,  4.5, alpha=0.05, color="#43A047")
    for bar in list(b1) + list(b2):
        h = bar.get_height()
        if h > 0:
            ax.text(bar.get_x() + bar.get_width()/2, h + 0.2,
                    str(int(h)), ha="center", fontsize=8, fontweight="bold")

    # ── Plot 2: Accuracy metrics ──────────────────────────────────────────────
    ax2 = axes[1]
    metrics = {
        "Overall\nAccuracy":    correct / total * 100,
        "Pathogenic\nAccuracy": path_acc,
        "Benign\nAccuracy":     benign_acc,
        "gnomAD\nCoverage":    gnomad_hits / total * 100,
    }
    colors = ["#1976D2","#E53935","#43A047","#0288D1"]
    bars = ax2.bar(list(metrics.keys()), [v/100 for v in metrics.values()],
                   color=colors, alpha=0.88, width=0.55)
    ax2.set_ylim(0, 1.22); ax2.set_ylabel("Rate")
    ax2.set_title("Classification Accuracy\n(vs Expert ClinVar Review)", fontweight="bold")
    ax2.axhline(0.8, color="gray", linestyle="--", alpha=0.5, label="80% threshold")
    ax2.legend(fontsize=8)
    for bar, val in zip(bars, metrics.values()):
        ax2.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.02,
                 f"{val:.1f}%", ha="center", fontsize=11, fontweight="bold")
    ax2.tick_params(axis="x", labelsize=8)

    # ── Plot 3: Criteria frequency ────────────────────────────────────────────
    ax3 = axes[2]
    criteria_list = ["PVS1","PS1","PS2","PM1","PM2","PM4","PP3","PP5",
                     "BA1","BS1","BS2","BP4","BP6","BP7"]
    path_freq  = {c: sum(1 for r in path_res   if c in r["criteria_met"]) for c in criteria_list}
    benign_freq = {c: sum(1 for r in benign_res if c in r["criteria_met"]) for c in criteria_list}
    active = [c for c in criteria_list if path_freq[c] > 0 or benign_freq[c] > 0]
    if active:
        y = np.arange(len(active))
        ax3.barh(y + 0.2, [path_freq[c]   for c in active], 0.38,
                 label="Pathogenic/LP", color="#E53935", alpha=0.82)
        ax3.barh(y - 0.2, [benign_freq[c] for c in active], 0.38,
                 label="Benign/LB",    color="#43A047", alpha=0.82)
        ax3.set_yticks(y); ax3.set_yticklabels(active, fontsize=9)
        ax3.set_xlabel("Times Criterion Applied")
        ax3.legend(fontsize=8)
    ax3.set_title("ACMG Criteria Frequency\n(Pathogenic vs Benign)", fontweight="bold")

    plt.tight_layout()
    out = OUTPUT_DIR / "real_acmg_validation.png"
    plt.savefig(out, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  Figure saved  → {out}")


if __name__ == "__main__":
    run()
