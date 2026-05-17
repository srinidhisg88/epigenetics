"""
Validation Script for Epilepsy Diagnostic Assistant.

Tests the full pipeline (ML prediction + RAG + SHAP + gnomAD + contradictions)
against 50 benchmark variants (2 per gene, 26 genes) with known classifications.

Usage:
    python validation/validate_system.py [--api-url URL] [--skip-rag] [--verbose]
"""

import json
import sys
import time
import argparse
from pathlib import Path
from datetime import datetime

import requests

# Default API URL
DEFAULT_API_URL = "http://localhost:8000"

BENCHMARK_FILE = Path(__file__).parent / "benchmark_variants.json"


def load_benchmark_variants():
    """Load benchmark variants from JSON file."""
    with open(BENCHMARK_FILE, "r") as f:
        return json.load(f)


def test_variant(api_url: str, variant: dict, verbose: bool = False) -> dict:
    """
    Test a single variant against the API.

    Returns a result dict with pass/fail and details.
    """
    payload = {
        "gene": variant["gene"],
        "chromosome": variant["chromosome"],
        "position": variant.get("position"),
        "reference_allele": variant["reference_allele"],
        "alternate_allele": variant["alternate_allele"],
        "consequence": variant["consequence"],
        "variant_type": variant["variant_type"],
        "review_status": variant["review_status"],
        "origin": variant["origin"],
    }

    try:
        start_time = time.time()
        response = requests.post(
            f"{api_url}/analyze_variant",
            json=payload,
            timeout=120,
        )
        elapsed = time.time() - start_time

        if response.status_code != 200:
            return {
                "id": variant["id"],
                "gene": variant["gene"],
                "status": "ERROR",
                "error": f"HTTP {response.status_code}: {response.text[:200]}",
                "elapsed": elapsed,
            }

        data = response.json()

        # Check ML prediction correctness
        predicted = data["prediction"]
        expected = variant["expected_classification"]
        ml_correct = predicted == expected

        # Check new features presence
        has_shap = data.get("shap_explanation") is not None
        has_gnomad = data.get("gnomad_data") is not None
        has_contradictions = data.get("contradictions") is not None
        has_uncertainty = data.get("uncertainty_analysis") is not None
        has_rag = data.get("rag_response") is not None and data["rag_response"] != ""

        # Check if RAG triggers for uncertain predictions
        pathogenic_prob = data.get("pathogenic_probability", 0)
        is_uncertain = 0.3 <= pathogenic_prob <= 0.7

        result = {
            "id": variant["id"],
            "gene": variant["gene"],
            "expected": expected,
            "predicted": predicted,
            "ml_correct": ml_correct,
            "confidence": data.get("confidence", 0),
            "pathogenic_prob": pathogenic_prob,
            "is_uncertain": is_uncertain,
            "has_shap": has_shap,
            "has_gnomad": has_gnomad,
            "has_contradictions": has_contradictions,
            "has_uncertainty": has_uncertainty,
            "has_rag": has_rag,
            "elapsed": round(elapsed, 2),
            "status": "PASS" if ml_correct else "FAIL",
        }

        if verbose:
            if has_shap and data["shap_explanation"]:
                top = data["shap_explanation"].get("top_contributors", [])
                if top:
                    result["top_shap_feature"] = top[0].get("description", "")

            if has_gnomad and data["gnomad_data"]:
                result["gnomad_af"] = data["gnomad_data"].get("allele_frequency")
                result["gnomad_found"] = data["gnomad_data"].get("found", False)

            if has_contradictions and data["contradictions"]:
                result["contradiction_count"] = data["contradictions"].get("count", 0)
                result["contradiction_severity"] = data["contradictions"].get("severity", "none")

        return result

    except requests.exceptions.ConnectionError:
        return {
            "id": variant["id"],
            "gene": variant["gene"],
            "status": "CONNECTION_ERROR",
            "error": f"Cannot connect to {api_url}",
            "elapsed": 0,
        }
    except Exception as e:
        return {
            "id": variant["id"],
            "gene": variant["gene"],
            "status": "ERROR",
            "error": str(e),
            "elapsed": 0,
        }


def run_validation(api_url: str, skip_rag: bool = False, verbose: bool = False):
    """Run full validation suite."""
    print("=" * 70)
    print("EPILEPSY DIAGNOSTIC ASSISTANT — VALIDATION SUITE")
    print(f"API: {api_url}")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)

    # Load variants
    variants = load_benchmark_variants()
    print(f"\nLoaded {len(variants)} benchmark variants across {len(set(v['gene'] for v in variants))} genes\n")

    # Check API health
    try:
        health = requests.get(f"{api_url}/health", timeout=10)
        if health.status_code == 200:
            h = health.json()
            print(f"API Health: {h.get('status', 'unknown')}")
            print(f"  ML Model: {'loaded' if h.get('model_loaded') else 'NOT loaded'}")
            print(f"  RAG: {'loaded' if h.get('rag_loaded') else 'NOT loaded'}")
        print()
    except Exception:
        print("Warning: Could not check API health\n")

    # Run tests
    results = []
    for i, variant in enumerate(variants, 1):
        label = f"[{i}/{len(variants)}] {variant['id']}"
        print(f"  Testing {label}...", end=" ", flush=True)

        result = test_variant(api_url, variant, verbose=verbose)
        results.append(result)

        if result["status"] == "PASS":
            print(f"✓ PASS ({result.get('confidence', 0):.1f}% conf, {result['elapsed']}s)")
        elif result["status"] == "FAIL":
            print(f"✗ FAIL — expected {result['expected']}, got {result['predicted']} "
                  f"({result.get('confidence', 0):.1f}% conf)")
        else:
            print(f"⚠ {result['status']}: {result.get('error', 'unknown')[:60]}")

    # Compute metrics
    print("\n" + "=" * 70)
    print("RESULTS SUMMARY")
    print("=" * 70)

    total = len(results)
    tested = [r for r in results if r["status"] in ("PASS", "FAIL")]
    errors = [r for r in results if r["status"] not in ("PASS", "FAIL")]
    correct = [r for r in tested if r["ml_correct"]]

    # Overall accuracy
    if tested:
        accuracy = len(correct) / len(tested) * 100
        print(f"\nML Prediction Accuracy: {len(correct)}/{len(tested)} = {accuracy:.1f}%")
    else:
        accuracy = 0
        print("\nNo variants were successfully tested!")

    # Per-class metrics
    pathogenic_variants = [r for r in tested if r["expected"] == "Pathogenic"]
    benign_variants = [r for r in tested if r["expected"] == "Benign"]

    path_correct = sum(1 for r in pathogenic_variants if r["ml_correct"])
    benign_correct = sum(1 for r in benign_variants if r["ml_correct"])

    if pathogenic_variants:
        sensitivity = path_correct / len(pathogenic_variants) * 100
        print(f"Sensitivity (Pathogenic): {path_correct}/{len(pathogenic_variants)} = {sensitivity:.1f}%")
    if benign_variants:
        specificity = benign_correct / len(benign_variants) * 100
        print(f"Specificity (Benign): {benign_correct}/{len(benign_variants)} = {specificity:.1f}%")

    # Feature availability
    print(f"\n--- Feature Coverage ---")
    shap_count = sum(1 for r in tested if r.get("has_shap"))
    gnomad_count = sum(1 for r in tested if r.get("has_gnomad"))
    contra_count = sum(1 for r in tested if r.get("has_contradictions"))
    unc_count = sum(1 for r in tested if r.get("has_uncertainty"))
    rag_count = sum(1 for r in tested if r.get("has_rag"))

    print(f"SHAP Explanations:      {shap_count}/{len(tested)} variants")
    print(f"gnomAD Data:            {gnomad_count}/{len(tested)} variants")
    print(f"Contradiction Detection: {contra_count}/{len(tested)} variants")
    print(f"Uncertainty Analysis:    {unc_count}/{len(tested)} variants")
    print(f"RAG Responses:          {rag_count}/{len(tested)} variants")

    # Uncertain predictions
    uncertain = [r for r in tested if r.get("is_uncertain")]
    if uncertain:
        print(f"\n--- Uncertain Predictions (0.3-0.7 range) ---")
        print(f"Count: {len(uncertain)}/{len(tested)}")
        for r in uncertain:
            print(f"  {r['id']}: prob={r['pathogenic_prob']:.3f}, "
                  f"rag={'yes' if r.get('has_rag') else 'no'}, "
                  f"uncertainty_analysis={'yes' if r.get('has_uncertainty') else 'no'}")

    # Per-gene breakdown
    print(f"\n--- Per-Gene Results ---")
    genes = sorted(set(r["gene"] for r in tested))
    for gene in genes:
        gene_results = [r for r in tested if r["gene"] == gene]
        gene_correct = sum(1 for r in gene_results if r["ml_correct"])
        status = "✓" if gene_correct == len(gene_results) else "✗"
        print(f"  {status} {gene}: {gene_correct}/{len(gene_results)}")

    # Errors
    if errors:
        print(f"\n--- Errors ({len(errors)}) ---")
        for r in errors:
            print(f"  {r['id']}: {r.get('error', 'unknown')[:80]}")

    # Timing
    avg_time = sum(r.get("elapsed", 0) for r in results) / max(len(results), 1)
    print(f"\nAverage response time: {avg_time:.2f}s")
    print(f"Total test time: {sum(r.get('elapsed', 0) for r in results):.1f}s")

    # Save results
    output_file = Path(__file__).parent / "validation_results.json"
    output = {
        "timestamp": datetime.now().isoformat(),
        "api_url": api_url,
        "total_variants": total,
        "tested": len(tested),
        "accuracy": round(accuracy, 2),
        "sensitivity": round(sensitivity, 2) if pathogenic_variants else None,
        "specificity": round(specificity, 2) if benign_variants else None,
        "feature_coverage": {
            "shap": shap_count,
            "gnomad": gnomad_count,
            "contradictions": contra_count,
            "uncertainty": unc_count,
            "rag": rag_count,
        },
        "results": results,
    }

    with open(output_file, "w") as f:
        json.dump(output, f, indent=2)
    print(f"\nDetailed results saved to: {output_file}")

    return accuracy


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Validate Epilepsy Diagnostic Assistant")
    parser.add_argument("--api-url", default=DEFAULT_API_URL, help="API base URL")
    parser.add_argument("--skip-rag", action="store_true", help="Skip RAG validation")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    args = parser.parse_args()

    accuracy = run_validation(args.api_url, args.skip_rag, args.verbose)

    sys.exit(0 if accuracy >= 80 else 1)
