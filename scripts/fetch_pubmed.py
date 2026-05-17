#!/usr/bin/env python3
"""
Fetch PubMed abstracts for epilepsy-related genetic variants.
Uses NCBI E-utilities API (free, no key required for small volumes).

Output: data/knowledge_base/pubmed_abstracts/ directory with one .txt file per abstract
"""

import os
import time
import json
import requests
from pathlib import Path
from typing import List, Dict, Optional

# NCBI E-utilities base URLs
ESEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
EFETCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"

# Target epilepsy genes (all 26 from the model)
EPILEPSY_GENES = [
    'SCN1A', 'SCN2A', 'SCN3A', 'SCN8A',
    'KCNQ2', 'KCNQ3',
    'GABRA1', 'GABRG2',
    'TSC1', 'TSC2',
    'MECP2', 'CDKL5', 'FOXG1', 'PCDH19',
    'SLC2A1', 'SLC6A1',
    'ARX', 'STXBP1', 'DEPDC5', 'TBC1D24',
    'LGI1', 'GRIN2A', 'CHD2', 'PRRT2', 'ALDH7A1', 'CACNA1A'
]

# Search queries for comprehensive coverage
SEARCH_QUERIES = [
    # Gene-specific queries
    *[f"{gene} epilepsy variant pathogenicity" for gene in EPILEPSY_GENES],
    *[f"{gene} epilepsy treatment" for gene in EPILEPSY_GENES[:10]],  # Top genes

    # General epilepsy genetics queries
    "epilepsy genetic variant classification",
    "epilepsy pathogenicity prediction machine learning",
    "genetic epilepsy treatment guidelines",
    "epileptic encephalopathy genetic diagnosis",
    "ACMG variant classification epilepsy",
    "ion channel epilepsy genetics",
    "sodium channel epilepsy SCN1A SCN2A",
    "potassium channel epilepsy KCNQ2",
    "mTOR pathway epilepsy TSC",
    "Dravet syndrome treatment",
    "CDKL5 deficiency disorder treatment",
    "Rett syndrome MECP2 epilepsy",
    "GLUT1 deficiency ketogenic diet",
    "pyridoxine dependent epilepsy ALDH7A1",
    "genetic testing epilepsy diagnosis",
    "variant of uncertain significance epilepsy",
    "loss of function gain of function epilepsy",
    "precision medicine epilepsy genetics",
]


def search_pubmed(query: str, max_results: int = 10) -> List[str]:
    """
    Search PubMed and return list of PMIDs.

    Args:
        query: Search query string
        max_results: Maximum number of results to return

    Returns:
        List of PMID strings
    """
    params = {
        "db": "pubmed",
        "term": query,
        "retmax": max_results,
        "retmode": "json",
        "sort": "relevance"
    }

    try:
        response = requests.get(ESEARCH_URL, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()

        pmids = data.get("esearchresult", {}).get("idlist", [])
        return pmids

    except requests.RequestException as e:
        print(f"Error searching PubMed for '{query}': {e}")
        return []


def fetch_abstract(pmid: str) -> Optional[Dict]:
    """
    Fetch abstract and metadata for a given PMID.

    Args:
        pmid: PubMed ID

    Returns:
        Dictionary with title, abstract, authors, journal, year, pmid
    """
    params = {
        "db": "pubmed",
        "id": pmid,
        "rettype": "abstract",
        "retmode": "xml"
    }

    try:
        response = requests.get(EFETCH_URL, params=params, timeout=30)
        response.raise_for_status()

        # Parse XML response
        from xml.etree import ElementTree as ET
        root = ET.fromstring(response.content)

        article = root.find(".//PubmedArticle")
        if article is None:
            return None

        # Extract title
        title_elem = article.find(".//ArticleTitle")
        title = title_elem.text if title_elem is not None else "No title"

        # Extract abstract
        abstract_parts = []
        abstract_elem = article.find(".//Abstract")
        if abstract_elem is not None:
            for text in abstract_elem.findall(".//AbstractText"):
                label = text.get("Label", "")
                content = text.text or ""
                if label:
                    abstract_parts.append(f"{label}: {content}")
                else:
                    abstract_parts.append(content)
        abstract = " ".join(abstract_parts) if abstract_parts else "No abstract available"

        # Extract authors
        authors = []
        for author in article.findall(".//Author"):
            last_name = author.find("LastName")
            fore_name = author.find("ForeName")
            if last_name is not None:
                name = last_name.text
                if fore_name is not None:
                    name = f"{fore_name.text} {name}"
                authors.append(name)

        # Extract journal
        journal_elem = article.find(".//Journal/Title")
        journal = journal_elem.text if journal_elem is not None else "Unknown journal"

        # Extract year
        year_elem = article.find(".//PubDate/Year")
        year = year_elem.text if year_elem is not None else "Unknown year"

        # Extract MeSH terms
        mesh_terms = []
        for mesh in article.findall(".//MeshHeading/DescriptorName"):
            if mesh.text:
                mesh_terms.append(mesh.text)

        return {
            "pmid": pmid,
            "title": title,
            "abstract": abstract,
            "authors": authors[:5],  # First 5 authors
            "journal": journal,
            "year": year,
            "mesh_terms": mesh_terms[:10]  # First 10 MeSH terms
        }

    except Exception as e:
        print(f"Error fetching PMID {pmid}: {e}")
        return None


def save_abstract(abstract_data: Dict, output_dir: Path) -> str:
    """
    Save abstract to a text file.

    Args:
        abstract_data: Dictionary with abstract information
        output_dir: Output directory path

    Returns:
        Path to saved file
    """
    pmid = abstract_data["pmid"]
    filename = f"pmid_{pmid}.txt"
    filepath = output_dir / filename

    # Format the content
    content = f"""PMID: {pmid}
Title: {abstract_data['title']}
Authors: {', '.join(abstract_data['authors'])}
Journal: {abstract_data['journal']}
Year: {abstract_data['year']}
MeSH Terms: {', '.join(abstract_data['mesh_terms'])}

Abstract:
{abstract_data['abstract']}
"""

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

    return str(filepath)


def main():
    """Main function to fetch all PubMed abstracts."""

    # Setup output directory
    script_dir = Path(__file__).parent.parent
    output_dir = script_dir / "data" / "knowledge_base" / "pubmed_abstracts"
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Output directory: {output_dir}")
    print(f"Number of search queries: {len(SEARCH_QUERIES)}")
    print("-" * 50)

    # Track all PMIDs to avoid duplicates
    all_pmids = set()
    fetched_abstracts = []

    # Search and collect PMIDs
    print("\n[1/2] Searching PubMed for relevant articles...")
    for i, query in enumerate(SEARCH_QUERIES):
        print(f"  [{i+1}/{len(SEARCH_QUERIES)}] Searching: {query[:50]}...")
        pmids = search_pubmed(query, max_results=8)
        new_pmids = [p for p in pmids if p not in all_pmids]
        all_pmids.update(new_pmids)
        print(f"    Found {len(pmids)} results, {len(new_pmids)} new")

        # Rate limiting - be nice to NCBI servers
        time.sleep(0.4)

    print(f"\nTotal unique PMIDs found: {len(all_pmids)}")

    # Fetch abstracts
    print("\n[2/2] Fetching abstracts...")
    pmid_list = list(all_pmids)

    for i, pmid in enumerate(pmid_list):
        if (i + 1) % 20 == 0:
            print(f"  Progress: {i+1}/{len(pmid_list)}")

        abstract_data = fetch_abstract(pmid)
        if abstract_data and abstract_data["abstract"] != "No abstract available":
            filepath = save_abstract(abstract_data, output_dir)
            fetched_abstracts.append({
                "pmid": pmid,
                "title": abstract_data["title"],
                "file": filepath
            })

        # Rate limiting
        time.sleep(0.35)

    # Save index
    index_path = output_dir / "index.json"
    with open(index_path, 'w', encoding='utf-8') as f:
        json.dump({
            "total_abstracts": len(fetched_abstracts),
            "fetch_date": time.strftime("%Y-%m-%d %H:%M:%S"),
            "abstracts": fetched_abstracts
        }, f, indent=2)

    print("\n" + "=" * 50)
    print(f"Completed!")
    print(f"  Total abstracts fetched: {len(fetched_abstracts)}")
    print(f"  Output directory: {output_dir}")
    print(f"  Index file: {index_path}")
    print("=" * 50)


if __name__ == "__main__":
    main()
