"""
Automated ACMG/AMP Variant Classification for Epilepsy Genes.

Implements the ACMG/AMP 2015 guidelines (Richards et al.) with the
Tavtigian et al. 2018 points-based scoring for unambiguous classification.

Uses data already collected by the pipeline:
  - gnomAD allele frequency  → PM2 / BA1 / BS1
  - Variant consequence       → PVS1 / BP7
  - Variant origin            → PS2
  - ClinVar classifications   → PS1 / PP5 / BS2 / BP6
  - SHAP functional evidence  → PP3 / BP4
  - Gene mechanism (LOF/GOF)  → modulates PVS1 eligibility

Output: 5-tier classification
  Pathogenic | Likely Pathogenic | VUS | Likely Benign | Benign
"""

from typing import Dict, List, Optional, Tuple


# ─────────────────────────────────────────────────────────────────────────────
# Gene Mechanism Map
# LOF = loss-of-function causes disease → PVS1 applies to truncating variants
# GOF = gain-of-function causes disease → PVS1 does NOT apply
# ─────────────────────────────────────────────────────────────────────────────
GENE_MECHANISM = {
    # ── Loss-of-function genes ────────────────────────────────────────────────
    # PVS1 (+8) applies to frameshift / nonsense / canonical splice variants.
    "SCN1A":   "LOF",   # Dravet syndrome — haploinsufficiency
    "KCNQ2":   "LOF",   # BFNE (LOF dominant); NOTE: GOF variants also cause DEE7 (Miceli 2015)
    "KCNQ3":   "LOF",   # BFNE — haploinsufficiency
    "GABRA1":  "LOF",   # CAE, JME — reduced GABA-A surface expression
    "GABRG2":  "LOF",   # GEFS+, CAE; NOTE: GOF variants cause severe early-onset DEE (GABRG2 2024)
    "TSC1":    "LOF",   # Tuberous sclerosis — tumour suppressor, two-hit LOF
    "TSC2":    "LOF",   # Tuberous sclerosis — tumour suppressor, two-hit LOF
    "DEPDC5":  "LOF",   # Familial focal epilepsy — GATOR1 complex haploinsufficiency
    "NPRL3":   "LOF",   # Familial focal epilepsy — GATOR1 complex haploinsufficiency
    "CDKL5":   "LOF",   # CDKL5 deficiency disorder — kinase LOF
    "MECP2":   "LOF",   # Rett syndrome — transcriptional regulator LOF
    "STXBP1":  "LOF",   # Ohtahara / West syndrome — synaptic vesicle fusion LOF
    "ARX":     "LOF",   # Ohtahara / West syndrome — homeobox transcription factor LOF
    "FOXG1":   "LOF",   # FOXG1 syndrome — forkhead transcription factor LOF
    "PCDH19":  "LOF",   # PCDH19-related epilepsy — cellular interference (NOT haploinsufficiency;
                        #   hemizygous males are unaffected — do not apply PVS1 for XY patients)
    "SLC2A1":  "LOF",   # GLUT1 deficiency syndrome — glucose transporter LOF
    "SLC6A1":  "LOF",   # SLC6A1-related epilepsy — GAT-1 GABA transporter LOF
    "CHD2":    "LOF",   # CHD2 myoclonic encephalopathy — chromatin remodelling LOF
    "PLCB1":   "LOF",   # Early-onset epileptic encephalopathy — phospholipase LOF
    "PRRT2":   "LOF",   # BFIE / paroxysmal kinesigenic dyskinesia — presynaptic scaffold LOF
    "TBC1D24": "LOF",   # DOORS syndrome / focal epilepsy — synaptic vesicle trafficking LOF
    "ALDH7A1": "LOF",   # Pyridoxine-dependent epilepsy — antiquitin enzyme LOF

    # ── Gain-of-function genes ────────────────────────────────────────────────
    # PVS1 does NOT apply — truncating variants are generally not disease-causing.
    "SCN2A":   "GOF",   # Early-onset epilepsy (<3 mo) — GOF; LOF SCN2A → ASD/later onset
                        #   (Ben-Shalom 2017, Wolff 2017). ClinVar epilepsy submissions are
                        #   predominantly GOF. NOTE: LOF can also cause later-onset epilepsy.
    "SCN3A":   "GOF",   # Focal epileptic encephalopathy — elevated persistent Na+ current;
                        #   91% of tested pathogenic missense variants are GOF (Zaman 2018)
    "SCN8A":   "GOF",   # DEE-SCN8A — GOF dominant for severe phenotype; LOF SCN8A causes
                        #   milder generalised epilepsy (Larsen 2015)
    "SCN9A":   "GOF",   # GEFS+/Dravet-like — Nav1.7 GOF lowers neuronal firing threshold
                        #   (Bhatt 2019 PMC6940421). Role as standalone epilepsy gene is debated.
}

# Consequences that trigger PVS1 (only in LOF genes)
LOF_CONSEQUENCES = {
    "frameshift_variant",
    "stop_gained",
    "splice_donor_variant",
    "splice_acceptor_variant",
    "start_lost",
    "nonsense",
}

# Consequences that support BP7 (synonymous only — per Richards 2015)
# BP7 definition: "A synonymous (silent) variant for which splicing prediction
# algorithms predict no impact to the splice consensus sequence nor the creation
# of a new splice site AND the nucleotide is not highly conserved."
# intron_variant is intentionally excluded — intronic variants can cause disease
# via cryptic splice activation (e.g., MECP2, SCN1A deep intronic variants)
# and should NOT automatically receive a benign supporting point.
BENIGN_CONSEQUENCES = {
    "synonymous_variant",
}


# ─────────────────────────────────────────────────────────────────────────────
# Points-based scoring (Tavtigian et al. 2018)
# Positive = pathogenic evidence, Negative = benign evidence
# ─────────────────────────────────────────────────────────────────────────────
CRITERION_POINTS = {
    # Pathogenic
    "PVS1": 8,
    "PS1":  4,
    "PS2":  4,
    "PS3":  4,
    "PM1":  2,
    "PM2":  2,
    "PM6":  2,
    "PM4":  2,
    "PP3":  1,
    "PP5":  1,
    # Benign
    "BA1": -8,
    "BS1": -4,
    "BS2": -4,
    "BP4": -1,
    "BP6": -1,
    "BP7": -1,
}

# Classification thresholds (points-based)
CLASSIFICATION_THRESHOLDS = [
    (10,  "Pathogenic"),
    (6,   "Likely Pathogenic"),
    (1,   "VUS"),
    (-6,  "Likely Benign"),
    (None, "Benign"),  # ≤ -7 or BA1 alone
]

# Human-readable criterion descriptions
CRITERION_DESCRIPTIONS = {
    "PVS1": "Loss-of-function variant in a gene where LOF is a disease mechanism",
    "PS1":  "Same amino acid change as a previously established pathogenic variant",
    "PS2":  "De novo variant (confirmed, both parents tested and negative)",
    "PM6":  "De novo variant (assumed — parental testing not confirmed)",
    "PS3":  "Well-established functional studies confirm damaging effect",
    "PM1":  "Located in a mutational hotspot or well-established functional domain",
    "PM2":  "Absent from population databases (gnomAD) — extremely rare",
    "PM4":  "In-frame insertion/deletion in a non-repeat region",
    "PP3":  "ML model computational analysis predicts damaging effect on gene/protein",
    "PP5":  "Reported as pathogenic in a reputable database (ClinVar)",
    "BA1":  "Allele frequency >5% in population databases — stand-alone benign",
    "BS1":  "Allele frequency greater than expected for disease (>1% in gnomAD)",
    "BS2":  "Observed in healthy individuals — argues against pathogenicity",
    "BP4":  "ML model computational analysis predicts benign/tolerated effect on gene/protein",
    "BP6":  "Reported as benign in a reputable database (ClinVar)",
    "BP7":  "Synonymous variant with no predicted splice impact",
}


class ACMGClassifier:
    """
    Automated ACMG/AMP variant classifier for epilepsy genes.

    Evaluates applicable criteria from available evidence and produces
    a 5-tier classification with full criteria justification.
    """

    def classify(
        self,
        gene: str,
        consequence: str,
        origin: str = "germline",
        gnomad_data: Optional[Dict] = None,
        clinvar_data: Optional[Dict] = None,
        shap_data: Optional[Dict] = None,
        variant_type: str = "single nucleotide variant",
        reference_allele: str = "",
        alternate_allele: str = "",
    ) -> Dict:
        """
        Run ACMG/AMP classification for a variant.

        Returns:
            {
                'classification': str (5-tier),
                'criteria_met': list of criterion dicts,
                'criteria_not_met': list of criterion dicts,
                'total_score': int,
                'score_breakdown': dict,
                'clinical_summary': str,
                'context_for_llm': str,
            }
        """
        gene = gene.upper()
        mechanism = GENE_MECHANISM.get(gene, "LOF")
        consequence_norm = consequence.lower().replace(" ", "_")

        criteria_met = []
        criteria_not_met = []

        def add(code: str, met: bool, reason: str):
            entry = {
                "code": code,
                "description": CRITERION_DESCRIPTIONS.get(code, code),
                "reason": reason,
                "points": CRITERION_POINTS.get(code, 0),
            }
            if met:
                criteria_met.append(entry)
            else:
                criteria_not_met.append(entry)

        # ── PVS1: Loss-of-function in LOF gene ───────────────────────────────
        if consequence_norm in LOF_CONSEQUENCES:
            if mechanism == "LOF":
                add("PVS1", True,
                    f"{consequence} in {gene} — a gene where loss-of-function is a known disease mechanism")
            else:
                add("PVS1", False,
                    f"{consequence} but {gene} causes disease via gain-of-function — PVS1 not applicable")
        else:
            add("PVS1", False,
                f"Consequence ({consequence}) is not a loss-of-function type")

        # ── PS1: Same amino acid change as known pathogenic ───────────────────
        # ACMG PS1 requires the EXACT same amino acid substitution at the same
        # codon position — not merely any pathogenic variant in the same gene.
        # Without per-variant AA-level position matching this criterion cannot
        # be reliably automated; it is therefore marked not-met and flagged for
        # manual review.  ClinVar pathogenic evidence is captured by PP5 below.
        add("PS1", False,
            "PS1 requires the same amino acid change at the same codon position "
            "as a previously established pathogenic variant — requires manual "
            "review of amino acid-level ClinVar evidence; not auto-assigned")

        # ── PS2 / PM6: De novo ───────────────────────────────────────────────
        # PS2 (+4 Strong): confirmed de novo — both parents tested and negative
        # PM6 (+2 Moderate): assumed de novo — not confirmed by parental testing
        origin_lower = origin.lower().replace("_", " ")
        is_confirmed_denovo = "confirmed" in origin_lower and "de novo" in origin_lower
        is_assumed_denovo   = "de novo" in origin_lower and "confirmed" not in origin_lower

        if is_confirmed_denovo:
            add("PS2", True,
                "Variant confirmed as de novo — parental testing performed, "
                "not present in either parent (Strong pathogenic evidence)")
            add("PM6", False,
                "PM6 not applied — PS2 (confirmed de novo) takes precedence")
        elif is_assumed_denovo:
            add("PS2", False,
                "PS2 not applied — de novo status not confirmed by parental testing; "
                "PM6 (assumed de novo, Moderate) applied instead")
            add("PM6", True,
                "Assumed de novo — parental testing not reported; "
                "scored as Moderate (PM6) rather than Strong (PS2)")
        else:
            add("PS2", False, f"Origin is '{origin}' — not a de novo variant")
            add("PM6", False, f"Origin is '{origin}' — not a de novo variant")

        # ── PM1: Mutational hotspot / critical functional domain ──────────────
        # ACMG PM1: "Located in a mutational hotspot and/or critical and
        # well-established functional domain without benign variation."
        # Ideally requires domain annotation (e.g., voltage-sensor domain,
        # pore region) at the specific variant position.
        # Proxy used here: severe consequence (missense) + SHAP consequence
        # feature (not gene-identity feature) driving pathogenicity strongly.
        # Gene-identity SHAP (e.g., "gene_SCN1A") reflects PP4-type specificity,
        # not PM1-type domain evidence — excluded from PM1 trigger.
        pm1_met = False
        severe_missense_consequences = {"missense_variant", "inframe_deletion", "inframe_insertion"}
        if shap_data and shap_data.get("top_contributors") and consequence_norm in severe_missense_consequences:
            for contrib in shap_data["top_contributors"][:5]:
                feature = contrib.get("feature", "").lower()
                # Only accept consequence/severity features, not gene-identity features
                is_consequence_feature = any(k in feature for k in (
                    "consequence", "severe", "missense", "frameshift",
                    "nonsense", "splice", "position", "domain"
                ))
                is_gene_feature = feature.startswith("gene_") or feature in (
                    "is_sodium_channel", "is_ion_channel", "is_gaba_receptor", "is_tsc_complex"
                )
                if (contrib.get("direction") == "increases" and
                        contrib.get("contribution_pct", 0) >= 20 and
                        is_consequence_feature and not is_gene_feature):
                    pm1_met = True
                    add("PM1", True,
                        f"Variant consequence ({consequence}) in {gene} is in a "
                        f"functionally critical region — '{contrib['description']}' "
                        f"is a strong driver of pathogenic prediction")
                    break
        if not pm1_met:
            add("PM1", False,
                "PM1 requires domain-level annotation (mutational hotspot or critical "
                "functional domain) — insufficient positional evidence available automatically; "
                "manual review of variant position within protein structure recommended")

        # ── PM2: Absent / ultra-rare in gnomAD ───────────────────────────────
        # PM2 is pathogenic-supporting evidence.  If ClinVar expert review
        # already classifies this variant as Benign/Likely Benign (BP6 would
        # trigger), gnomAD absence does NOT override that expert classification.
        clinvar_says_benign = False
        if clinvar_data and clinvar_data.get("variants"):
            for _cv in clinvar_data["variants"][:3]:
                _sig = _cv.get("clinical_significance", "").lower()
                if "benign" in _sig and "pathogenic" not in _sig:
                    clinvar_says_benign = True
                    break

        if gnomad_data and not clinvar_says_benign:
            # Do NOT apply PM2 when gnomAD data is from an API error — the
            # variant may well be present in gnomAD; absence of a response is
            # not evidence of absence from the population database.
            gnomad_api_error = not gnomad_data.get("found", True) and gnomad_data.get("error")
            af = gnomad_data.get("allele_frequency")
            is_absent = gnomad_data.get("is_absent", False)
            is_ultra_rare = gnomad_data.get("is_ultra_rare", False)

            if gnomad_api_error:
                add("PM2", False,
                    "PM2 not evaluated — gnomAD API returned an error; variant "
                    "presence in population databases is unknown")
            elif is_absent:
                add("PM2", True,
                    f"Variant is absent from gnomAD population database "
                    f"(0 alleles observed in >140,000 individuals)")
            elif is_ultra_rare and af is not None:
                add("PM2", True,
                    f"Variant is ultra-rare in gnomAD (AF={af:.2e}) — "
                    f"consistent with rare disease-causing variant")
            else:
                af_display = f"{af:.5f}" if af else "unknown"
                add("PM2", False,
                    f"Variant is present in gnomAD (AF={af_display})")
        elif clinvar_says_benign:
            add("PM2", False,
                "PM2 not applied — ClinVar expert review classifies this variant "
                "as Benign/Likely Benign, which takes precedence over gnomAD absence")
        else:
            add("PM2", False, "gnomAD data not available — PM2 not evaluated")

        # ── PM4: In-frame indel or stop-loss ─────────────────────────────────
        # ACMG PM4: "Protein length changes as a result of in-frame deletions/
        # insertions in a non-repeat region OR stop-loss variants."
        # Applies regardless of gene mechanism (LOF or GOF).
        is_inframe = consequence_norm in {"inframe_deletion", "inframe_insertion"}
        is_stop_loss = consequence_norm == "stop_lost"
        if is_inframe:
            add("PM4", True,
                f"In-frame {consequence} in {gene} — protein length change without "
                f"complete truncation; may disrupt critical structural/functional region")
        elif is_stop_loss:
            add("PM4", True,
                f"Stop-loss variant in {gene} — extends protein beyond normal stop codon, "
                f"potentially disrupting C-terminal regulatory or structural elements")
        else:
            add("PM4", False,
                "Not an in-frame insertion/deletion or stop-loss variant — PM4 not applicable")

        # ── PP3: ML model analysis (SHAP → pathogenic) ───────────────────────
        # Note: ACMG PP3 formally requires multiple *independent* computational
        # tools (CADD, REVEL, SIFT, PolyPhen-2, etc.).  Here we use the
        # XGBoost model's SHAP feature attribution as a single-source proxy.
        # This is a known limitation — treat PP3/BP4 as supporting evidence only.
        pp3_met = False
        bp4_met = False
        if shap_data and shap_data.get("top_contributors"):
            top = shap_data["top_contributors"][0]
            if top.get("direction") == "increases" and top.get("contribution_pct", 0) >= 15:
                pp3_met = True
                add("PP3", True,
                    f"ML model analysis (SHAP) predicts damaging effect — "
                    f"'{top['description']}' is the strongest driver of the pathogenic prediction")
            elif top.get("direction") == "decreases" and top.get("contribution_pct", 0) >= 15:
                bp4_met = True

        if not pp3_met:
            add("PP3", False, "ML model analysis does not strongly predict a damaging effect for this variant")

        # ── PP5: ClinVar pathogenic (any star) ───────────────────────────────
        pp5_met = False
        if clinvar_data and clinvar_data.get("variants"):
            for cv in clinvar_data["variants"][:3]:
                sig = cv.get("clinical_significance", "").lower()
                if "pathogenic" in sig and "benign" not in sig:
                    pp5_met = True
                    stars = cv.get("review_stars", 0)
                    add("PP5", True,
                        f"ClinVar reports this variant as '{cv['clinical_significance']}' "
                        f"({'⭐' * stars if stars > 0 else 'no review stars'})")
                    break
        if not pp5_met:
            add("PP5", False, "ClinVar does not report a pathogenic classification for this variant")

        # ── BA1: Stand-alone benign (AF > 5%) ────────────────────────────────
        ba1_met = False
        if gnomad_data:
            af = gnomad_data.get("allele_frequency") or 0.0
            if af > 0.05:
                ba1_met = True
                add("BA1", True,
                    f"Allele frequency in gnomAD is {af:.3f} ({af*100:.1f}%) — "
                    f"exceeds 5% threshold, stand-alone Benign classification")
            else:
                af_display = f"{af:.4f}" if af else "absent"
                add("BA1", False,
                    f"Allele frequency ({af_display}) does not exceed 5% threshold")
        else:
            add("BA1", False, "gnomAD data not available")

        # ── BS1: Common variant (AF 1-5%) ────────────────────────────────────
        bs1_met = False
        if gnomad_data and not ba1_met:
            af = gnomad_data.get("allele_frequency") or 0.0
            if af > 0.01:
                bs1_met = True
                add("BS1", True,
                    f"Allele frequency in gnomAD is {af:.3f} ({af*100:.1f}%) — "
                    f"exceeds 1% threshold, higher than expected for a severe epilepsy variant")
            else:
                af_display = f"{af:.5f}" if af else "absent"
                add("BS1", False,
                    f"Allele frequency ({af_display}) does not exceed 1%")
        elif not gnomad_data:
            add("BS1", False, "gnomAD data not available")

        # ── BS2: Observed in healthy individuals ─────────────────────────────
        # ACMG BS2: "Observed in a healthy adult individual for a recessive
        # (homozygous), dominant (heterozygous), or X-linked (hemizygous male)
        # disorder with full penetrance expected at an early age."
        # For DOMINANT epilepsy genes (most genes here): use allele_count
        # (heterozygous + homozygous carriers) in gnomAD as the signal.
        # A threshold of ≥5 alleles in gnomAD healthy individuals is used;
        # for RECESSIVE genes, homozygote_count would be the correct field.
        bs2_met = False
        if gnomad_data and not gnomad_data.get("error"):
            ac = gnomad_data.get("allele_count", 0) or 0
            af = gnomad_data.get("allele_frequency", 0) or 0
            ac_hom = gnomad_data.get("homozygote_count", 0) or 0

            if mechanism == "LOF" and ac >= 5 and af > 0.00001:
                # Dominant epilepsy gene: heterozygous carriers in gnomAD
                bs2_met = True
                add("BS2", True,
                    f"Variant found in {ac} alleles (including {ac_hom} homozygotes) "
                    f"in gnomAD healthy individuals — argues against fully penetrant "
                    f"pathogenicity in this dominant epilepsy gene")
            elif mechanism == "GOF" and ac_hom >= 2:
                # GOF genes: homozygotes without disease is strong BS2
                bs2_met = True
                add("BS2", True,
                    f"Variant found in {ac_hom} homozygous individuals in gnomAD — "
                    f"argues against pathogenicity for {gene} (GOF gene)")
            else:
                add("BS2", False,
                    f"Insufficient observations in healthy individuals "
                    f"(AC={ac}, homozygotes={ac_hom}) to apply BS2")
        else:
            add("BS2", False, "gnomAD data not available or API error — BS2 not evaluated")

        # ── BP4: ML model analysis (SHAP → benign) ───────────────────────────
        if bp4_met and shap_data:
            top = shap_data["top_contributors"][0]
            add("BP4", True,
                f"ML model analysis (SHAP) predicts benign/tolerated effect — "
                f"'{top['description']}' is the strongest driver arguing against pathogenicity")
        else:
            add("BP4", False, "ML model analysis does not predict a benign effect for this variant")

        # ── BP6: ClinVar benign ───────────────────────────────────────────────
        bp6_met = False
        if clinvar_data and clinvar_data.get("variants"):
            for cv in clinvar_data["variants"][:3]:
                sig = cv.get("clinical_significance", "").lower()
                if "benign" in sig and "pathogenic" not in sig:
                    bp6_met = True
                    add("BP6", True,
                        f"ClinVar reports this variant as '{cv['clinical_significance']}'")
                    break
        if not bp6_met:
            add("BP6", False, "ClinVar does not report a benign classification")

        # ── BP7: Synonymous variant ───────────────────────────────────────────
        if consequence_norm in BENIGN_CONSEQUENCES:
            add("BP7", True,
                f"Variant is {consequence} — no amino acid change, "
                f"minimal predicted impact on protein function")
        else:
            add("BP7", False,
                f"Consequence ({consequence}) is not synonymous/intronic")

        # ── Scoring ───────────────────────────────────────────────────────────
        total_score = sum(c["points"] for c in criteria_met)

        # BA1 alone = Benign (override)
        ba1_triggered = any(c["code"] == "BA1" for c in criteria_met)

        if ba1_triggered or total_score <= -7:
            classification = "Benign"
        elif total_score <= -1:
            classification = "Likely Benign"
        elif total_score <= 5:
            classification = "VUS"
        elif total_score <= 9:
            classification = "Likely Pathogenic"
        else:
            classification = "Pathogenic"

        # Score breakdown
        pathogenic_pts = sum(c["points"] for c in criteria_met if c["points"] > 0)
        benign_pts = sum(c["points"] for c in criteria_met if c["points"] < 0)

        score_breakdown = {
            "total": total_score,
            "pathogenic_points": pathogenic_pts,
            "benign_points": benign_pts,
            "pathogenic_criteria": [c["code"] for c in criteria_met if c["points"] > 0],
            "benign_criteria": [c["code"] for c in criteria_met if c["points"] < 0],
        }

        clinical_summary = self._build_clinical_summary(
            classification, criteria_met, gene, consequence, total_score
        )
        context_for_llm = self._build_llm_context(
            classification, criteria_met, gene, total_score
        )

        return {
            "classification": classification,
            "criteria_met": criteria_met,
            "criteria_not_met": [c for c in criteria_not_met
                                  if c["code"] in ("PVS1", "PS1", "PS2", "PM6", "PM2", "BA1", "BS1", "BP7")],
            "score_breakdown": score_breakdown,
            "total_score": total_score,
            "clinical_summary": clinical_summary,
            "context_for_llm": context_for_llm,
            "gene_mechanism": mechanism,
        }

    def _build_clinical_summary(
        self, classification: str, criteria_met: List[Dict],
        gene: str, consequence: str, score: int
    ) -> str:
        met_codes = [c["code"] for c in criteria_met]
        lines = [
            f"ACMG/AMP Classification: {classification.upper()}",
            f"Total evidence score: {score:+d}",
            "",
        ]

        if criteria_met:
            lines.append("Criteria Met:")
            for c in criteria_met:
                weight = _weight_label(c["points"])
                lines.append(f"  ✓ {c['code']} ({weight}) — {c['description']}")
        else:
            lines.append("No criteria met — classification defaults to VUS.")

        return "\n".join(lines)

    def _build_llm_context(
        self, classification: str, criteria_met: List[Dict],
        gene: str, score: int
    ) -> str:
        path_criteria = [c for c in criteria_met if c["points"] > 0]
        benign_criteria = [c for c in criteria_met if c["points"] < 0]

        lines = [
            "=== ACMG/AMP VARIANT CLASSIFICATION ===",
            f"Classification: {classification}",
            f"Evidence Score: {score:+d}",
            "",
        ]

        if path_criteria:
            lines.append("Pathogenic evidence criteria met:")
            for c in path_criteria:
                lines.append(f"  • {c['code']}: {c['reason']}")

        if benign_criteria:
            lines.append("Benign evidence criteria met:")
            for c in benign_criteria:
                lines.append(f"  • {c['code']}: {c['reason']}")

        if not criteria_met:
            lines.append("No criteria met — insufficient evidence for classification beyond VUS.")

        lines.append("")
        lines.append(
            "Present the ACMG classification prominently in the report. "
            "List the criteria met in plain clinical language — do NOT use "
            "the code names (PVS1, PM2, etc.) directly; instead describe "
            "what each criterion means for this specific variant."
        )

        return "\n".join(lines)


def _weight_label(points: int) -> str:
    abs_pts = abs(points)
    if abs_pts >= 8:
        return "Very Strong"
    elif abs_pts >= 4:
        return "Strong"
    elif abs_pts >= 2:
        return "Moderate"
    else:
        return "Supporting"


# ─────────────────────────────────────────────────────────────────────────────
# Singleton
# ─────────────────────────────────────────────────────────────────────────────
_acmg_instance: Optional[ACMGClassifier] = None


def get_acmg_classifier() -> ACMGClassifier:
    """Get or create singleton ACMGClassifier."""
    global _acmg_instance
    if _acmg_instance is None:
        _acmg_instance = ACMGClassifier()
    return _acmg_instance
