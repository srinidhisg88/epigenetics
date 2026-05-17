#!/usr/bin/env python3
"""
Fetch authoritative clinical guidelines for the epilepsy knowledge base.

Replaces the LLM-generated treatment_guidelines.txt with two real sources:

1. GeneReviews (NCBI Bookshelf) — per-gene expert chapters covering
   clinical features, diagnosis, and management for all 26 panel genes.

2. ILAE Practice Guidelines — key International League Against Epilepsy
   consensus papers on epilepsy classification and treatment fetched via PubMed.

After fetching, rebuilds the FAISS index automatically.

Usage:
    cd /path/to/epilepsy_diagnostic_assistant
    python scripts/fetch_guidelines.py
"""

import os
import sys
import re
import time
import requests
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.genereview_fetcher import fetch_all_genereview, OUTPUT_DIR as GENEREVIEW_DIR
from dotenv import load_dotenv

load_dotenv()

NCBI_API_KEY = os.getenv("NCBI_API_KEY", "")
ESEARCH_URL  = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
EFETCH_URL   = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"

PUBMED_DIR = Path("data/knowledge_base/pubmed_abstracts")

# ── Known ILAE guideline PMIDs ────────────────────────────────────────────────
# These are authoritative ILAE papers on epilepsy classification & treatment.
KNOWN_ILAE_PMIDS = [
    "28276060",  # ILAE 2017 operational classification of seizure types (Fisher)
    "28276062",  # ILAE 2017 classification of the epilepsies (Scheffer)
    "24730690",  # ILAE 2014 practical clinical definition of epilepsy (Fisher)
    "26336950",  # ILAE 2015 definition/classification of status epilepticus (Trinka)
    "25901057",  # Evidence-based guideline: first unprovoked seizure in adults (Krumholz 2015)
    "26122601",  # ILAE recommendations for management of infantile seizures
    "23350722",  # Updated ILAE AED efficacy/effectiveness review (Glauser 2013)
]

# ── PubMed search for additional ILAE guidelines ──────────────────────────────
ILAE_SEARCH_QUERIES = [
    '"International League Against Epilepsy"[au] AND epilepsy[mesh] AND "practice guideline"[pt]',
    'ILAE[title] AND epilepsy AND guideline AND treatment',
    'epilepsy genetic treatment guideline consensus 2020:2024[dp]',
]


def _api_params(**kwargs) -> dict:
    p = {"retmode": "json", **kwargs}
    if NCBI_API_KEY:
        p["api_key"] = NCBI_API_KEY
    return p


def search_pubmed(query: str, max_results: int = 10) -> list:
    try:
        r = requests.get(ESEARCH_URL, params=_api_params(
            db="pubmed", term=query, retmax=max_results, sort="relevance"
        ), timeout=10)
        return r.json().get("esearchresult", {}).get("idlist", [])
    except Exception as e:
        print(f"  Search error: {e}")
        return []


def fetch_and_save_abstract(pmid: str, delay: float = 0.4) -> bool:
    """Fetch a PubMed abstract and save as pmid_{pmid}.txt. Returns True if saved."""
    out_path = PUBMED_DIR / f"pmid_{pmid}.txt"
    if out_path.exists():
        print(f"    PMID {pmid}: already exists, skipping")
        return True

    try:
        r = requests.get(EFETCH_URL, params={
            "db": "pubmed", "id": pmid,
            "rettype": "abstract", "retmode": "xml",
            **({"api_key": NCBI_API_KEY} if NCBI_API_KEY else {})
        }, timeout=15)
        xml = r.text

        # Extract fields
        title_m  = re.search(r'<ArticleTitle>(.*?)</ArticleTitle>', xml, re.DOTALL)
        title    = re.sub(r'<[^>]+>', '', title_m.group(1)).strip() if title_m else f"PMID {pmid}"

        abs_parts = re.findall(r'<AbstractText[^>]*>(.*?)</AbstractText>', xml, re.DOTALL)
        abstract  = " ".join(re.sub(r'<[^>]+>', '', p).strip() for p in abs_parts)

        journal_m = re.search(r'<Title>(.*?)</Title>', xml, re.DOTALL)
        journal   = re.sub(r'<[^>]+>', '', journal_m.group(1)).strip() if journal_m else ""

        year_m = re.search(r'<PubDate>.*?<Year>(\d{4})</Year>', xml, re.DOTALL)
        year   = year_m.group(1) if year_m else ""

        if not abstract:
            print(f"    PMID {pmid}: no abstract, skipping")
            return False

        content = (
            f"Title: {title}\n"
            f"Journal: {journal}\n"
            f"Year: {year}\n"
            f"PMID: {pmid}\n"
            f"URL: https://pubmed.ncbi.nlm.nih.gov/{pmid}/\n"
            f"Source: ILAE Guidelines / Practice Guideline\n\n"
            f"{abstract}\n"
        )
        out_path.write_text(content, encoding="utf-8")
        print(f"    PMID {pmid}: saved — {title[:70]}")
        time.sleep(delay)
        return True

    except Exception as e:
        print(f"    PMID {pmid}: error — {e}")
        return False


def fetch_ilae_guidelines():
    """Fetch ILAE guideline papers into the pubmed_abstracts directory."""
    PUBMED_DIR.mkdir(parents=True, exist_ok=True)
    saved = set()

    # Step 1: Fetch known ILAE PMIDs
    print("\n[ILAE] Fetching known guideline papers...")
    for pmid in KNOWN_ILAE_PMIDS:
        if fetch_and_save_abstract(pmid):
            saved.add(pmid)

    # Step 2: Search for additional ILAE guidelines
    print("\n[ILAE] Searching PubMed for additional guideline papers...")
    for query in ILAE_SEARCH_QUERIES:
        print(f"  Query: {query[:60]}...")
        pmids = search_pubmed(query, max_results=5)
        for pmid in pmids:
            if pmid not in saved:
                if fetch_and_save_abstract(pmid):
                    saved.add(pmid)
        time.sleep(0.5)

    print(f"\n[ILAE] Total guideline papers saved: {len(saved)}")
    return saved


def rebuild_faiss_index():
    """Re-run build_knowledge_base.py using the base conda Python (has sentence_transformers)."""
    import subprocess, shutil
    print("\n[FAISS] Rebuilding knowledge base index...")

    # Prefer base conda Python which has sentence_transformers + faiss installed
    candidates = [
        "/opt/anaconda3/bin/python3",
        "/opt/homebrew/anaconda3/bin/python3",
        shutil.which("conda") and shutil.which("conda").replace("bin/conda", "bin/python3"),
        sys.executable,
    ]
    python_bin = next((p for p in candidates if p and __import__("os").path.isfile(p)), sys.executable)
    print(f"  Using Python: {python_bin}")

    result = subprocess.run(
        [python_bin, "scripts/build_knowledge_base.py"],
        capture_output=False
    )
    if result.returncode == 0:
        print("[FAISS] Index rebuilt successfully.")
    else:
        print(f"[FAISS] Failed. Run manually:\n  {python_bin} scripts/build_knowledge_base.py")


def remove_llm_guidelines():
    """Delete the LLM-generated treatment_guidelines.txt."""
    path = Path("data/knowledge_base/treatment_guidelines.txt")
    if path.exists():
        path.unlink()
        print(f"\n[Cleanup] Deleted LLM-generated file: {path}")
    else:
        print(f"\n[Cleanup] {path} not found (already removed).")


def main():
    print("=" * 60)
    print("Fetching Authoritative Epilepsy Clinical Guidelines")
    print("=" * 60)

    # 1. GeneReviews
    print("\n[1/3] Fetching GeneReviews for 26-gene epilepsy panel...")
    gr_results = fetch_all_genereview(output_dir=GENEREVIEW_DIR)
    print(f"  GeneReviews fetched: {len([v for v in gr_results.values() if v != 'cached'])} new, "
          f"{len([v for v in gr_results.values() if v == 'cached'])} cached")

    # 2. ILAE guidelines
    print("\n[2/3] Fetching ILAE practice guidelines...")
    ilae_pmids = fetch_ilae_guidelines()

    # 3. Remove LLM file + rebuild index
    remove_llm_guidelines()
    print("\n[3/3] Rebuilding FAISS index with real sources...")
    rebuild_faiss_index()

    print("\n" + "=" * 60)
    print("Done! Knowledge base now uses authoritative clinical sources:")
    print(f"  • GeneReviews: {len(gr_results)} gene chapters")
    print(f"  • ILAE guidelines: {len(ilae_pmids)} papers")
    print("=" * 60)


if __name__ == "__main__":
    main()
