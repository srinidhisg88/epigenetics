"""
PharmGKB Fetcher module for Epilepsy Diagnostic Assistant.

Automatically downloads and caches drug-gene interactions from PharmGKB database.
No manual curation - all data fetched from official PharmGKB TSV files.
"""

import os
import csv
import json
import sqlite3
import zipfile
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Set
from pathlib import Path
from io import BytesIO

import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# PharmGKB data URLs (official download endpoints)
PHARMGKB_CLINICAL_ANNOTATIONS_URL = "https://s3.pgkb.org/data/clinicalAnnotations.zip"

# Local data directory
DATA_DIR = Path("data/pharmgkb")
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Cache database
CACHE_DB = Path("cache/pharmgkb/pharmgkb_cache.db")
CACHE_DB.parent.mkdir(parents=True, exist_ok=True)

# Cache validity (30 days)
CACHE_VALIDITY_DAYS = 30

# Epilepsy-relevant genes
EPILEPSY_GENES = {
    'SCN1A', 'SCN2A', 'SCN3A', 'SCN8A', 'SCN9A',
    'KCNQ2', 'KCNQ3', 'KCNT1', 'KCNMA1',
    'SLC2A1', 'SLC6A1', 'SLC13A5',
    'TSC1', 'TSC2', 'MTOR',
    'ALDH7A1', 'PNPO', 'CDKL5',
    'STXBP1', 'PCDH19', 'CHD2',
    'GABRA1', 'GABRG2', 'GABRD',
    'DEPDC5', 'NPRL2', 'NPRL3'
}

# Epilepsy-relevant drugs (AEDs - Anti-Epileptic Drugs)
EPILEPSY_DRUGS = {
    # Sodium channel blockers
    'carbamazepine', 'oxcarbazepine', 'lamotrigine', 'phenytoin',
    'lacosamide', 'eslicarbazepine',
    # GABAergic
    'valproate', 'valproic acid', 'sodium valproate', 'gabapentin',
    'pregabalin', 'vigabatrin', 'tiagabine',
    # Benzodiazepines
    'clobazam', 'clonazepam', 'diazepam', 'lorazepam', 'midazolam',
    # Broad spectrum
    'levetiracetam', 'topiramate', 'zonisamide', 'perampanel',
    # Other AEDs
    'ethosuximide', 'phenobarbital', 'primidone', 'stiripentol',
    'rufinamide', 'cannabidiol', 'fenfluramine', 'cenobamate',
    # Additional
    'retigabine', 'ezogabine', 'everolimus', 'pyridoxine',
    # Generic terms
    'antiepileptics', 'antiepileptic', 'anticonvulsants'
}


class PharmGKBFetcher:
    """
    Fetches drug-gene interaction data from PharmGKB automatically.
    Downloads official TSV files and caches results.
    """

    def __init__(self):
        """Initialize PharmGKB Fetcher."""
        self.data_dir = DATA_DIR
        self._init_cache()
        self._ensure_data_downloaded()

    def _init_cache(self):
        """Initialize SQLite cache database."""
        conn = sqlite3.connect(CACHE_DB)
        cursor = conn.cursor()

        # Table for clinical annotations
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS clinical_annotations (
                annotation_id TEXT PRIMARY KEY,
                gene TEXT,
                variant TEXT,
                drug TEXT,
                phenotype TEXT,
                evidence_level TEXT,
                score REAL,
                phenotype_category TEXT,
                pmid_count INTEGER,
                url TEXT,
                raw_data TEXT,
                downloaded_at TIMESTAMP
            )
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_gene
            ON clinical_annotations(gene)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_drug
            ON clinical_annotations(drug)
        """)

        # Table for download metadata
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS download_metadata (
                id INTEGER PRIMARY KEY,
                source TEXT,
                downloaded_at TIMESTAMP,
                file_path TEXT,
                record_count INTEGER
            )
        """)

        conn.commit()
        conn.close()

    def _is_cache_valid(self) -> bool:
        """Check if cached data is still valid (within 30 days)."""
        conn = sqlite3.connect(CACHE_DB)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT downloaded_at FROM download_metadata
            WHERE source = 'clinical_annotations'
            ORDER BY downloaded_at DESC LIMIT 1
        """)

        result = cursor.fetchone()
        conn.close()

        if not result:
            return False

        downloaded_at = datetime.fromisoformat(result[0])
        age = datetime.now() - downloaded_at

        return age.days < CACHE_VALIDITY_DAYS

    def _ensure_data_downloaded(self):
        """Ensure PharmGKB data is downloaded and cached."""
        if self._is_cache_valid():
            print(f"PharmGKB cache is valid (< {CACHE_VALIDITY_DAYS} days old)")
            return

        print("Downloading PharmGKB clinical annotations...")
        self._download_clinical_annotations()

    def _download_clinical_annotations(self):
        """Download and parse clinical annotations from PharmGKB."""
        try:
            # Download ZIP file
            response = requests.get(PHARMGKB_CLINICAL_ANNOTATIONS_URL, timeout=60)
            response.raise_for_status()

            # Extract TSV from ZIP
            with zipfile.ZipFile(BytesIO(response.content)) as z:
                # Read clinical_annotations.tsv
                with z.open('clinical_annotations.tsv') as f:
                    content = f.read().decode('utf-8')

            # Parse TSV
            reader = csv.DictReader(content.splitlines(), delimiter='\t')

            conn = sqlite3.connect(CACHE_DB)
            cursor = conn.cursor()

            # Clear old data
            cursor.execute("DELETE FROM clinical_annotations")

            record_count = 0
            epilepsy_record_count = 0

            for row in reader:
                annotation_id = row.get('Clinical Annotation ID', '')
                variant = row.get('Variant/Haplotypes', '')
                gene = row.get('Gene', '')
                evidence_level = row.get('Level of Evidence', '')
                score = row.get('Score', '0')
                phenotype_category = row.get('Phenotype Category', '')
                pmid_count = row.get('PMID Count', '0')
                drugs = row.get('Drug(s)', '')
                phenotypes = row.get('Phenotype(s)', '')
                url = row.get('URL', '')

                # Skip if no gene
                if not gene:
                    continue

                # Parse score
                try:
                    score_float = float(score) if score else 0.0
                except:
                    score_float = 0.0

                # Parse PMID count
                try:
                    pmid_count_int = int(pmid_count) if pmid_count else 0
                except:
                    pmid_count_int = 0

                # Check if epilepsy-relevant (gene OR drug)
                is_epilepsy_gene = gene.upper() in EPILEPSY_GENES
                drugs_lower = drugs.lower()
                is_epilepsy_drug = any(drug in drugs_lower for drug in EPILEPSY_DRUGS)

                # Only store epilepsy-relevant annotations
                if is_epilepsy_gene or is_epilepsy_drug:
                    cursor.execute("""
                        INSERT INTO clinical_annotations
                        (annotation_id, gene, variant, drug, phenotype, evidence_level,
                         score, phenotype_category, pmid_count, url, raw_data, downloaded_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        annotation_id, gene, variant, drugs, phenotypes, evidence_level,
                        score_float, phenotype_category, pmid_count_int, url,
                        json.dumps(row), datetime.now().isoformat()
                    ))
                    epilepsy_record_count += 1

                record_count += 1

            # Update metadata
            cursor.execute("""
                INSERT INTO download_metadata (source, downloaded_at, file_path, record_count)
                VALUES (?, ?, ?, ?)
            """, ('clinical_annotations', datetime.now().isoformat(),
                  'clinical_annotations.tsv', epilepsy_record_count))

            conn.commit()
            conn.close()

            print(f"✅ Downloaded {record_count} total annotations")
            print(f"✅ Stored {epilepsy_record_count} epilepsy-relevant annotations")

        except Exception as e:
            print(f"❌ Error downloading PharmGKB data: {e}")
            print("   Will use cached data if available")

    def get_drug_gene_interactions(self, gene: str) -> List[Dict]:
        """
        Get drug-gene interactions for a specific gene from PharmGKB.

        Args:
            gene: Gene symbol (e.g., 'SCN1A')

        Returns:
            List of interaction dictionaries
        """
        gene_upper = gene.upper()

        conn = sqlite3.connect(CACHE_DB)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT annotation_id, gene, variant, drug, phenotype, evidence_level,
                   score, phenotype_category, pmid_count, url
            FROM clinical_annotations
            WHERE UPPER(gene) = ?
            ORDER BY score DESC, pmid_count DESC
        """, (gene_upper,))

        results = cursor.fetchall()
        conn.close()

        interactions = []
        for row in results:
            interactions.append({
                'annotation_id': row[0],
                'gene': row[1],
                'variant': row[2],
                'drug': row[3],
                'phenotype': row[4],
                'evidence_level': row[5],
                'score': row[6],
                'phenotype_category': row[7],
                'pmid_count': row[8],
                'url': row[9],
                'source': 'PharmGKB'
            })

        return interactions

    def get_drug_recommendations(self, gene: str) -> Dict:
        """
        Get categorized drug recommendations for a gene.

        Args:
            gene: Gene symbol

        Returns:
            Dictionary with interactions organized by category
        """
        interactions = self.get_drug_gene_interactions(gene)

        # Organize by phenotype category
        recommendations = {
            'efficacy': [],
            'toxicity': [],
            'dosage': [],
            'other': []
        }

        for interaction in interactions:
            category = interaction['phenotype_category'].lower()

            drug_info = {
                'drug': interaction['drug'],
                'variant': interaction['variant'],
                'phenotype': interaction['phenotype'],
                'evidence_level': interaction['evidence_level'],
                'score': interaction['score'],
                'pmid_count': interaction['pmid_count'],
                'url': interaction['url']
            }

            if 'efficacy' in category:
                recommendations['efficacy'].append(drug_info)
            elif 'toxicity' in category or 'adverse' in category:
                recommendations['toxicity'].append(drug_info)
            elif 'dosage' in category or 'metabolism' in category:
                recommendations['dosage'].append(drug_info)
            else:
                recommendations['other'].append(drug_info)

        return recommendations

    def format_for_rag(self, gene: str) -> str:
        """
        Format drug-gene interactions for RAG context.

        Args:
            gene: Gene symbol

        Returns:
            Formatted string for RAG retrieval
        """
        recommendations = self.get_drug_recommendations(gene)

        output = [f"PharmGKB Drug-Gene Interactions for {gene}:\n"]

        total_interactions = sum(len(v) for v in recommendations.values())
        if total_interactions == 0:
            return f"No PharmGKB drug-gene interactions found for {gene}."

        # Efficacy interactions
        if recommendations['efficacy']:
            output.append(f"DRUG EFFICACY ({len(recommendations['efficacy'])} annotations):")
            for drug in recommendations['efficacy'][:5]:  # Top 5
                evidence = f"Level {drug['evidence_level']}" if drug['evidence_level'] else "Unknown level"
                output.append(f"• {drug['drug']} ({drug['variant']})")
                output.append(f"  Phenotype: {drug['phenotype']}")
                output.append(f"  Evidence: {evidence}, Score: {drug['score']}, PMIDs: {drug['pmid_count']}")
            output.append("")

        # Toxicity/adverse events
        if recommendations['toxicity']:
            output.append(f"⚠️ TOXICITY/ADVERSE EVENTS ({len(recommendations['toxicity'])} annotations):")
            for drug in recommendations['toxicity'][:5]:  # Top 5
                evidence = f"Level {drug['evidence_level']}" if drug['evidence_level'] else "Unknown level"
                output.append(f"• {drug['drug']} ({drug['variant']})")
                output.append(f"  Phenotype: {drug['phenotype']}")
                output.append(f"  Evidence: {evidence}, Score: {drug['score']}, PMIDs: {drug['pmid_count']}")
            output.append("")

        # Dosage recommendations
        if recommendations['dosage']:
            output.append(f"DOSAGE RECOMMENDATIONS ({len(recommendations['dosage'])} annotations):")
            for drug in recommendations['dosage'][:3]:  # Top 3
                evidence = f"Level {drug['evidence_level']}" if drug['evidence_level'] else "Unknown level"
                output.append(f"• {drug['drug']} ({drug['variant']})")
                output.append(f"  Phenotype: {drug['phenotype']}")
                output.append(f"  Evidence: {evidence}")
            output.append("")

        output.append(f"Source: PharmGKB (https://www.pharmgkb.org/search?query={gene})")

        return "\n".join(output)

    def get_all_genes_with_interactions(self) -> List[str]:
        """Get list of all genes with documented interactions."""
        conn = sqlite3.connect(CACHE_DB)
        cursor = conn.cursor()

        cursor.execute("SELECT DISTINCT gene FROM clinical_annotations ORDER BY gene")
        results = cursor.fetchall()
        conn.close()

        return [row[0] for row in results]

    def get_statistics(self) -> Dict:
        """Get statistics about cached PharmGKB data."""
        conn = sqlite3.connect(CACHE_DB)
        cursor = conn.cursor()

        stats = {}

        # Total annotations
        cursor.execute("SELECT COUNT(*) FROM clinical_annotations")
        stats['total_annotations'] = cursor.fetchone()[0]

        # Total genes
        cursor.execute("SELECT COUNT(DISTINCT gene) FROM clinical_annotations")
        stats['total_genes'] = cursor.fetchone()[0]

        # Last download
        cursor.execute("""
            SELECT downloaded_at, record_count FROM download_metadata
            WHERE source = 'clinical_annotations'
            ORDER BY downloaded_at DESC LIMIT 1
        """)
        result = cursor.fetchone()
        if result:
            stats['last_download'] = result[0]
            stats['downloaded_records'] = result[1]

        conn.close()

        return stats


# Singleton instance
_fetcher_instance: Optional[PharmGKBFetcher] = None


def get_pharmgkb_fetcher() -> PharmGKBFetcher:
    """
    Get or create singleton PharmGKBFetcher instance.

    Returns:
        PharmGKBFetcher instance
    """
    global _fetcher_instance

    if _fetcher_instance is None:
        _fetcher_instance = PharmGKBFetcher()

    return _fetcher_instance
