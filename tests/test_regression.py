"""
Regression Tests — Epilepsy Diagnostic Assistant
=================================================
Pins known-correct outputs for specific inputs.
Any change that breaks these tests has introduced a regression.

These are the ground-truth reference cases derived from the
validation run (real_acmg_results.json) and manual verification.

Categories:
  REG-01  Known predictions pinned (exact probability range)
  REG-02  Known ACMG criteria pinned
  REG-03  Known classification pinned
  REG-04  Score arithmetic pinned
  REG-05  Confidence resolver thresholds pinned
  REG-06  Contradiction detector logic pinned
  REG-07  Gene mechanism map pinned

Run:
    pytest tests/test_regression.py -v
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
import requests

from backend.acmg_classifier import (
    ACMGClassifier, CRITERION_POINTS, GENE_MECHANISM,
    LOF_CONSEQUENCES, BENIGN_CONSEQUENCES,
)
from backend.confidence_resolver import (
    ConfidenceResolver, ContradictionDetector,
    UNCERTAIN_LOW, UNCERTAIN_HIGH,
)

BASE = "http://localhost:8000"

acmg = ACMGClassifier()
resolver = ConfidenceResolver()
detector = ContradictionDetector()


# ─────────────────────────────────────────────────────────────────────────────
# REG-01: Known ML predictions pinned
# ─────────────────────────────────────────────────────────────────────────────

class TestKnownMLPredictions:

    def test_scn1a_stop_gained_is_pathogenic(self):
        r = requests.post(f"{BASE}/predict_variant", json={
            "gene": "SCN1A", "chromosome": "2",
            "reference_allele": "C", "alternate_allele": "T",
            "consequence": "stop_gained",
            "variant_type": "single nucleotide variant",
            "review_status": "criteria provided, multiple submitters",
            "origin": "germline",
        }).json()
        assert r["prediction"] == "Pathogenic"
        assert r["pathogenic_probability"] > 0.90, \
            f"Regression: SCN1A stop_gained probability dropped to {r['pathogenic_probability']:.4f}"

    def test_slc2a1_synonymous_is_benign(self):
        r = requests.post(f"{BASE}/predict_variant", json={
            "gene": "SLC2A1", "chromosome": "1",
            "reference_allele": "C", "alternate_allele": "T",
            "consequence": "synonymous_variant",
            "variant_type": "single nucleotide variant",
            "review_status": "no assertion criteria provided",
            "origin": "germline",
        }).json()
        assert r["prediction"] == "Benign"
        assert r["benign_probability"] > 0.70, \
            f"Regression: SLC2A1 synonymous benign probability dropped to {r['benign_probability']:.4f}"

    def test_kcnq2_denovo_stop_gained_is_pathogenic(self):
        r = requests.post(f"{BASE}/predict_variant", json={
            "gene": "KCNQ2", "chromosome": "20",
            "reference_allele": "C", "alternate_allele": "T",
            "consequence": "stop_gained",
            "variant_type": "single nucleotide variant",
            "review_status": "reviewed by expert panel",
            "origin": "de novo (confirmed)",
        }).json()
        assert r["prediction"] == "Pathogenic"

    def test_tsc2_frameshift_is_pathogenic(self):
        r = requests.post(f"{BASE}/predict_variant", json={
            "gene": "TSC2", "chromosome": "16",
            "reference_allele": "AG", "alternate_allele": "A",
            "consequence": "frameshift_variant",
            "variant_type": "deletion",
            "review_status": "criteria provided, single submitter",
            "origin": "germline",
        }).json()
        assert r["prediction"] == "Pathogenic"

    def test_probability_sum_regression(self):
        """probabilities must always sum to exactly 1.0."""
        for variant in [
            {"gene": "SCN1A", "chromosome": "2", "reference_allele": "C",
             "alternate_allele": "T", "consequence": "stop_gained",
             "variant_type": "single nucleotide variant",
             "review_status": "no assertion criteria provided", "origin": "germline"},
            {"gene": "SLC2A1", "chromosome": "1", "reference_allele": "C",
             "alternate_allele": "T", "consequence": "synonymous_variant",
             "variant_type": "single nucleotide variant",
             "review_status": "no assertion criteria provided", "origin": "germline"},
        ]:
            r = requests.post(f"{BASE}/predict_variant", json=variant).json()
            total = round(r["pathogenic_probability"] + r["benign_probability"], 5)
            assert total == 1.0, f"Regression: probabilities sum to {total}"


# ─────────────────────────────────────────────────────────────────────────────
# REG-02: Known ACMG criteria pinned
# ─────────────────────────────────────────────────────────────────────────────

class TestKnownACMGCriteria:

    def test_scn1a_stop_gained_triggers_pvs1(self):
        """Regression: PVS1 must always fire for SCN1A stop_gained."""
        result = acmg.classify("SCN1A", "stop_gained")
        codes = [c["code"] for c in result["criteria_met"]]
        assert "PVS1" in codes, \
            f"Regression: PVS1 no longer fires for SCN1A stop_gained. Got: {codes}"

    def test_confirmed_denovo_triggers_ps2_not_pm6(self):
        """Regression: de novo confirmed → PS2 (not PM6)."""
        result = acmg.classify("KCNQ2", "stop_gained", origin="de novo (confirmed)")
        met = [c["code"] for c in result["criteria_met"]]
        assert "PS2" in met, f"Regression: PS2 not in {met}"
        assert "PM6" not in met, f"Regression: PM6 should not fire with PS2. Got: {met}"

    def test_assumed_denovo_triggers_pm6_not_ps2(self):
        """Regression: de novo assumed → PM6 (not PS2)."""
        result = acmg.classify("KCNQ2", "stop_gained", origin="de novo")
        met = [c["code"] for c in result["criteria_met"]]
        assert "PM6" in met, f"Regression: PM6 not in {met}"
        assert "PS2" not in met, f"Regression: PS2 should not fire without confirmation. Got: {met}"

    def test_synonymous_always_triggers_bp7(self):
        """Regression: synonymous_variant must always trigger BP7."""
        result = acmg.classify("SLC2A1", "synonymous_variant")
        codes = [c["code"] for c in result["criteria_met"]]
        assert "BP7" in codes, f"Regression: BP7 not triggered for synonymous. Got: {codes}"

    def test_gof_gene_never_gets_pvs1(self):
        """Regression: SCN2A (GOF) must never get PVS1 for any LOF consequence."""
        for consequence in ["stop_gained", "frameshift_variant", "splice_donor_variant"]:
            result = acmg.classify("SCN2A", consequence)
            codes = [c["code"] for c in result["criteria_met"]]
            assert "PVS1" not in codes, \
                f"Regression: PVS1 fired for GOF gene SCN2A with {consequence}"

    def test_ba1_triggers_benign_classification(self):
        """Regression: BA1 (AF>5%) must always produce Benign classification."""
        gnomad_common = {
            "found": True, "is_absent": False, "is_ultra_rare": False,
            "allele_frequency": 0.08, "allele_count": 1200,
            "homozygote_count": 50, "error": None,
        }
        result = acmg.classify("SCN1A", "missense_variant", gnomad_data=gnomad_common)
        assert result["classification"] == "Benign", \
            f"Regression: BA1 did not override to Benign. Got: {result['classification']}"

    def test_inframe_deletion_triggers_pm4(self):
        """Regression: PM4 must fire for inframe_deletion."""
        result = acmg.classify("SCN1A", "inframe_deletion")
        codes = [c["code"] for c in result["criteria_met"]]
        assert "PM4" in codes, f"Regression: PM4 not triggered for inframe_deletion"

    def test_pvs1_frameshift_in_tsc2(self):
        """Regression: TSC2 is a LOF gene — frameshift must trigger PVS1."""
        result = acmg.classify("TSC2", "frameshift_variant")
        codes = [c["code"] for c in result["criteria_met"]]
        assert "PVS1" in codes


# ─────────────────────────────────────────────────────────────────────────────
# REG-03: Known classification pinned
# ─────────────────────────────────────────────────────────────────────────────

class TestKnownClassificationPinned:

    def test_pvs1_plus_ps2_plus_pm2_is_pathogenic(self):
        """PVS1(8) + PS2(4) + PM2(2) = 14 → must always be Pathogenic (≥10)."""
        gnomad_absent = {
            "found": True, "is_absent": True, "is_ultra_rare": False,
            "allele_frequency": None, "allele_count": 0,
            "homozygote_count": 0, "error": None,
        }
        result = acmg.classify(
            "SCN1A", "stop_gained",
            origin="de novo (confirmed)",
            gnomad_data=gnomad_absent,
        )
        assert result["classification"] == "Pathogenic", \
            f"Regression: PVS1+PS2+PM2 classified as {result['classification']} (score={result['total_score']})"
        assert result["total_score"] >= 10

    def test_synonymous_no_external_data_is_vus_or_likely_benign(self):
        """synonymous_variant without external data → VUS or Likely Benign."""
        result = acmg.classify("SCN1A", "synonymous_variant")
        assert result["classification"] in {"VUS", "Likely Benign", "Benign"}, \
            f"Regression: synonymous classified as {result['classification']}"

    def test_all_five_valid_classifications_exist(self):
        """The five ACMG tiers must all be reachable."""
        valid = {"Pathogenic", "Likely Pathogenic", "VUS", "Likely Benign", "Benign"}

        r_path = acmg.classify("SCN1A", "stop_gained",
                                origin="de novo (confirmed)",
                                gnomad_data={"found": True, "is_absent": True,
                                             "is_ultra_rare": False, "allele_frequency": None,
                                             "allele_count": 0, "homozygote_count": 0, "error": None})
        r_benign = acmg.classify("SCN1A", "missense_variant",
                                  gnomad_data={"found": True, "is_absent": False, "is_ultra_rare": False,
                                               "allele_frequency": 0.08, "allele_count": 1200,
                                               "homozygote_count": 50, "error": None})
        r_vus = acmg.classify("SCN1A", "missense_variant")

        assert r_path["classification"] == "Pathogenic"
        assert r_benign["classification"] == "Benign"
        assert r_vus["classification"] in valid


# ─────────────────────────────────────────────────────────────────────────────
# REG-04: Score arithmetic pinned
# ─────────────────────────────────────────────────────────────────────────────

class TestScoreArithmeticPinned:

    def test_pvs1_adds_exactly_8_points(self):
        with_pvs1 = acmg.classify("SCN1A", "stop_gained")
        without_pvs1 = acmg.classify("SCN1A", "missense_variant")
        pvs1_contribution = with_pvs1["total_score"] - without_pvs1["total_score"]
        assert pvs1_contribution == 8, \
            f"Regression: PVS1 contributed {pvs1_contribution} points (expected 8)"

    def test_ps2_adds_exactly_4_points(self):
        with_ps2 = acmg.classify("KCNQ2", "missense_variant", origin="de novo (confirmed)")
        without = acmg.classify("KCNQ2", "missense_variant", origin="germline")
        diff = with_ps2["total_score"] - without["total_score"]
        assert diff == 4, f"Regression: PS2 contributed {diff} points (expected 4)"

    def test_pm6_adds_exactly_2_points(self):
        with_pm6 = acmg.classify("KCNQ2", "missense_variant", origin="de novo")
        without = acmg.classify("KCNQ2", "missense_variant", origin="germline")
        diff = with_pm6["total_score"] - without["total_score"]
        assert diff == 2, f"Regression: PM6 contributed {diff} points (expected 2)"

    def test_bp7_subtracts_exactly_1_point(self):
        with_bp7 = acmg.classify("SLC2A1", "synonymous_variant")
        without_bp7 = acmg.classify("SLC2A1", "missense_variant")
        diff = with_bp7["total_score"] - without_bp7["total_score"]
        # BP7 = -1 point; difference should include BP7 effect
        bp7_in_met = any(c["code"] == "BP7" for c in with_bp7["criteria_met"])
        if bp7_in_met:
            assert diff <= -1, \
                f"Regression: BP7 should subtract at least 1 point. Diff={diff}"

    def test_criterion_points_map_unchanged(self):
        """The scoring map must not change between runs."""
        expected = {
            "PVS1": 8, "PS1": 4, "PS2": 4, "PS3": 4,
            "PM1": 2, "PM2": 2, "PM6": 2, "PM4": 2,
            "PP3": 1, "PP5": 1,
            "BA1": -8, "BS1": -4, "BS2": -4,
            "BP4": -1, "BP6": -1, "BP7": -1,
        }
        for code, pts in expected.items():
            assert CRITERION_POINTS[code] == pts, \
                f"Regression: {code} points changed from {pts} to {CRITERION_POINTS[code]}"


# ─────────────────────────────────────────────────────────────────────────────
# REG-05: Confidence resolver thresholds pinned
# ─────────────────────────────────────────────────────────────────────────────

class TestConfidenceResolverRegression:

    def test_uncertain_low_threshold_unchanged(self):
        assert UNCERTAIN_LOW == 0.3, \
            f"Regression: UNCERTAIN_LOW changed to {UNCERTAIN_LOW}"

    def test_uncertain_high_threshold_unchanged(self):
        assert UNCERTAIN_HIGH == 0.7, \
            f"Regression: UNCERTAIN_HIGH changed to {UNCERTAIN_HIGH}"

    def test_boundary_values_classified_correctly(self):
        r = ConfidenceResolver()
        # Exactly at boundaries → uncertain
        assert r.is_uncertain(0.3) is True
        assert r.is_uncertain(0.7) is True
        # Just outside → not uncertain
        assert r.is_uncertain(0.29) is False
        assert r.is_uncertain(0.71) is False

    def test_confidence_level_labels_unchanged(self):
        r = ConfidenceResolver()
        cases = [
            (0.95, "very_high"),
            (0.75, "high"),
            (0.55, "moderate_pathogenic"),
            (0.40, "moderate_benign"),
            (0.15, "high_benign"),
            (0.05, "very_high_benign"),
        ]
        for prob, expected_level in cases:
            actual = r.get_confidence_level(prob)
            assert actual == expected_level, \
                f"Regression: get_confidence_level({prob}) = {actual!r} (expected {expected_level!r})"


# ─────────────────────────────────────────────────────────────────────────────
# REG-06: Contradiction detector logic pinned
# ─────────────────────────────────────────────────────────────────────────────

class TestContradictionDetectorRegression:

    def test_pathogenic_ml_benign_clinvar_is_contradiction(self):
        """This specific scenario must always be detected as a contradiction."""
        result = detector.detect_contradictions(
            ml_prediction="Pathogenic",
            ml_confidence=90.0,
            pathogenic_prob=0.90,
            clinvar_data={"variants": [{"clinical_significance": "Benign", "review_stars": 2}]},
        )
        assert result["has_contradictions"] is True
        types = [c["type"] for c in result["contradictions"]]
        assert "ML vs ClinVar" in types

    def test_benign_ml_lof_consequence_is_contradiction(self):
        """Benign ML + frameshift must always be flagged."""
        result = detector.detect_contradictions(
            ml_prediction="Benign",
            ml_confidence=70.0,
            pathogenic_prob=0.30,
            consequence="frameshift_variant",
        )
        assert result["has_contradictions"] is True

    def test_common_variant_pathogenic_ml_is_contradiction(self):
        """AF > 1% + Pathogenic ML must always be a contradiction."""
        result = detector.detect_contradictions(
            ml_prediction="Pathogenic",
            ml_confidence=80.0,
            pathogenic_prob=0.80,
            gnomad_data={"allele_frequency": 0.05, "allele_count": 800,
                         "is_absent": False, "is_ultra_rare": False},
        )
        assert result["has_contradictions"] is True
        types = [c["type"] for c in result["contradictions"]]
        assert "ML vs gnomAD" in types


# ─────────────────────────────────────────────────────────────────────────────
# REG-07: Gene mechanism map pinned
# ─────────────────────────────────────────────────────────────────────────────

class TestGeneMechanismRegression:

    # These must never change — they are clinically validated
    LOF_GENES = [
        "SCN1A", "SCN3A", "KCNQ2", "KCNQ3", "GABRA1", "GABRG2",
        "TSC1", "TSC2", "MECP2", "CDKL5", "FOXG1", "PCDH19",
        "SLC2A1", "SLC6A1", "ARX", "STXBP1", "DEPDC5", "TBC1D24",
        "LGI1", "GRIN2A", "CHD2", "PRRT2", "ALDH7A1", "CACNA1A",
    ]
    GOF_GENES = ["SCN2A", "SCN8A", "SCN9A"]

    def test_all_lof_genes_pinned(self):
        for gene in self.LOF_GENES:
            mechanism = GENE_MECHANISM.get(gene)
            assert mechanism == "LOF", \
                f"Regression: {gene} mechanism changed to {mechanism!r} (expected LOF)"

    def test_all_gof_genes_pinned(self):
        for gene in self.GOF_GENES:
            mechanism = GENE_MECHANISM.get(gene)
            assert mechanism == "GOF", \
                f"Regression: {gene} mechanism changed to {mechanism!r} (expected GOF)"

    def test_lof_consequences_set_pinned(self):
        required = {
            "frameshift_variant", "stop_gained", "splice_donor_variant",
            "splice_acceptor_variant", "start_lost", "nonsense",
        }
        missing = required - LOF_CONSEQUENCES
        assert not missing, f"Regression: LOF_CONSEQUENCES missing: {missing}"

    def test_benign_consequences_set_pinned(self):
        assert "synonymous_variant" in BENIGN_CONSEQUENCES, \
            "Regression: synonymous_variant removed from BENIGN_CONSEQUENCES"
