"""
SHAP Explainer module for Epilepsy Diagnostic Assistant.

Computes SHAP values for XGBoost predictions and translates
feature contributions into clinical language for LLM context.
"""

import numpy as np
import pandas as pd
import shap
import joblib
from typing import Dict, List, Optional, Tuple


# Human-readable names for features
FEATURE_DESCRIPTIONS = {
    # Gene features
    "gene_SCN1A": "Located in SCN1A (sodium channel gene, Dravet syndrome)",
    "gene_SCN2A": "Located in SCN2A (sodium channel gene, early-onset epilepsy)",
    "gene_SCN3A": "Located in SCN3A (sodium channel gene)",
    "gene_SCN8A": "Located in SCN8A (sodium channel gene, EIEE13)",
    "gene_SCN9A": "Located in SCN9A (sodium channel gene)",
    "gene_KCNQ2": "Located in KCNQ2 (potassium channel, neonatal seizures)",
    "gene_KCNQ3": "Located in KCNQ3 (potassium channel, neonatal seizures)",
    "gene_GABRA1": "Located in GABRA1 (GABA receptor, generalized epilepsy)",
    "gene_GABRG2": "Located in GABRG2 (GABA receptor, febrile seizures)",
    "gene_TSC1": "Located in TSC1 (tuberous sclerosis complex)",
    "gene_TSC2": "Located in TSC2 (tuberous sclerosis complex)",
    "gene_MECP2": "Located in MECP2 (Rett syndrome gene)",
    "gene_CDKL5": "Located in CDKL5 (early-onset seizures, X-linked)",
    "gene_FOXG1": "Located in FOXG1 (Rett-like syndrome)",
    "gene_PCDH19": "Located in PCDH19 (epilepsy in females)",
    "gene_SLC2A1": "Located in SLC2A1 (GLUT1 deficiency, absence epilepsy)",
    "gene_SLC6A1": "Located in SLC6A1 (GABA transporter, myoclonic-atonic epilepsy)",
    "gene_STXBP1": "Located in STXBP1 (synaptic transmission, Ohtahara syndrome)",
    "gene_DEPDC5": "Located in DEPDC5 (mTOR pathway, focal epilepsy)",
    "gene_TBC1D24": "Located in TBC1D24 (multifocal epilepsy)",
    "gene_LGI1": "Located in LGI1 (temporal lobe epilepsy)",
    "gene_GRIN2A": "Located in GRIN2A (NMDA receptor, speech-related epilepsy)",
    "gene_CHD2": "Located in CHD2 (chromatin remodeling, myoclonic epilepsy)",
    "gene_PRRT2": "Located in PRRT2 (paroxysmal kinesigenic dyskinesia)",
    "gene_ALDH7A1": "Located in ALDH7A1 (pyridoxine-dependent epilepsy)",
    "gene_CACNA1A": "Located in CACNA1A (calcium channel, absence epilepsy)",
    "gene_ARX": "Located in ARX (X-linked epilepsy, infantile spasms)",

    # Consequence features
    "severe_consequence_count": "Severe protein consequence (frameshift/nonsense/splice)",
    "is_frameshift": "Frameshift mutation (disrupts protein reading frame)",
    "is_nonsense": "Nonsense mutation (creates premature stop codon)",
    "is_missense": "Missense mutation (changes single amino acid)",
    "is_splice": "Splice site variant (disrupts mRNA processing)",
    "is_synonymous": "Synonymous variant (no amino acid change)",
    "is_inframe": "In-frame insertion/deletion (preserves reading frame)",
    "is_start_loss": "Start loss (disrupts translation initiation)",
    "is_stop_loss": "Stop loss (extends protein beyond normal stop)",

    # Variant type features
    "is_snp": "Single nucleotide change",
    "is_transition": "Transition mutation (purine↔purine or pyrimidine↔pyrimidine)",
    "is_transversion": "Transversion mutation (purine↔pyrimidine)",

    # Review features
    "review_score": "ClinVar review confidence level",
    "has_expert_review": "Has expert panel review in ClinVar",
    "has_multiple_submitters": "Multiple ClinVar submitters agree",
    "has_criteria_provided": "Submitters provided classification criteria",
    "num_submitters": "Number of ClinVar submitters",

    # Position features
    "position_in_gene": "Relative position within gene",
    "is_early_in_gene": "Located in early region of gene",
    "is_late_in_gene": "Located in late region of gene",

    # Origin features
    "is_germline": "Germline variant (inherited/constitutional)",
    "is_de_novo": "De novo variant (not inherited from parents)",

    # Gene category features
    "is_sodium_channel": "Gene encodes a sodium channel",
    "is_ion_channel": "Gene encodes an ion channel",
    "is_gaba_receptor": "Gene encodes a GABA receptor",
    "is_tsc_complex": "Gene is part of TSC complex (mTOR pathway)",
    "gene_pathogenicity_rate": "Gene's overall pathogenicity rate in ClinVar",
    "gene_sample_count": "Number of known variants in this gene",

    # Allele features
    "ref_length": "Reference allele length",
    "alt_length": "Alternate allele length",
    "allele_length_diff": "Difference in allele lengths",
}

# Fallback for unmapped features
DEFAULT_DESCRIPTION = "Genomic feature"


class SHAPExplainer:
    """
    Computes SHAP explanations for XGBoost variant predictions
    and translates them into clinical language.
    """

    def __init__(self, model, feature_names: List[str]):
        """
        Initialize SHAP explainer.

        Args:
            model: Trained model (XGBoost or CalibratedClassifierCV wrapping XGBoost)
            feature_names: List of feature names matching model input
        """
        self.model = model
        self.feature_names = feature_names

        # Extract underlying XGBoost if wrapped in CalibratedClassifierCV
        xgb_model = self._extract_base_model(model)
        self.explainer = shap.TreeExplainer(xgb_model)

    def _extract_base_model(self, model):
        """
        Extract the base XGBoost model from a CalibratedClassifierCV wrapper,
        or return the model directly if it's already an XGBoost model.
        """
        # sklearn CalibratedClassifierCV wrapper
        if hasattr(model, 'calibrated_classifiers_'):
            return model.calibrated_classifiers_[0].estimator
        return model

    def explain(self, features_df: pd.DataFrame, top_n: int = 5) -> Dict:
        """
        Compute SHAP values and generate clinical explanation.

        Args:
            features_df: DataFrame with features for a single variant
            top_n: Number of top contributing features to include

        Returns:
            Dictionary with SHAP explanation:
            {
                'shap_values': list of (feature, value, contribution_direction),
                'top_contributors': list of top N features with clinical descriptions,
                'base_value': float (expected prediction without any features),
                'prediction_value': float (actual prediction),
                'clinical_explanation': str (for LLM context)
            }
        """
        # Compute SHAP values
        shap_values = self.explainer.shap_values(features_df)
        sv = np.array(shap_values)

        # Handle shapes: (n_samples, n_features) or list [class0, class1]
        if sv.ndim == 3:
            # Old SHAP format: list of arrays per class, stacked → (2, n_samples, n_features)
            sv = sv[1]  # pathogenic class
        # Now sv shape is (n_samples, n_features); take first sample row
        sv_row = sv[0]

        # Get base value
        expected = self.explainer.expected_value
        if isinstance(expected, (list, np.ndarray)):
            base_value = float(np.array(expected).flat[-1])
        else:
            base_value = float(expected)

        # Get feature values
        feature_values = features_df.values[0]

        # Build (feature_name, shap_value, feature_value) tuples
        shap_tuples = []
        for i, fname in enumerate(self.feature_names):
            shap_tuples.append((fname, float(sv_row[i]), float(feature_values[i])))

        # Sort by absolute SHAP value (most important first)
        shap_tuples.sort(key=lambda x: abs(x[1]), reverse=True)

        # Get top contributors
        top_contributors = []
        for fname, shap_val, feat_val in shap_tuples[:top_n]:
            description = FEATURE_DESCRIPTIONS.get(fname, fname)
            direction = "increases" if shap_val > 0 else "decreases"
            contribution_pct = abs(shap_val) / sum(abs(x[1]) for x in shap_tuples) * 100

            top_contributors.append({
                "feature": fname,
                "shap_value": round(shap_val, 4),
                "feature_value": feat_val,
                "description": description,
                "direction": direction,
                "contribution_pct": round(contribution_pct, 1),
            })

        # Generate clinical explanation text
        clinical_explanation = self._generate_clinical_text(top_contributors)

        # Format for LLM context
        context_text = self._format_for_context(top_contributors, base_value)

        return {
            "top_contributors": top_contributors,
            "base_value": round(base_value, 4),
            "clinical_explanation": clinical_explanation,
            "context_for_llm": context_text,
        }

    # Strength labels based on contribution percentage
    _STRENGTH_LABELS = [
        (40, "the strongest indicator"),
        (20, "a strong indicator"),
        (10, "a notable factor"),
        (5,  "a contributing factor"),
        (0,  "a minor factor"),
    ]

    def _strength_label(self, pct: float) -> str:
        for threshold, label in self._STRENGTH_LABELS:
            if pct >= threshold:
                return label
        return "a minor factor"

    def _generate_clinical_text(self, top_contributors: List[Dict]) -> str:
        """Generate human-readable clinical explanation from SHAP values."""
        pathogenic = [c for c in top_contributors if c["direction"] == "increases"]
        benign = [c for c in top_contributors if c["direction"] == "decreases"]
        lines = []

        if pathogenic:
            lines.append("Factors supporting pathogenicity:")
            for c in pathogenic:
                label = self._strength_label(c["contribution_pct"])
                lines.append(f"  • {c['description']} — {label}")

        if benign:
            lines.append("\nFactors arguing against pathogenicity:")
            for c in benign:
                label = self._strength_label(c["contribution_pct"])
                lines.append(f"  • {c['description']} — {label}")

        return "\n".join(lines)

    def _format_for_context(self, top_contributors: List[Dict], base_value: float) -> str:
        """
        Format SHAP findings as clinical context for the LLM.
        Uses plain clinical language — no raw numbers, no ML terminology.
        """
        pathogenic = [c for c in top_contributors if c["direction"] == "increases"]
        benign = [c for c in top_contributors if c["direction"] == "decreases"]

        lines = ["=== CLINICAL EVIDENCE SUMMARY ===", ""]

        if pathogenic:
            lines.append("Key factors supporting pathogenicity for this variant:")
            for c in pathogenic:
                label = self._strength_label(c["contribution_pct"])
                lines.append(f"  • {c['description']} — {label} for pathogenicity classification.")

        if benign:
            lines.append("")
            lines.append("Factors that reduce the likelihood of pathogenicity:")
            for c in benign:
                label = self._strength_label(c["contribution_pct"])
                lines.append(f"  • {c['description']} — {label} suggesting lower pathogenicity risk.")

        lines.append("")
        lines.append(
            "Use these clinical factors to explain, in plain medical language, "
            "why this variant is likely pathogenic or benign. "
            "Do NOT mention scores, numbers, or algorithm names."
        )

        return "\n".join(lines)


# Singleton instance
_explainer_instance: Optional[SHAPExplainer] = None


def get_shap_explainer(model=None, feature_names=None) -> Optional[SHAPExplainer]:
    """Get or create singleton SHAPExplainer instance."""
    global _explainer_instance
    if _explainer_instance is None and model is not None and feature_names is not None:
        _explainer_instance = SHAPExplainer(model, feature_names)
    return _explainer_instance
