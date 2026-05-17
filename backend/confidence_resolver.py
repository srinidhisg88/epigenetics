"""
Confidence Resolver and Contradictory Evidence Detector.

Two key features:
1. Confidence-Aware RAG: When ML prediction is uncertain (0.3-0.7),
   gathers additional evidence to help resolve uncertainty.
2. Contradiction Detection: Identifies when different sources
   (ML, ClinVar, PubMed, gnomAD) disagree about a variant.
"""

from typing import Dict, List, Optional, Tuple


# Confidence thresholds
UNCERTAIN_LOW = 0.3   # Below this = confident benign
UNCERTAIN_HIGH = 0.7  # Above this = confident pathogenic


class ConfidenceResolver:
    """
    Handles uncertain ML predictions by gathering additional evidence
    and detecting contradictions between data sources.
    """

    def is_uncertain(self, pathogenic_probability: float) -> bool:
        """Check if ML prediction falls in the uncertain range."""
        return UNCERTAIN_LOW <= pathogenic_probability <= UNCERTAIN_HIGH

    def get_confidence_level(self, pathogenic_probability: float) -> str:
        """Categorize the confidence level."""
        if pathogenic_probability >= 0.9:
            return "very_high"
        elif pathogenic_probability >= UNCERTAIN_HIGH:
            return "high"
        elif pathogenic_probability >= 0.5:
            return "moderate_pathogenic"
        elif pathogenic_probability >= UNCERTAIN_LOW:
            return "moderate_benign"
        elif pathogenic_probability >= 0.1:
            return "high_benign"
        else:
            return "very_high_benign"

    def build_uncertainty_context(
        self,
        pathogenic_prob: float,
        gene: str,
        consequence: str,
        gnomad_data: Optional[Dict] = None,
        clinvar_data: Optional[Dict] = None,
        shap_data: Optional[Dict] = None,
    ) -> Dict:
        """
        Build additional context when prediction is uncertain.

        Returns a dict with:
        - uncertainty_level: str
        - additional_prompt: str (extra instructions for LLM)
        - evidence_summary: str (what evidence we have)
        - recommended_action: str
        """
        prob_pct = round(pathogenic_prob * 100, 1)

        # Gather evidence points
        evidence_points = []
        supporting_pathogenic = 0
        supporting_benign = 0

        # Check gnomAD — only count absence as pathogenic signal when ClinVar
        # does not already provide a Benign classification (PM2 override logic)
        clinvar_benign = False
        if clinvar_data and clinvar_data.get("variants"):
            for _cv in clinvar_data["variants"][:3]:
                _s = _cv.get("clinical_significance", "").lower()
                if "benign" in _s and "pathogenic" not in _s:
                    clinvar_benign = True
                    break

        if gnomad_data:
            if (gnomad_data.get("is_absent") or gnomad_data.get("is_ultra_rare")) and not clinvar_benign:
                evidence_points.append(
                    f"gnomAD: Variant is {'absent from' if gnomad_data.get('is_absent') else 'ultra-rare in'} "
                    f"population database (supports pathogenicity)"
                )
                supporting_pathogenic += 1
            elif gnomad_data.get("allele_frequency") and gnomad_data["allele_frequency"] > 0.01:
                evidence_points.append(
                    f"gnomAD: Variant is common in population (AF={gnomad_data['allele_frequency']:.4f}), "
                    f"argues against pathogenicity (ACMG BS1)"
                )
                supporting_benign += 1
            elif gnomad_data.get("is_rare"):
                evidence_points.append(
                    f"gnomAD: Variant is rare (AF={gnomad_data.get('allele_frequency', 0):.6f}), "
                    f"consistent with possible pathogenicity"
                )
                supporting_pathogenic += 0.5

        # Check ClinVar
        if clinvar_data and clinvar_data.get("variants"):
            top_variant = clinvar_data["variants"][0]
            clin_sig = top_variant.get("clinical_significance", "").lower()
            stars = top_variant.get("review_stars", 0)

            if "pathogenic" in clin_sig and "benign" not in clin_sig:
                evidence_points.append(
                    f"ClinVar: Classified as {top_variant['clinical_significance']} "
                    f"({'⭐' * stars} review) — supports pathogenicity"
                )
                supporting_pathogenic += 1 + (stars * 0.5)
            elif "benign" in clin_sig:
                evidence_points.append(
                    f"ClinVar: Classified as {top_variant['clinical_significance']} "
                    f"({'⭐' * stars} review) — supports benign"
                )
                supporting_benign += 1 + (stars * 0.5)
            elif "uncertain" in clin_sig:
                evidence_points.append(
                    f"ClinVar: Classified as Uncertain Significance (VUS) — inconclusive"
                )

        # Check consequence severity
        severe_consequences = ["frameshift_variant", "stop_gained", "splice_donor_variant",
                               "splice_acceptor_variant", "start_lost"]
        benign_consequences = ["synonymous_variant", "intron_variant"]

        if consequence in severe_consequences:
            evidence_points.append(
                f"Variant consequence: {consequence} — severe protein impact, supports pathogenicity (ACMG PVS1)"
            )
            supporting_pathogenic += 1.5
        elif consequence in benign_consequences:
            evidence_points.append(
                f"Variant consequence: {consequence} — minimal protein impact, supports benign"
            )
            supporting_benign += 1

        # Check SHAP
        if shap_data and shap_data.get("top_contributors"):
            top = shap_data["top_contributors"][0]
            evidence_points.append(
                f"Top prediction driver: {top['description']} "
                f"({top['direction']} pathogenicity by {top['contribution_pct']}%)"
            )

        # Determine overall assessment
        if supporting_pathogenic > supporting_benign + 1:
            suggested = "Likely Pathogenic"
            reasoning = "Multiple evidence sources support pathogenicity despite ML model uncertainty"
        elif supporting_benign > supporting_pathogenic + 1:
            suggested = "Likely Benign"
            reasoning = "Multiple evidence sources support benign classification despite ML model uncertainty"
        else:
            suggested = "Variant of Uncertain Significance (VUS)"
            reasoning = "Evidence is mixed — clinical correlation and functional studies recommended"

        # Build context for LLM
        evidence_text = "\n".join(f"  • {ep}" for ep in evidence_points) if evidence_points else "  • No additional evidence available"

        additional_prompt = (
            f"\n\n⚠️ UNCERTAINTY NOTICE: The ML model is uncertain about this variant "
            f"(pathogenic probability: {prob_pct}%, within the uncertain range of 30-70%).\n\n"
            f"Additional evidence gathered to help resolve uncertainty:\n"
            f"{evidence_text}\n\n"
            f"Evidence weight: {supporting_pathogenic:.1f} supporting pathogenic, "
            f"{supporting_benign:.1f} supporting benign.\n"
            f"Suggested classification: {suggested}\n"
            f"Reasoning: {reasoning}\n\n"
            f"IMPORTANT: In your response, clearly state that the ML model is uncertain "
            f"and explain the additional evidence that helps clarify the classification. "
            f"Recommend further clinical investigation if evidence is mixed."
        )

        return {
            "is_uncertain": True,
            "uncertainty_level": self.get_confidence_level(pathogenic_prob),
            "pathogenic_prob_pct": prob_pct,
            "evidence_points": evidence_points,
            "supporting_pathogenic": supporting_pathogenic,
            "supporting_benign": supporting_benign,
            "suggested_classification": suggested,
            "reasoning": reasoning,
            "additional_prompt": additional_prompt,
        }


class ContradictionDetector:
    """
    Detects contradictions between different evidence sources.
    """

    def detect_contradictions(
        self,
        ml_prediction: str,
        ml_confidence: float,
        pathogenic_prob: float,
        clinvar_data: Optional[Dict] = None,
        gnomad_data: Optional[Dict] = None,
        gene: str = "",
        consequence: str = "",
    ) -> Dict:
        """
        Detect contradictions between ML prediction and other sources.

        Returns:
            Dictionary with:
            - has_contradictions: bool
            - contradictions: list of contradiction descriptions
            - severity: 'low', 'medium', 'high'
            - context_for_llm: str (formatted for LLM prompt)
        """
        contradictions = []

        # 1. ML vs ClinVar contradiction
        if clinvar_data and clinvar_data.get("variants"):
            top_variant = clinvar_data["variants"][0]
            clin_sig = top_variant.get("clinical_significance", "").lower()
            stars = top_variant.get("review_stars", 0)

            if ml_prediction == "Pathogenic" and "benign" in clin_sig and "pathogenic" not in clin_sig:
                contradictions.append({
                    "type": "ML vs ClinVar",
                    "description": (
                        f"ML model predicts PATHOGENIC ({ml_confidence:.1f}% confidence), "
                        f"but ClinVar classifies this variant as {top_variant['clinical_significance']} "
                        f"({'⭐' * stars} review status)"
                    ),
                    "severity": "high" if stars >= 2 else "medium",
                    "recommendation": "ClinVar expert review may be more reliable. "
                                      "Consider the ClinVar classification."
                })

            elif ml_prediction == "Benign" and "pathogenic" in clin_sig and "benign" not in clin_sig:
                contradictions.append({
                    "type": "ML vs ClinVar",
                    "description": (
                        f"ML model predicts BENIGN ({ml_confidence:.1f}% confidence), "
                        f"but ClinVar classifies this variant as {top_variant['clinical_significance']} "
                        f"({'⭐' * stars} review status)"
                    ),
                    "severity": "high" if stars >= 2 else "medium",
                    "recommendation": "ClinVar pathogenic classification should take priority. "
                                      "This variant may be pathogenic despite the ML prediction."
                })

            elif ml_prediction == "Pathogenic" and "uncertain" in clin_sig:
                contradictions.append({
                    "type": "ML vs ClinVar (VUS)",
                    "description": (
                        f"ML model predicts PATHOGENIC ({ml_confidence:.1f}% confidence), "
                        f"but ClinVar classifies this as Variant of Uncertain Significance (VUS)"
                    ),
                    "severity": "medium",
                    "recommendation": "The ML prediction may provide additional evidence for reclassification. "
                                      "Recent literature may support pathogenicity."
                })

        # 2. ML vs gnomAD contradiction
        if gnomad_data:
            af = gnomad_data.get("allele_frequency")

            if ml_prediction == "Pathogenic" and af and af > 0.01:
                contradictions.append({
                    "type": "ML vs gnomAD",
                    "description": (
                        f"ML model predicts PATHOGENIC, but variant is COMMON in population "
                        f"(gnomAD AF={af:.4f}, {gnomad_data.get('allele_count', 0)} alleles). "
                        f"Common variants are unlikely to cause severe epilepsy (ACMG BS1)."
                    ),
                    "severity": "high",
                    "recommendation": "Population frequency argues strongly against pathogenicity. "
                                      "Review the ML prediction carefully."
                })

            elif ml_prediction == "Benign" and gnomad_data.get("is_absent"):
                # This is weaker — absence alone doesn't mean pathogenic
                pass  # Not a strong contradiction

        # 3. Consequence vs prediction contradiction
        severe_consequences = ["frameshift_variant", "stop_gained",
                               "splice_donor_variant", "splice_acceptor_variant"]

        if ml_prediction == "Benign" and consequence in severe_consequences:
            contradictions.append({
                "type": "ML vs Variant Consequence",
                "description": (
                    f"ML model predicts BENIGN, but variant consequence is {consequence} "
                    f"which typically causes severe protein disruption. "
                    f"Loss-of-function variants in epilepsy genes are usually pathogenic."
                ),
                "severity": "medium",
                "recommendation": "The severe consequence type warrants further investigation. "
                                  "Consider functional studies."
            })

        # 4. Multiple ClinVar submitters disagree
        if clinvar_data and clinvar_data.get("variants"):
            for cv in clinvar_data["variants"][:5]:
                clin_sig = cv.get("clinical_significance", "").lower()
                if "conflicting" in clin_sig:
                    contradictions.append({
                        "type": "ClinVar Internal Conflict",
                        "description": (
                            f"ClinVar has conflicting interpretations for this gene region. "
                            f"Different submitters disagree on pathogenicity."
                        ),
                        "severity": "medium",
                        "recommendation": "Conflicting expert opinions exist. "
                                          "Review individual submitter evidence."
                    })
                    break

        # Determine overall severity
        if not contradictions:
            overall_severity = "none"
        elif any(c["severity"] == "high" for c in contradictions):
            overall_severity = "high"
        elif any(c["severity"] == "medium" for c in contradictions):
            overall_severity = "medium"
        else:
            overall_severity = "low"

        # Format for LLM context
        context_text = self._format_for_context(contradictions) if contradictions else ""

        return {
            "has_contradictions": len(contradictions) > 0,
            "contradictions": contradictions,
            "severity": overall_severity,
            "count": len(contradictions),
            "context_for_llm": context_text,
        }

    def _format_for_context(self, contradictions: List[Dict]) -> str:
        """Format contradictions as context for LLM prompt."""
        lines = [
            "\n=== ⚠️ CONTRADICTORY EVIDENCE DETECTED ===",
            "The following contradictions were found between evidence sources:",
            "",
        ]

        for i, c in enumerate(contradictions, 1):
            lines.append(f"Contradiction {i} ({c['type']}) — Severity: {c['severity'].upper()}")
            lines.append(f"  {c['description']}")
            lines.append(f"  Recommendation: {c['recommendation']}")
            lines.append("")

        lines.append(
            "IMPORTANT: Address these contradictions in your response. "
            "Clearly explain the conflicting evidence and provide a balanced assessment. "
            "Recommend additional clinical investigation where appropriate."
        )

        return "\n".join(lines)


# Singleton instances
_resolver_instance: Optional[ConfidenceResolver] = None
_detector_instance: Optional[ContradictionDetector] = None


def get_confidence_resolver() -> ConfidenceResolver:
    """Get or create singleton ConfidenceResolver."""
    global _resolver_instance
    if _resolver_instance is None:
        _resolver_instance = ConfidenceResolver()
    return _resolver_instance


def get_contradiction_detector() -> ContradictionDetector:
    """Get or create singleton ContradictionDetector."""
    global _detector_instance
    if _detector_instance is None:
        _detector_instance = ContradictionDetector()
    return _detector_instance
