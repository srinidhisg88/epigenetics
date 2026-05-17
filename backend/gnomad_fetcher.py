"""
gnomAD Fetcher module for Epilepsy Diagnostic Assistant.

Fetches population allele frequency data from gnomAD GraphQL API.
Used to assess variant rarity (PM2 criterion) and filter common variants (BS1).
Caches results in SQLite with 30-day TTL.
"""

import os
import json
import sqlite3
import hashlib
from datetime import datetime, timedelta
from typing import Dict, Optional
from pathlib import Path

import requests

# gnomAD GraphQL API endpoint
GNOMAD_API_URL = "https://gnomad.broadinstitute.org/api"

# Cache configuration
CACHE_DIR = Path("cache/gnomad")
CACHE_DIR.mkdir(parents=True, exist_ok=True)
CACHE_DB = CACHE_DIR / "gnomad_cache.db"
CACHE_TTL_DAYS = 30


class GnomADFetcher:
    """
    Fetches population allele frequency data from gnomAD.
    """

    def __init__(self):
        self._init_cache()

    def _init_cache(self):
        """Initialize SQLite cache."""
        conn = sqlite3.connect(str(CACHE_DB))
        conn.execute("""
            CREATE TABLE IF NOT EXISTS gnomad_cache (
                query_hash TEXT PRIMARY KEY,
                result TEXT,
                timestamp TEXT
            )
        """)
        conn.commit()
        conn.close()

    def _get_cache(self, query_hash: str) -> Optional[Dict]:
        """Get cached result if not expired."""
        conn = sqlite3.connect(str(CACHE_DB))
        cursor = conn.execute(
            "SELECT result, timestamp FROM gnomad_cache WHERE query_hash = ?",
            (query_hash,)
        )
        row = cursor.fetchone()
        conn.close()

        if row:
            timestamp = datetime.fromisoformat(row[1])
            if datetime.now() - timestamp < timedelta(days=CACHE_TTL_DAYS):
                return json.loads(row[0])
        return None

    def _set_cache(self, query_hash: str, result: Dict):
        """Store result in cache."""
        conn = sqlite3.connect(str(CACHE_DB))
        conn.execute(
            "INSERT OR REPLACE INTO gnomad_cache (query_hash, result, timestamp) VALUES (?, ?, ?)",
            (query_hash, json.dumps(result), datetime.now().isoformat())
        )
        conn.commit()
        conn.close()

    def get_variant_frequency(
        self,
        chromosome: str,
        position: int,
        reference: str,
        alternate: str,
        genome_version: str = "GRCh38"
    ) -> Dict:
        """
        Fetch allele frequency for a specific variant from gnomAD.

        Args:
            chromosome: Chromosome number (e.g., '2', 'X')
            position: Genomic position
            reference: Reference allele
            alternate: Alternate allele
            genome_version: 'GRCh38' or 'GRCh37'

        Returns:
            Dictionary with frequency data:
            {
                'found': bool,
                'allele_frequency': float or None,
                'allele_count': int,
                'allele_number': int,
                'homozygote_count': int,
                'population_frequencies': dict,
                'is_rare': bool (AF < 0.01),
                'is_ultra_rare': bool (AF < 0.0001),
                'is_absent': bool (not in gnomAD),
                'clinical_interpretation': str,
                'dataset': str
            }
        """
        # Build cache key
        cache_key = f"{chromosome}:{position}:{reference}:{alternate}:{genome_version}"
        query_hash = hashlib.md5(cache_key.encode()).hexdigest()

        # Check cache
        cached = self._get_cache(query_hash)
        if cached is not None:
            return cached

        # Determine dataset based on genome version
        dataset = "gnomad_r4" if genome_version == "GRCh38" else "gnomad_r2_1"

        # Format chromosome for gnomAD (needs 'chr' prefix for v4)
        chrom = chromosome.replace("chr", "")

        # GraphQL query
        query = """
        query VariantQuery($variantId: String!, $datasetId: DatasetId!) {
            variant(variantId: $variantId, dataset: $datasetId) {
                variant_id
                chrom
                pos
                ref
                alt
                exome {
                    ac
                    an
                    ac_hom
                    af
                    populations {
                        id
                        ac
                        an
                        ac_hom
                        af
                    }
                }
                genome {
                    ac
                    an
                    ac_hom
                    af
                    populations {
                        id
                        ac
                        an
                        ac_hom
                        af
                    }
                }
            }
        }
        """

        variant_id = f"{chrom}-{position}-{reference}-{alternate}"

        try:
            response = requests.post(
                GNOMAD_API_URL,
                json={
                    "query": query,
                    "variables": {
                        "variantId": variant_id,
                        "datasetId": dataset,
                    }
                },
                timeout=30,
                headers={"Content-Type": "application/json"}
            )

            if response.status_code != 200:
                result = self._build_absent_result(variant_id, dataset)
                self._set_cache(query_hash, result)
                return result

            data = response.json()
            variant_data = data.get("data", {}).get("variant")

            if variant_data is None:
                result = self._build_absent_result(variant_id, dataset)
                self._set_cache(query_hash, result)
                return result

            # Extract frequency data (prefer exome, fallback to genome)
            freq_data = variant_data.get("exome") or variant_data.get("genome")

            if freq_data is None:
                result = self._build_absent_result(variant_id, dataset)
                self._set_cache(query_hash, result)
                return result

            af = freq_data.get("af") or 0.0
            ac = freq_data.get("ac") or 0
            an = freq_data.get("an") or 0
            ac_hom = freq_data.get("ac_hom") or 0

            # Extract population frequencies
            pop_freqs = {}
            for pop in freq_data.get("populations", []):
                pop_id = pop.get("id", "unknown")
                pop_af = pop.get("af")
                if pop_af is not None and pop_af > 0:
                    pop_freqs[pop_id] = {
                        "af": pop_af,
                        "ac": pop.get("ac", 0),
                        "an": pop.get("an", 0),
                    }

            # Clinical interpretation
            is_rare = af < 0.01
            is_ultra_rare = af < 0.0001
            is_absent = ac == 0

            interpretation = self._interpret_frequency(af, ac, ac_hom)

            result = {
                "found": True,
                "variant_id": variant_id,
                "allele_frequency": af,
                "allele_count": ac,
                "allele_number": an,
                "homozygote_count": ac_hom,
                "population_frequencies": pop_freqs,
                "is_rare": is_rare,
                "is_ultra_rare": is_ultra_rare,
                "is_absent": is_absent,
                "clinical_interpretation": interpretation,
                "dataset": dataset,
            }

            self._set_cache(query_hash, result)
            return result

        except requests.exceptions.RequestException as e:
            print(f"gnomAD API error: {e}")
            result = self._build_absent_result(variant_id, dataset, error=str(e))
            return result

    def _build_absent_result(self, variant_id: str, dataset: str, error: str = None) -> Dict:
        """Build result for variant not found in gnomAD."""
        return {
            "found": False,
            "variant_id": variant_id,
            "allele_frequency": None,
            "allele_count": 0,
            "allele_number": 0,
            "homozygote_count": 0,
            "population_frequencies": {},
            "is_rare": True,
            "is_ultra_rare": True,
            "is_absent": True,
            "clinical_interpretation": "Variant absent from gnomAD population database. "
                                       "Absence from population databases supports pathogenicity (ACMG PM2).",
            "dataset": dataset,
            "error": error,
        }

    def _interpret_frequency(self, af: float, ac: int, ac_hom: int) -> str:
        """Generate clinical interpretation of allele frequency."""
        if af == 0 or af is None:
            return ("Variant absent from gnomAD population database. "
                    "Absence from population databases supports pathogenicity (ACMG PM2).")

        if af < 0.0001:
            return (f"Ultra-rare variant (AF={af:.6f}, {ac} alleles in gnomAD). "
                    f"Rarity supports pathogenicity (ACMG PM2). "
                    f"Homozygotes: {ac_hom}.")

        if af < 0.001:
            return (f"Very rare variant (AF={af:.5f}, {ac} alleles in gnomAD). "
                    f"Consistent with rare disease-causing variant. "
                    f"Homozygotes: {ac_hom}.")

        if af < 0.01:
            return (f"Rare variant (AF={af:.4f}, {ac} alleles in gnomAD). "
                    f"Frequency is borderline for a highly penetrant pathogenic variant. "
                    f"Homozygotes: {ac_hom}.")

        return (f"Common variant (AF={af:.4f}, {ac} alleles in gnomAD). "
                f"High population frequency argues AGAINST pathogenicity (ACMG BS1). "
                f"Homozygotes: {ac_hom}.")

    def format_for_context(self, gnomad_data: Dict) -> str:
        """Format gnomAD data as context string for LLM."""
        if not gnomad_data.get("found"):
            return (f"=== gnomAD POPULATION DATA ===\n"
                    f"Variant: {gnomad_data.get('variant_id', 'unknown')}\n"
                    f"Status: NOT FOUND in gnomAD\n"
                    f"Interpretation: {gnomad_data['clinical_interpretation']}\n")

        af = gnomad_data["allele_frequency"]
        lines = [
            "=== gnomAD POPULATION DATA ===",
            f"Variant: {gnomad_data['variant_id']}",
            f"Overall Allele Frequency: {af:.6f}" if af else "Overall Allele Frequency: 0 (absent)",
            f"Allele Count: {gnomad_data['allele_count']} / {gnomad_data['allele_number']}",
            f"Homozygotes: {gnomad_data['homozygote_count']}",
            f"Dataset: {gnomad_data['dataset']}",
        ]

        # Add top population frequencies
        pop_freqs = gnomad_data.get("population_frequencies", {})
        if pop_freqs:
            lines.append("\nPopulation Frequencies:")
            sorted_pops = sorted(pop_freqs.items(), key=lambda x: x[1]["af"], reverse=True)
            for pop_id, pdata in sorted_pops[:5]:
                lines.append(f"  {pop_id}: AF={pdata['af']:.6f} (AC={pdata['ac']})")

        lines.append(f"\nInterpretation: {gnomad_data['clinical_interpretation']}")
        return "\n".join(lines)


# Singleton instance
_gnomad_instance: Optional[GnomADFetcher] = None


def get_gnomad_fetcher() -> GnomADFetcher:
    """Get or create singleton GnomADFetcher instance."""
    global _gnomad_instance
    if _gnomad_instance is None:
        _gnomad_instance = GnomADFetcher()
    return _gnomad_instance
