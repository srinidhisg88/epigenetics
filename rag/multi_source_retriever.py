"""
Multi-Source Retriever for Epilepsy Diagnostic Assistant.

Coordinates retrieval from multiple knowledge sources:
- PubMed literature (existing RAG system)
- ClinVar variant database
- PharmGKB drug-gene interactions

Merges and ranks results by evidence quality and relevance.
"""

from typing import List, Dict, Optional
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from rag.retriever import RAGRetriever
from backend.clinvar_fetcher import get_clinvar_fetcher, ClinVarFetcher
from backend.pharmgkb_fetcher import get_pharmgkb_fetcher, PharmGKBFetcher
from backend.gnomad_fetcher import get_gnomad_fetcher, GnomADFetcher


class MultiSourceRetriever:
    """
    Retrieves and merges information from multiple knowledge sources.

    Implements evidence-based medicine hierarchy:
    1. ClinVar (variant-specific clinical evidence)
    2. PharmGKB (drug-gene interactions)
    3. gnomAD (population allele frequency)
    4. PubMed literature (general evidence)
    """

    def __init__(
        self,
        pubmed_retriever: Optional[RAGRetriever] = None,
        clinvar_fetcher: Optional[ClinVarFetcher] = None,
        pharmgkb_fetcher: Optional[PharmGKBFetcher] = None,
        gnomad_fetcher: Optional[GnomADFetcher] = None
    ):
        """
        Initialize Multi-Source Retriever.

        Args:
            pubmed_retriever: Existing PubMed RAG retriever
            clinvar_fetcher: ClinVar fetcher instance
            pharmgkb_fetcher: PharmGKB fetcher instance
            gnomad_fetcher: gnomAD fetcher instance
        """
        self.pubmed_retriever = pubmed_retriever
        self.clinvar_fetcher = clinvar_fetcher or get_clinvar_fetcher()
        self.pharmgkb_fetcher = pharmgkb_fetcher or get_pharmgkb_fetcher()
        self.gnomad_fetcher = gnomad_fetcher or get_gnomad_fetcher()

    def retrieve_comprehensive(
        self,
        gene: str,
        variant: Optional[str] = None,
        consequence: Optional[str] = None,
        query: Optional[str] = None,
        include_clinvar: bool = True,
        include_pharmgkb: bool = True,
        include_pubmed: bool = True,
        include_gnomad: bool = True,
        chromosome: Optional[str] = None,
        position: Optional[int] = None,
        reference_allele: Optional[str] = None,
        alternate_allele: Optional[str] = None,
        genome_version: str = "GRCh38",
        top_k: int = 5
    ) -> Dict:
        """
        Retrieve information from all sources and merge results.

        Args:
            gene: Gene symbol (e.g., 'SCN1A')
            variant: Optional variant notation (e.g., 'p.Arg1648His')
            consequence: Variant consequence (e.g., 'missense')
            query: Optional additional search query
            include_clinvar: Whether to include ClinVar data
            include_pharmgkb: Whether to include PharmGKB data
            include_pubmed: Whether to include PubMed literature
            top_k: Number of PubMed results to retrieve

        Returns:
            Dictionary with merged results from all sources
        """
        results = {
            'gene': gene,
            'variant': variant,
            'sources': {},
            'combined_context': '',
            'metadata': {
                'sources_queried': [],
                'total_sources': 0
            }
        }

        context_parts = []

        # 1. ClinVar - Variant-specific evidence (highest priority)
        if include_clinvar:
            try:
                # Use positional search when available — most precise ClinVar lookup
                # Without position, falls back to gene-level search
                if chromosome and position and reference_allele and alternate_allele:
                    print(f"Querying ClinVar exact position: chr{chromosome}:{position} for {gene}")
                    clinvar_variants = self.clinvar_fetcher.search_variant(
                        gene=gene,
                        chromosome=chromosome,
                        position=position,
                        reference_allele=reference_allele,
                        alternate_allele=alternate_allele,
                    )
                else:
                    print(f"Querying ClinVar for {gene}" + (f" {variant}" if variant else " (gene-level, no position)"))
                    clinvar_variants = self.clinvar_fetcher.search_variant(gene, variant)

                if clinvar_variants:
                    results['sources']['clinvar'] = {
                        'variants': clinvar_variants,
                        'count': len(clinvar_variants)
                    }
                    results['metadata']['sources_queried'].append('ClinVar')

                    # Add top variant to context
                    top_variant = clinvar_variants[0]
                    context_parts.append(f"[ClinVar Evidence - {top_variant['review_stars']}⭐]\n" +
                                        top_variant['description'])

            except Exception as e:
                print(f"ClinVar retrieval error: {e}")

        # 2. PharmGKB - Drug-gene interactions (high priority)
        if include_pharmgkb:
            try:
                print(f"Querying PharmGKB for {gene}")
                drug_interactions = self.pharmgkb_fetcher.format_for_rag(gene)

                if drug_interactions:
                    recommendations = self.pharmgkb_fetcher.get_drug_recommendations(gene)
                    results['sources']['pharmgkb'] = recommendations
                    results['metadata']['sources_queried'].append('PharmGKB')

                    # Add to context
                    context_parts.append(f"[PharmGKB Drug-Gene Interactions]\n{drug_interactions}")

            except Exception as e:
                print(f"PharmGKB retrieval error: {e}")

        # 3. gnomAD - Population allele frequency
        if include_gnomad and chromosome and position and reference_allele and alternate_allele:
            try:
                print(f"Querying gnomAD for {chromosome}:{position}:{reference_allele}>{alternate_allele}")
                gnomad_data = self.gnomad_fetcher.get_variant_frequency(
                    chromosome=chromosome,
                    position=position,
                    reference=reference_allele,
                    alternate=alternate_allele,
                    genome_version=genome_version
                )

                results['sources']['gnomad'] = gnomad_data
                results['metadata']['sources_queried'].append('gnomAD')

                # Add to context
                gnomad_context = self.gnomad_fetcher.format_for_context(gnomad_data)
                context_parts.append(gnomad_context)

            except Exception as e:
                print(f"gnomAD retrieval error: {e}")

        # 4. PubMed Literature - General evidence (supplementary)
        if include_pubmed and self.pubmed_retriever and self.pubmed_retriever.is_loaded:
            try:
                print(f"Querying PubMed literature for {gene}")

                if consequence:
                    chunks = self.pubmed_retriever.retrieve_for_variant(
                        gene=gene,
                        variant_type='',
                        consequence=consequence,
                        top_k=top_k
                    )
                elif query:
                    chunks = self.pubmed_retriever.retrieve(query, top_k=top_k)
                else:
                    # General gene query
                    chunks = self.pubmed_retriever.retrieve(
                        f"{gene} epilepsy pathogenicity treatment",
                        top_k=top_k
                    )

                if chunks:
                    results['sources']['pubmed'] = {
                        'chunks': chunks,
                        'count': len(chunks)
                    }
                    results['metadata']['sources_queried'].append('PubMed')

                    # Add top 2 chunks to context
                    for i, chunk in enumerate(chunks[:2], 1):
                        context_parts.append(f"[PubMed Literature {i}]\n{chunk['text'][:500]}...")

            except Exception as e:
                print(f"PubMed retrieval error: {e}")

        # Combine all contexts
        results['combined_context'] = "\n\n---\n\n".join(context_parts)
        results['metadata']['total_sources'] = len(results['metadata']['sources_queried'])

        return results

    def format_context_for_llm(self, results: Dict, max_length: int = 4000) -> str:
        """
        Format multi-source results into a context string for LLM.

        Prioritizes information by evidence quality:
        - ClinVar: 40% of space (variant-specific)
        - PharmGKB: 30% of space (treatment recommendations)
        - PubMed: 30% of space (supporting literature)

        Args:
            results: Results from retrieve_comprehensive()
            max_length: Maximum character length

        Returns:
            Formatted context string
        """
        context_parts = []
        remaining_length = max_length

        # Priority 1: ClinVar (40% of space)
        if 'clinvar' in results['sources']:
            clinvar_limit = int(max_length * 0.4)
            clinvar_data = results['sources']['clinvar']

            section = ["=== CLINVAR VARIANT EVIDENCE ===\n"]

            for variant in clinvar_data['variants'][:3]:  # Top 3 variants
                stars = "⭐" * variant['review_stars'] if variant['review_stars'] > 0 else "No review"
                section.append(f"Variant: {variant['variant_name']}")
                section.append(f"Clinical Significance: {variant['clinical_significance']} ({stars})")
                section.append(f"Conditions: {', '.join(variant['conditions'][:2])}")
                section.append("")

            clinvar_text = "\n".join(section)
            if len(clinvar_text) <= clinvar_limit:
                context_parts.append(clinvar_text)
                remaining_length -= len(clinvar_text)

        # Priority 2: PharmGKB (30% of space)
        if 'pharmgkb' in results['sources']:
            pharmgkb_limit = int(max_length * 0.3)
            pharmgkb_data = results['sources']['pharmgkb']

            section = ["=== DRUG-GENE INTERACTIONS ===\n"]

            if pharmgkb_data.get('essential'):
                section.append("ESSENTIAL TREATMENTS:")
                for drug in pharmgkb_data['essential']:
                    section.append(f"• {drug['drug']}: {drug['description']}")
                section.append("")

            if pharmgkb_data.get('recommended'):
                section.append("RECOMMENDED:")
                for drug in pharmgkb_data['recommended'][:3]:
                    section.append(f"• {drug['drug']}: {drug['description']}")
                section.append("")

            if pharmgkb_data.get('contraindicated'):
                section.append("⚠️ CONTRAINDICATED (AVOID):")
                for drug in pharmgkb_data['contraindicated']:
                    section.append(f"• {drug['drug']}: {drug['description']}")
                section.append("")

            pharmgkb_text = "\n".join(section)
            if len(pharmgkb_text) <= pharmgkb_limit:
                context_parts.append(pharmgkb_text)
                remaining_length -= len(pharmgkb_text)

        # Priority 3: gnomAD (10% of space)
        if 'gnomad' in results['sources']:
            gnomad_text = self.gnomad_fetcher.format_for_context(results['sources']['gnomad'])
            gnomad_limit = int(max_length * 0.1)
            if len(gnomad_text) <= gnomad_limit:
                context_parts.append(gnomad_text)
                remaining_length -= len(gnomad_text)

        # Priority 4: PubMed (remaining space)
        if 'pubmed' in results['sources'] and remaining_length > 200:
            pubmed_data = results['sources']['pubmed']

            section = ["=== PUBMED LITERATURE ===\n"]

            for i, chunk in enumerate(pubmed_data['chunks'][:5], 1):
                title = chunk.get('title', 'Unknown')
                text = chunk['text'][:600]  # Truncate to fit
                section.append(f"[Source {i}]: {title}")
                section.append(text)
                section.append("")

            pubmed_text = "\n".join(section)
            if len(pubmed_text) <= remaining_length:
                context_parts.append(pubmed_text)

        return "\n\n".join(context_parts)

    def get_sources_summary(self, results: Dict) -> str:
        """
        Generate a human-readable summary of sources used.

        Args:
            results: Results from retrieve_comprehensive()

        Returns:
            Summary string
        """
        sources = results['metadata']['sources_queried']

        if not sources:
            return "No sources available"

        summary_parts = []

        if 'ClinVar' in sources:
            clinvar_count = results['sources']['clinvar']['count']
            summary_parts.append(f"ClinVar ({clinvar_count} variant{'s' if clinvar_count != 1 else ''})")

        if 'PharmGKB' in sources:
            pharmgkb = results['sources']['pharmgkb']
            # Count all interactions across all categories
            total_drugs = (len(pharmgkb.get('efficacy', [])) +
                          len(pharmgkb.get('toxicity', [])) +
                          len(pharmgkb.get('dosage', [])) +
                          len(pharmgkb.get('other', [])))
            summary_parts.append(f"PharmGKB ({total_drugs} drug interactions)")

        if 'gnomAD' in sources:
            gnomad = results['sources']['gnomad']
            af = gnomad.get('allele_frequency')
            if af is not None:
                summary_parts.append(f"gnomAD (AF={af:.6f})")
            else:
                summary_parts.append("gnomAD (absent)")

        if 'PubMed' in sources:
            pubmed_count = results['sources']['pubmed']['count']
            summary_parts.append(f"PubMed ({pubmed_count} articles)")

        return " | ".join(summary_parts)


# Singleton instance
_retriever_instance: Optional[MultiSourceRetriever] = None


def get_multi_source_retriever(pubmed_retriever: Optional[RAGRetriever] = None) -> MultiSourceRetriever:
    """
    Get or create singleton MultiSourceRetriever instance.

    Args:
        pubmed_retriever: Optional existing PubMed retriever

    Returns:
        MultiSourceRetriever instance
    """
    global _retriever_instance

    if _retriever_instance is None:
        _retriever_instance = MultiSourceRetriever(pubmed_retriever=pubmed_retriever)

    return _retriever_instance
