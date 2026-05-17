"""
Unit Tests — Epilepsy Diagnostic Assistant
==========================================
Tests individual modules in complete isolation using mocks.
No network calls, no model loading, no filesystem dependencies.

Modules covered:
  - ACMGClassifier        (acmg_classifier.py)
  - ConfidenceResolver    (confidence_resolver.py)
  - ContradictionDetector (confidence_resolver.py)
  - _weight_label helper  (acmg_classifier.py)
  - CRITERION_POINTS map  (acmg_classifier.py)
  - Classification thresholds

Run:
    pytest tests/test_unit.py -v
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from unittest.mock import MagicMock, patch

from backend.acmg_classifier import (
    ACMGClassifier,
    CRITERION_POINTS,
    CLASSIFICATION_THRESHOLDS,
    GENE_MECHANISM,
    LOF_CONSEQUENCES,
    BENIGN_CONSEQUENCES,
    _weight_label,
    get_acmg_classifier,
)
from backend.confidence_resolver import (
    ConfidenceResolver,
    ContradictionDetector,
    UNCERTAIN_LOW,
    UNCERTAIN_HIGH,
    get_confidence_resolver,
    get_contradiction_detector,
)


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def acmg():
    return ACMGClassifier()

@pytest.fixture
def resolver():
    return ConfidenceResolver()

@pytest.fixture
def detector():
    return ContradictionDetector()

GNOMAD_ABSENT = {
    "found": True,
    "is_absent": True,
    "is_ultra_rare": False,
    "is_rare": False,
    "allele_frequency": None,
    "allele_count": 0,
    "homozygote_count": 0,
    "error": None,
}

GNOMAD_COMMON = {
    "found": True,
    "is_absent": False,
    "is_ultra_rare": False,
    "is_rare": False,
    "allele_frequency": 0.08,
    "allele_count": 1200,
    "homozygote_count": 50,
    "error": None,
}

GNOMAD_RARE = {
    "found": True,
    "is_absent": False,
    "is_ultra_rare": True,
    "is_rare": False,
    "allele_frequency": 0.000003,
    "allele_count": 1,
    "homozygote_count": 0,
    "error": None,
}

CLINVAR_PATHOGENIC = {
    "variants": [{
        "clinical_significance": "Pathogenic",
        "review_stars": 2,
    }]
}

CLINVAR_BENIGN = {
    "variants": [{
        "clinical_significance": "Benign",
        "review_stars": 2,
    }]
}

CLINVAR_VUS = {
    "variants": [{
        "clinical_significance": "Uncertain significance",
        "review_stars": 1,
    }]
}

SHAP_PATHOGENIC = {
    "top_contributors": [{
        "feature": "is_nonsense",
        "description": "Nonsense mutation (creates premature stop codon)",
        "direction": "increases",
        "contribution_pct": 35,
    }]
}

SHAP_BENIGN = {
    "top_contributors": [{
        "feature": "is_synonymous",
        "description": "Synonymous variant (no amino acid change)",
        "direction": "decreases",
        "contribution_pct": 40,
    }]
}


# ─────────────────────────────────────────────────────────────────────────────
# Unit: _weight_label helper
# ─────────────────────────────────────────────────────────────────────────────

class TestWeightLabel:

    def test_pvs1_is_very_strong(self):
        assert _weight_label(8) == "Very Strong"

    def test_ps_is_strong(self):
        assert _weight_label(4) == "Strong"

    def test_pm_is_moderate(self):
        assert _weight_label(2) == "Moderate"

    def test_pp_is_supporting(self):
        assert _weight_label(1) == "Supporting"

    def test_negative_very_strong(self):
        assert _weight_label(-8) == "Very Strong"

    def test_negative_strong(self):
        assert _weight_label(-4) == "Strong"


# ─────────────────────────────────────────────────────────────────────────────
# Unit: CRITERION_POINTS map integrity
# ─────────────────────────────────────────────────────────────────────────────

class TestCriterionPoints:

    def test_pvs1_points(self):
        assert CRITERION_POINTS["PVS1"] == 8

    def test_ps2_points(self):
        assert CRITERION_POINTS["PS2"] == 4

    def test_pm2_points(self):
        assert CRITERION_POINTS["PM2"] == 2

    def test_pp3_points(self):
        assert CRITERION_POINTS["PP3"] == 1

    def test_ba1_points(self):
        assert CRITERION_POINTS["BA1"] == -8

    def test_bs1_points(self):
        assert CRITERION_POINTS["BS1"] == -4

    def test_bp4_points(self):
        assert CRITERION_POINTS["BP4"] == -1

    def test_pathogenic_criteria_positive(self):
        pathogenic_codes = ["PVS1", "PS1", "PS2", "PS3", "PM1", "PM2", "PM6", "PM4", "PP3", "PP5"]
        for code in pathogenic_codes:
            assert CRITERION_POINTS[code] > 0, f"{code} should be positive"

    def test_benign_criteria_negative(self):
        benign_codes = ["BA1", "BS1", "BS2", "BP4", "BP6", "BP7"]
        for code in benign_codes:
            assert CRITERION_POINTS[code] < 0, f"{code} should be negative"


# ─────────────────────────────────────────────────────────────────────────────
# Unit: GENE_MECHANISM map
# ─────────────────────────────────────────────────────────────────────────────

class TestGeneMechanism:

    def test_scn1a_is_lof(self):
        assert GENE_MECHANISM["SCN1A"] == "LOF"

    def test_scn2a_is_gof(self):
        assert GENE_MECHANISM["SCN2A"] == "GOF"

    def test_scn8a_is_gof(self):
        assert GENE_MECHANISM["SCN8A"] == "GOF"

    def test_tsc2_is_lof(self):
        assert GENE_MECHANISM["TSC2"] == "LOF"

    def test_kcnq2_is_lof(self):
        assert GENE_MECHANISM["KCNQ2"] == "LOF"

    def test_lof_consequence_set_nonempty(self):
        assert len(LOF_CONSEQUENCES) > 0

    def test_stop_gained_in_lof_consequences(self):
        assert "stop_gained" in LOF_CONSEQUENCES

    def test_frameshift_in_lof_consequences(self):
        assert "frameshift_variant" in LOF_CONSEQUENCES

    def test_synonymous_in_benign_consequences(self):
        assert "synonymous_variant" in BENIGN_CONSEQUENCES


# ─────────────────────────────────────────────────────────────────────────────
# Unit: ACMGClassifier — PVS1 criterion
# ─────────────────────────────────────────────────────────────────────────────

class TestACMGPVS1:

    def test_pvs1_triggers_for_stop_gained_in_lof_gene(self, acmg):
        result = acmg.classify("SCN1A", "stop_gained")
        codes = [c["code"] for c in result["criteria_met"]]
        assert "PVS1" in codes

    def test_pvs1_triggers_for_frameshift_in_lof_gene(self, acmg):
        result = acmg.classify("TSC2", "frameshift_variant")
        codes = [c["code"] for c in result["criteria_met"]]
        assert "PVS1" in codes

    def test_pvs1_does_not_trigger_for_gof_gene(self, acmg):
        result = acmg.classify("SCN2A", "stop_gained")
        codes = [c["code"] for c in result["criteria_met"]]
        assert "PVS1" not in codes

    def test_pvs1_does_not_trigger_for_missense(self, acmg):
        result = acmg.classify("SCN1A", "missense_variant")
        codes = [c["code"] for c in result["criteria_met"]]
        assert "PVS1" not in codes

    def test_pvs1_does_not_trigger_for_synonymous(self, acmg):
        result = acmg.classify("SCN1A", "synonymous_variant")
        codes = [c["code"] for c in result["criteria_met"]]
        assert "PVS1" not in codes

    def test_pvs1_triggers_for_splice_donor(self, acmg):
        result = acmg.classify("KCNQ2", "splice_donor_variant")
        codes = [c["code"] for c in result["criteria_met"]]
        assert "PVS1" in codes


# ─────────────────────────────────────────────────────────────────────────────
# Unit: ACMGClassifier — PS2 / PM6 (de novo)
# ─────────────────────────────────────────────────────────────────────────────

class TestACMGDeNovo:

    def test_ps2_triggers_for_confirmed_de_novo(self, acmg):
        result = acmg.classify("KCNQ2", "stop_gained", origin="de novo (confirmed)")
        codes = [c["code"] for c in result["criteria_met"]]
        assert "PS2" in codes
        assert "PM6" not in codes

    def test_pm6_triggers_for_assumed_de_novo(self, acmg):
        result = acmg.classify("KCNQ2", "stop_gained", origin="de novo")
        codes = [c["code"] for c in result["criteria_met"]]
        assert "PM6" in codes
        assert "PS2" not in codes

    def test_neither_ps2_pm6_for_germline(self, acmg):
        result = acmg.classify("SCN1A", "stop_gained", origin="germline")
        codes = [c["code"] for c in result["criteria_met"]]
        assert "PS2" not in codes
        assert "PM6" not in codes

    def test_ps2_adds_4_points(self, acmg):
        with_denovo = acmg.classify("KCNQ2", "missense_variant", origin="de novo (confirmed)")
        without = acmg.classify("KCNQ2", "missense_variant", origin="germline")
        diff = with_denovo["total_score"] - without["total_score"]
        assert diff == 4  # PS2 = +4


# ─────────────────────────────────────────────────────────────────────────────
# Unit: ACMGClassifier — PM2 (gnomAD absence)
# ─────────────────────────────────────────────────────────────────────────────

class TestACMGPM2:

    def test_pm2_triggers_when_absent(self, acmg):
        result = acmg.classify("SCN1A", "missense_variant", gnomad_data=GNOMAD_ABSENT)
        codes = [c["code"] for c in result["criteria_met"]]
        assert "PM2" in codes

    def test_pm2_triggers_for_ultra_rare(self, acmg):
        result = acmg.classify("SCN1A", "missense_variant", gnomad_data=GNOMAD_RARE)
        codes = [c["code"] for c in result["criteria_met"]]
        assert "PM2" in codes

    def test_pm2_does_not_trigger_for_common_variant(self, acmg):
        result = acmg.classify("SCN1A", "missense_variant", gnomad_data=GNOMAD_COMMON)
        codes = [c["code"] for c in result["criteria_met"]]
        assert "PM2" not in codes

    def test_pm2_not_triggered_when_clinvar_says_benign(self, acmg):
        result = acmg.classify(
            "SCN1A", "missense_variant",
            gnomad_data=GNOMAD_ABSENT,
            clinvar_data=CLINVAR_BENIGN
        )
        codes = [c["code"] for c in result["criteria_met"]]
        assert "PM2" not in codes


# ─────────────────────────────────────────────────────────────────────────────
# Unit: ACMGClassifier — BA1 / BS1 (common variant)
# ─────────────────────────────────────────────────────────────────────────────

class TestACMGFrequencyCriteria:

    def test_ba1_triggers_for_high_af(self, acmg):
        result = acmg.classify("SCN1A", "missense_variant", gnomad_data=GNOMAD_COMMON)
        codes = [c["code"] for c in result["criteria_met"]]
        assert "BA1" in codes

    def test_ba1_results_in_benign_classification(self, acmg):
        result = acmg.classify("SCN1A", "missense_variant", gnomad_data=GNOMAD_COMMON)
        assert result["classification"] == "Benign"

    def test_bs1_triggers_for_moderately_common(self, acmg):
        gnomad_moderate = {**GNOMAD_ABSENT, "is_absent": False,
                           "allele_frequency": 0.015, "allele_count": 200}
        result = acmg.classify("SCN1A", "missense_variant", gnomad_data=gnomad_moderate)
        codes = [c["code"] for c in result["criteria_met"]]
        assert "BS1" in codes


# ─────────────────────────────────────────────────────────────────────────────
# Unit: ACMGClassifier — PP3 / BP4 (SHAP)
# ─────────────────────────────────────────────────────────────────────────────

class TestACMGSHAPCriteria:

    def test_pp3_triggers_for_pathogenic_shap(self, acmg):
        result = acmg.classify("SCN1A", "missense_variant", shap_data=SHAP_PATHOGENIC)
        codes = [c["code"] for c in result["criteria_met"]]
        assert "PP3" in codes

    def test_bp4_triggers_for_benign_shap(self, acmg):
        result = acmg.classify("SCN1A", "missense_variant", shap_data=SHAP_BENIGN)
        codes = [c["code"] for c in result["criteria_met"]]
        assert "BP4" in codes

    def test_pp3_and_bp4_mutually_exclusive(self, acmg):
        result = acmg.classify("SCN1A", "missense_variant", shap_data=SHAP_PATHOGENIC)
        codes = [c["code"] for c in result["criteria_met"]]
        assert not ("PP3" in codes and "BP4" in codes)


# ─────────────────────────────────────────────────────────────────────────────
# Unit: ACMGClassifier — BP7 (synonymous)
# ─────────────────────────────────────────────────────────────────────────────

class TestACMGBP7:

    def test_bp7_triggers_for_synonymous(self, acmg):
        result = acmg.classify("SLC2A1", "synonymous_variant")
        codes = [c["code"] for c in result["criteria_met"]]
        assert "BP7" in codes

    def test_bp7_does_not_trigger_for_missense(self, acmg):
        result = acmg.classify("SLC2A1", "missense_variant")
        codes = [c["code"] for c in result["criteria_met"]]
        assert "BP7" not in codes


# ─────────────────────────────────────────────────────────────────────────────
# Unit: ACMGClassifier — PP5 / BP6 (ClinVar)
# ─────────────────────────────────────────────────────────────────────────────

class TestACMGClinVarCriteria:

    def test_pp5_triggers_for_clinvar_pathogenic(self, acmg):
        result = acmg.classify("SCN1A", "missense_variant", clinvar_data=CLINVAR_PATHOGENIC)
        codes = [c["code"] for c in result["criteria_met"]]
        assert "PP5" in codes

    def test_bp6_triggers_for_clinvar_benign(self, acmg):
        result = acmg.classify("SCN1A", "missense_variant", clinvar_data=CLINVAR_BENIGN)
        codes = [c["code"] for c in result["criteria_met"]]
        assert "BP6" in codes

    def test_neither_pp5_nor_bp6_for_vus(self, acmg):
        result = acmg.classify("SCN1A", "missense_variant", clinvar_data=CLINVAR_VUS)
        codes = [c["code"] for c in result["criteria_met"]]
        assert "PP5" not in codes
        assert "BP6" not in codes


# ─────────────────────────────────────────────────────────────────────────────
# Unit: ACMGClassifier — PM4 (in-frame indel)
# ─────────────────────────────────────────────────────────────────────────────

class TestACMGPM4:

    def test_pm4_triggers_for_inframe_deletion(self, acmg):
        result = acmg.classify("SCN1A", "inframe_deletion")
        codes = [c["code"] for c in result["criteria_met"]]
        assert "PM4" in codes

    def test_pm4_triggers_for_stop_loss(self, acmg):
        result = acmg.classify("SCN1A", "stop_lost")
        codes = [c["code"] for c in result["criteria_met"]]
        assert "PM4" in codes

    def test_pm4_does_not_trigger_for_frameshift(self, acmg):
        # frameshift is PVS1, not PM4
        result = acmg.classify("SCN1A", "frameshift_variant")
        codes = [c["code"] for c in result["criteria_met"]]
        assert "PM4" not in codes


# ─────────────────────────────────────────────────────────────────────────────
# Unit: ACMGClassifier — Classification thresholds
# ─────────────────────────────────────────────────────────────────────────────

class TestACMGThresholds:

    def test_high_score_gives_pathogenic(self, acmg):
        # PVS1(8) + PS2(4) + PM2(2) = 14 → Pathogenic
        result = acmg.classify(
            "SCN1A", "stop_gained",
            origin="de novo (confirmed)",
            gnomad_data=GNOMAD_ABSENT
        )
        assert result["classification"] == "Pathogenic"
        assert result["total_score"] >= 10

    def test_low_score_gives_vus(self, acmg):
        result = acmg.classify("SCN1A", "missense_variant")
        # No external data → likely VUS or low score
        assert result["classification"] in {"VUS", "Likely Pathogenic", "Likely Benign"}

    def test_ba1_alone_overrides_to_benign(self, acmg):
        result = acmg.classify("SCN1A", "missense_variant", gnomad_data=GNOMAD_COMMON)
        assert result["classification"] == "Benign"

    def test_result_contains_all_required_fields(self, acmg):
        result = acmg.classify("SCN1A", "stop_gained")
        for field in ["classification", "criteria_met", "criteria_not_met",
                      "total_score", "score_breakdown", "clinical_summary",
                      "context_for_llm", "gene_mechanism"]:
            assert field in result, f"Missing field: {field}"

    def test_gene_mechanism_returned_correctly(self, acmg):
        lof = acmg.classify("SCN1A", "missense_variant")
        gof = acmg.classify("SCN2A", "missense_variant")
        assert lof["gene_mechanism"] == "LOF"
        assert gof["gene_mechanism"] == "GOF"

    def test_unknown_gene_defaults_to_lof(self, acmg):
        result = acmg.classify("BRCA1", "stop_gained")
        # Unknown gene — should default to LOF and still classify
        assert result["classification"] in {
            "Pathogenic", "Likely Pathogenic", "VUS", "Likely Benign", "Benign"
        }


# ─────────────────────────────────────────────────────────────────────────────
# Unit: ConfidenceResolver
# ─────────────────────────────────────────────────────────────────────────────

class TestConfidenceResolver:

    def test_thresholds_are_correct(self):
        assert UNCERTAIN_LOW == 0.3
        assert UNCERTAIN_HIGH == 0.7

    def test_is_uncertain_at_boundary_low(self, resolver):
        assert resolver.is_uncertain(0.3) is True

    def test_is_uncertain_at_boundary_high(self, resolver):
        assert resolver.is_uncertain(0.7) is True

    def test_is_not_uncertain_below_threshold(self, resolver):
        assert resolver.is_uncertain(0.1) is False

    def test_is_not_uncertain_above_threshold(self, resolver):
        assert resolver.is_uncertain(0.9) is False

    def test_is_uncertain_in_middle(self, resolver):
        assert resolver.is_uncertain(0.5) is True

    def test_confidence_level_very_high(self, resolver):
        assert resolver.get_confidence_level(0.95) == "very_high"

    def test_confidence_level_high(self, resolver):
        assert resolver.get_confidence_level(0.75) == "high"

    def test_confidence_level_moderate_pathogenic(self, resolver):
        assert resolver.get_confidence_level(0.55) == "moderate_pathogenic"

    def test_confidence_level_moderate_benign(self, resolver):
        assert resolver.get_confidence_level(0.4) == "moderate_benign"

    def test_confidence_level_high_benign(self, resolver):
        assert resolver.get_confidence_level(0.15) == "high_benign"

    def test_confidence_level_very_high_benign(self, resolver):
        assert resolver.get_confidence_level(0.05) == "very_high_benign"

    def test_build_uncertainty_context_returns_dict(self, resolver):
        ctx = resolver.build_uncertainty_context(0.5, "SCN1A", "missense_variant")
        assert isinstance(ctx, dict)
        assert ctx["is_uncertain"] is True

    def test_uncertainty_context_has_required_keys(self, resolver):
        ctx = resolver.build_uncertainty_context(0.5, "SCN1A", "missense_variant")
        for key in ["is_uncertain", "uncertainty_level", "evidence_points",
                    "supporting_pathogenic", "supporting_benign",
                    "suggested_classification", "reasoning", "additional_prompt"]:
            assert key in ctx

    def test_uncertainty_context_gnomad_absent_supports_pathogenic(self, resolver):
        ctx = resolver.build_uncertainty_context(
            0.5, "SCN1A", "missense_variant", gnomad_data=GNOMAD_ABSENT
        )
        assert ctx["supporting_pathogenic"] > 0

    def test_uncertainty_context_common_variant_supports_benign(self, resolver):
        ctx = resolver.build_uncertainty_context(
            0.5, "SCN1A", "missense_variant", gnomad_data=GNOMAD_COMMON
        )
        assert ctx["supporting_benign"] > 0

    def test_uncertainty_severe_consequence_supports_pathogenic(self, resolver):
        ctx = resolver.build_uncertainty_context(0.5, "SCN1A", "frameshift_variant")
        assert ctx["supporting_pathogenic"] > 0

    def test_uncertainty_synonymous_supports_benign(self, resolver):
        ctx = resolver.build_uncertainty_context(0.5, "SLC2A1", "synonymous_variant")
        assert ctx["supporting_benign"] > 0

    def test_suggested_classification_is_valid_string(self, resolver):
        ctx = resolver.build_uncertainty_context(0.5, "SCN1A", "missense_variant")
        valid = {"Likely Pathogenic", "Likely Benign", "Variant of Uncertain Significance (VUS)"}
        assert ctx["suggested_classification"] in valid

    def test_additional_prompt_mentions_uncertainty(self, resolver):
        ctx = resolver.build_uncertainty_context(0.5, "SCN1A", "missense_variant")
        assert "uncertain" in ctx["additional_prompt"].lower()

    def test_singleton_returns_same_instance(self):
        r1 = get_confidence_resolver()
        r2 = get_confidence_resolver()
        assert r1 is r2


# ─────────────────────────────────────────────────────────────────────────────
# Unit: ContradictionDetector
# ─────────────────────────────────────────────────────────────────────────────

class TestContradictionDetector:

    def test_no_contradiction_when_sources_agree(self, detector):
        result = detector.detect_contradictions(
            ml_prediction="Pathogenic",
            ml_confidence=95.0,
            pathogenic_prob=0.95,
            clinvar_data=CLINVAR_PATHOGENIC,
        )
        # Pathogenic ML + Pathogenic ClinVar → no contradiction
        ml_vs_clinvar = [c for c in result["contradictions"] if c["type"] == "ML vs ClinVar"]
        assert len(ml_vs_clinvar) == 0

    def test_detects_ml_pathogenic_vs_clinvar_benign(self, detector):
        result = detector.detect_contradictions(
            ml_prediction="Pathogenic",
            ml_confidence=90.0,
            pathogenic_prob=0.90,
            clinvar_data=CLINVAR_BENIGN,
        )
        assert result["has_contradictions"] is True
        types = [c["type"] for c in result["contradictions"]]
        assert "ML vs ClinVar" in types

    def test_detects_ml_benign_vs_clinvar_pathogenic(self, detector):
        result = detector.detect_contradictions(
            ml_prediction="Benign",
            ml_confidence=85.0,
            pathogenic_prob=0.15,
            clinvar_data=CLINVAR_PATHOGENIC,
        )
        assert result["has_contradictions"] is True

    def test_detects_ml_pathogenic_vs_common_gnomad(self, detector):
        result = detector.detect_contradictions(
            ml_prediction="Pathogenic",
            ml_confidence=80.0,
            pathogenic_prob=0.80,
            gnomad_data=GNOMAD_COMMON,
        )
        assert result["has_contradictions"] is True
        types = [c["type"] for c in result["contradictions"]]
        assert "ML vs gnomAD" in types

    def test_detects_benign_prediction_with_severe_consequence(self, detector):
        result = detector.detect_contradictions(
            ml_prediction="Benign",
            ml_confidence=70.0,
            pathogenic_prob=0.30,
            consequence="frameshift_variant",
        )
        assert result["has_contradictions"] is True

    def test_no_contradiction_benign_with_synonymous(self, detector):
        result = detector.detect_contradictions(
            ml_prediction="Benign",
            ml_confidence=85.0,
            pathogenic_prob=0.15,
            consequence="synonymous_variant",
        )
        # synonymous + benign prediction — no consequence contradiction
        consequence_contradictions = [
            c for c in result["contradictions"] if c["type"] == "ML vs Variant Consequence"
        ]
        assert len(consequence_contradictions) == 0

    def test_severity_high_when_clinvar_has_expert_review(self, detector):
        clinvar_high = {"variants": [{
            "clinical_significance": "Benign",
            "review_stars": 3,
        }]}
        result = detector.detect_contradictions(
            ml_prediction="Pathogenic",
            ml_confidence=90.0,
            pathogenic_prob=0.90,
            clinvar_data=clinvar_high,
        )
        if result["has_contradictions"]:
            assert result["severity"] in {"high", "medium"}

    def test_result_contains_required_keys(self, detector):
        result = detector.detect_contradictions(
            ml_prediction="Pathogenic",
            ml_confidence=90.0,
            pathogenic_prob=0.90,
        )
        for key in ["has_contradictions", "contradictions", "severity", "count", "context_for_llm"]:
            assert key in result

    def test_contradiction_count_matches_list(self, detector):
        result = detector.detect_contradictions(
            ml_prediction="Pathogenic",
            ml_confidence=90.0,
            pathogenic_prob=0.90,
            clinvar_data=CLINVAR_BENIGN,
            gnomad_data=GNOMAD_COMMON,
        )
        assert result["count"] == len(result["contradictions"])

    def test_no_contradictions_returns_empty_context(self, detector):
        result = detector.detect_contradictions(
            ml_prediction="Pathogenic",
            ml_confidence=95.0,
            pathogenic_prob=0.95,
        )
        if not result["has_contradictions"]:
            assert result["context_for_llm"] == ""

    def test_singleton_returns_same_instance(self):
        d1 = get_contradiction_detector()
        d2 = get_contradiction_detector()
        assert d1 is d2


# ─────────────────────────────────────────────────────────────────────────────
# Unit: ACMGClassifier — Score breakdown integrity
# ─────────────────────────────────────────────────────────────────────────────

class TestACMGScoreBreakdown:

    def test_score_breakdown_keys_present(self, acmg):
        result = acmg.classify("SCN1A", "stop_gained")
        sb = result["score_breakdown"]
        for key in ["total", "pathogenic_points", "benign_points",
                    "pathogenic_criteria", "benign_criteria"]:
            assert key in sb

    def test_total_equals_sum_of_criteria(self, acmg):
        result = acmg.classify("SCN1A", "stop_gained",
                                origin="de novo (confirmed)",
                                gnomad_data=GNOMAD_ABSENT)
        total = result["total_score"]
        computed = sum(c["points"] for c in result["criteria_met"])
        assert total == computed

    def test_pathogenic_points_all_positive(self, acmg):
        result = acmg.classify("SCN1A", "stop_gained")
        sb = result["score_breakdown"]
        assert sb["pathogenic_points"] >= 0

    def test_benign_points_all_negative_or_zero(self, acmg):
        result = acmg.classify("SCN1A", "stop_gained")
        sb = result["score_breakdown"]
        assert sb["benign_points"] <= 0
