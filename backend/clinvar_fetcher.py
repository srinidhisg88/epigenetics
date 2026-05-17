"""
ClinVar Fetcher module for Epilepsy Diagnostic Assistant.

Fetches variant interpretations from NCBI ClinVar database and caches results.
Provides clinical significance, review status, and condition associations.
"""

import os
import json
import sqlite3
import hashlib
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from pathlib import Path
import time

import requests
from xml.etree import ElementTree as ET
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# ClinVar E-utilities URLs
ESEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
ESUMMARY_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
EFETCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"

# Cache configuration
CACHE_DIR = Path("cache/clinvar")
CACHE_DIR.mkdir(parents=True, exist_ok=True)
CACHE_DB = CACHE_DIR / "clinvar_cache.db"

# Rate limiting
RATE_LIMIT_DELAY = 0.35  # 3 requests per second without API key, 10/sec with key


class ClinVarFetcher:
    """
    Fetches variant interpretations from ClinVar database.
    """

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize ClinVar Fetcher.

        Args:
            api_key: NCBI API key (optional, increases rate limit)
        """
        self.api_key = api_key or os.getenv("NCBI_API_KEY")
        self.rate_limit_delay = 0.1 if self.api_key else RATE_LIMIT_DELAY
        self.last_request_time = 0

        # Initialize SQLite cache
        self._init_cache()

    def _init_cache(self):
        """Initialize SQLite cache database."""
        conn = sqlite3.connect(CACHE_DB)
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS clinvar_cache (
                cache_key TEXT PRIMARY KEY,
                gene TEXT,
                variant TEXT,
                data TEXT,
                cached_at TIMESTAMP,
                expires_at TIMESTAMP
            )
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_gene_variant
            ON clinvar_cache(gene, variant)
        """)

        conn.commit()
        conn.close()

    def _get_cache_key(self, gene: str, variant: Optional[str] = None) -> str:
        """Generate cache key for gene/variant query."""
        key_str = f"{gene}_{variant}" if variant else gene
        return hashlib.md5(key_str.encode()).hexdigest()

    def _get_from_cache(self, cache_key: str) -> Optional[Dict]:
        """Retrieve data from cache if valid."""
        conn = sqlite3.connect(CACHE_DB)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT data, expires_at FROM clinvar_cache
            WHERE cache_key = ? AND expires_at > ?
        """, (cache_key, datetime.now().isoformat()))

        result = cursor.fetchone()
        conn.close()

        if result:
            return json.loads(result[0])
        return None

    def _save_to_cache(self, cache_key: str, gene: str, variant: Optional[str],
                       data: Dict, ttl_days: int = 30):
        """Save data to cache with TTL."""
        conn = sqlite3.connect(CACHE_DB)
        cursor = conn.cursor()

        expires_at = datetime.now() + timedelta(days=ttl_days)

        cursor.execute("""
            INSERT OR REPLACE INTO clinvar_cache
            (cache_key, gene, variant, data, cached_at, expires_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (cache_key, gene, variant, json.dumps(data),
              datetime.now().isoformat(), expires_at.isoformat()))

        conn.commit()
        conn.close()

    def _rate_limit(self):
        """Enforce rate limiting."""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.rate_limit_delay:
            time.sleep(self.rate_limit_delay - elapsed)
        self.last_request_time = time.time()

    def _make_request(self, url: str, params: Dict) -> requests.Response:
        """Make rate-limited request to NCBI API."""
        self._rate_limit()

        if self.api_key:
            params['api_key'] = self.api_key

        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        return response

    def search_variant(self, gene: str, variant: Optional[str] = None) -> List[Dict]:
        """
        Search ClinVar for variants in a gene.

        Args:
            gene: Gene symbol (e.g., 'SCN1A')
            variant: Optional specific variant (e.g., 'p.Arg1648His', 'c.1648G>A')

        Returns:
            List of variant dictionaries with clinical interpretations
        """
        # Check cache
        cache_key = self._get_cache_key(gene, variant)
        cached_data = self._get_from_cache(cache_key)
        if cached_data:
            print(f"ClinVar: Loaded from cache for {gene}" +
                  (f" {variant}" if variant else ""))
            return cached_data

        print(f"ClinVar: Fetching from API for {gene}" +
              (f" {variant}" if variant else "..."))

        # Build search query
        if variant:
            # Search for specific variant
            search_term = f"{gene}[gene] AND {variant}[variant name]"
        else:
            # Search for all variants in gene with pathogenic/likely pathogenic
            search_term = f"{gene}[gene] AND (pathogenic[clinical significance] OR likely pathogenic[clinical significance])"

        try:
            # Step 1: Search for variant IDs
            search_params = {
                'db': 'clinvar',
                'term': search_term,
                'retmax': 100,  # Limit results
                'retmode': 'json',
                'sort': 'clinical significance'
            }

            search_response = self._make_request(ESEARCH_URL, search_params)
            search_data = search_response.json()

            variant_ids = search_data.get('esearchresult', {}).get('idlist', [])

            if not variant_ids:
                print(f"  No variants found in ClinVar")
                return []

            print(f"  Found {len(variant_ids)} variant(s)")

            # Step 2: Fetch detailed information for each variant
            variants = []

            # Process in batches of 10
            for i in range(0, len(variant_ids), 10):
                batch_ids = variant_ids[i:i+10]

                summary_params = {
                    'db': 'clinvar',
                    'id': ','.join(batch_ids),
                    'retmode': 'json'
                }

                summary_response = self._make_request(ESUMMARY_URL, summary_params)
                summary_data = summary_response.json()

                # Parse each variant
                for vid in batch_ids:
                    variant_data = summary_data.get('result', {}).get(vid, {})
                    if not variant_data or vid == 'uids':
                        continue

                    # Extract key information — pass vid as the authoritative variation ID
                    variant_info = self._parse_variant_summary(variant_data, variation_uid=vid)
                    if variant_info:
                        variants.append(variant_info)

            # Sort by review status (higher stars first)
            variants.sort(key=lambda v: v.get('review_stars', 0), reverse=True)

            # Cache results
            self._save_to_cache(cache_key, gene, variant, variants, ttl_days=30)

            return variants

        except Exception as e:
            print(f"Error fetching from ClinVar: {e}")
            return []

    def _parse_variant_summary(self, variant_data: Dict, variation_uid: str = '') -> Optional[Dict]:
        """Parse ClinVar variant summary data."""
        try:
            # Extract clinical significance
            clinical_sig = variant_data.get('clinical_significance', {})
            significance = clinical_sig.get('description', 'Uncertain significance')
            review_status = clinical_sig.get('review_status', 'no assertion criteria provided')

            # Convert review status to star rating (0-4)
            review_stars = self._get_review_stars(review_status)

            # Extract variant details
            variation_set = variant_data.get('variation_set', [{}])[0] if variant_data.get('variation_set') else {}

            # Get variant names
            variant_name = variation_set.get('variation_name', 'Unknown')

            # Get gene info
            genes = variant_data.get('genes', [])
            gene_symbol = genes[0].get('symbol', '') if genes else ''

            # Get conditions
            trait_set = variant_data.get('trait_set', [])
            conditions = [trait.get('trait_name', '') for trait in trait_set]

            # Get accession — variation_uid (the esummary dict key) is the most reliable ID
            accession = variant_data.get('accession', '')
            variation_id = variation_uid or str(variant_data.get('uid', '')).strip()

            # Build ClinVar URL using numeric variation ID (/clinvar/variation/{id}/)
            if variation_id and variation_id.isdigit():
                clinvar_url = f"https://www.ncbi.nlm.nih.gov/clinvar/variation/{variation_id}/"
            elif accession and str(accession).strip():
                clinvar_url = f"https://www.ncbi.nlm.nih.gov/clinvar/{accession.strip()}/"
            elif gene_symbol:
                clinvar_url = f"https://www.ncbi.nlm.nih.gov/clinvar/?term={gene_symbol}[gene]"
            else:
                clinvar_url = "https://www.ncbi.nlm.nih.gov/clinvar/"

            return {
                'variation_id': variation_id,
                'accession': accession,
                'gene': gene_symbol,
                'variant_name': variant_name,
                'clinical_significance': significance,
                'review_status': review_status,
                'review_stars': review_stars,
                'conditions': conditions,
                'url': clinvar_url,
                'last_evaluated': variant_data.get('last_evaluated', ''),
                'description': self._format_description(
                    gene_symbol, variant_name, significance, conditions, review_stars
                )
            }

        except Exception as e:
            print(f"Error parsing variant: {e}")
            return None

    def _get_review_stars(self, review_status: str) -> int:
        """Convert review status to star rating (0-4)."""
        review_status_lower = review_status.lower()

        if 'practice guideline' in review_status_lower:
            return 4
        elif 'expert panel' in review_status_lower or 'reviewed by expert panel' in review_status_lower:
            return 3
        elif 'multiple submitters' in review_status_lower and 'no conflicts' in review_status_lower:
            return 2
        elif 'criteria provided' in review_status_lower and 'single submitter' in review_status_lower:
            return 1
        else:
            return 0

    def _format_description(self, gene: str, variant: str, significance: str,
                           conditions: List[str], stars: int) -> str:
        """Format variant description for RAG context."""
        star_display = "⭐" * stars if stars > 0 else "No review"
        conditions_str = ", ".join(conditions[:3]) if conditions else "Not specified"

        return f"""ClinVar Variant Report ({star_display}):

Gene: {gene}
Variant: {variant}
Clinical Significance: {significance}
Associated Conditions: {conditions_str}
Review Status: {stars}-star rating

This variant has been evaluated by clinical laboratories and submitted to ClinVar,
the NIH's public archive of variant interpretations. Higher star ratings indicate
more rigorous expert review and consensus."""

    def get_gene_summary(self, gene: str, limit: int = 10) -> Dict:
        """
        Get summary statistics for a gene's variants in ClinVar.

        Args:
            gene: Gene symbol
            limit: Maximum number of top variants to include

        Returns:
            Dictionary with gene-level statistics and top variants
        """
        variants = self.search_variant(gene)

        if not variants:
            return {
                'gene': gene,
                'total_variants': 0,
                'message': 'No pathogenic/likely pathogenic variants found in ClinVar'
            }

        # Count by significance
        sig_counts = {}
        for v in variants:
            sig = v.get('clinical_significance', 'Unknown')
            sig_counts[sig] = sig_counts.get(sig, 0) + 1

        # Count by review status
        review_counts = {0: 0, 1: 0, 2: 0, 3: 0, 4: 0}
        for v in variants:
            stars = v.get('review_stars', 0)
            review_counts[stars] = review_counts.get(stars, 0) + 1

        return {
            'gene': gene,
            'total_variants': len(variants),
            'significance_distribution': sig_counts,
            'review_distribution': review_counts,
            'top_variants': variants[:limit]
        }


# Singleton instance
_fetcher_instance: Optional[ClinVarFetcher] = None


def get_clinvar_fetcher() -> ClinVarFetcher:
    """
    Get or create singleton ClinVarFetcher instance.

    Returns:
        ClinVarFetcher instance
    """
    global _fetcher_instance

    if _fetcher_instance is None:
        _fetcher_instance = ClinVarFetcher()

    return _fetcher_instance
