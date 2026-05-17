"""
GeneReviews fetcher for Epilepsy Diagnostic Assistant.

GeneReviews chapters are indexed as regular PubMed entries.
We use verified PMIDs for genes that have chapters, and fall back to
recent clinical review papers for genes without GeneReviews chapters.
"""

import os
import re
import time
import requests
from pathlib import Path
from typing import Optional, Dict
from dotenv import load_dotenv

load_dotenv()

NCBI_API_KEY = os.getenv("NCBI_API_KEY", "")
ESEARCH_URL  = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
EFETCH_URL   = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"

OUTPUT_DIR = Path("data/knowledge_base/genereview")

# Verified GeneReviews PMIDs for epilepsy panel genes.
# Confirmed by fetching and checking gene name appears in abstract.
GENEREVIEW_PMIDS: Dict[str, str] = {
    # Voltage-gated sodium channels
    "SCN1A":  "20301494",  # SCN1A Seizure Disorders (Dravet, GEFS+)
    "SCN3A":  "34081427",  # SCN3A-Related Neurodevelopmental Disorder
    "SCN8A":  "27559564",  # SCN8A-Related Epilepsy and/or Neurodevelopmental Disorders
    # Voltage-gated potassium channels
    "KCNQ2":  "20437616",  # KCNQ2-Related Disorders
    "KCNQ3":  "24851285",  # KCNQ3-Related Disorders
    # GABA-A receptor subunits
    "GABRA1": "24980848",  # GABRA1-Related Epilepsy
    # mTOR pathway
    "TSC1":   "20301399",  # Tuberous Sclerosis Complex (covers TSC1 + TSC2)
    "TSC2":   "20301399",  # Tuberous Sclerosis Complex (same chapter)
    # Neurodevelopmental loci
    "CDKL5":  "38603524",  # CDKL5 Deficiency Disorder
    "MECP2":  "20301670",  # MECP2 Disorders (Rett Syndrome)
    "STXBP1": "27905812",  # STXBP1 Encephalopathy with Epilepsy
    "PCDH19": "27560212",  # PCDH19-Related Epilepsy
    "SLC2A1": "20301603",  # GLUT1 Deficiency Syndrome
    "SLC6A1": "36780407",  # SLC6A1-Related Neurodevelopmental Disorder
}

# Genes without confirmed GeneReviews chapters — search for best clinical review
FALLBACK_QUERIES: Dict[str, list] = {
    # Sodium channels
    "SCN2A":   ["SCN2A epilepsy encephalopathy treatment review", "SCN2A gain loss function seizure"],
    "SCN9A":   ["SCN9A epilepsy febrile seizures GEFS review"],
    # GABA receptor
    "GABRG2":  ["GABRG2 GEFS Dravet epilepsy treatment review", "GABRG2 epilepsy febrile seizures"],
    # mTOR pathway
    "DEPDC5":  ["DEPDC5 GATOR1 focal epilepsy treatment review", "DEPDC5 familial focal epilepsy"],
    "NPRL3":   ["NPRL3 GATOR1 focal epilepsy treatment review", "NPRL3 familial focal epilepsy cortical dysplasia"],
    # Neurodevelopmental
    "ARX":     ["ARX epilepsy intellectual disability treatment review", "ARX Ohtahara West syndrome"],
    "FOXG1":   ["FOXG1 syndrome epilepsy treatment review", "FOXG1 congenital Rett variant epilepsy"],
    "CHD2":    ["CHD2 myoclonic epilepsy encephalopathy treatment review"],
    "PLCB1":   ["PLCB1 epileptic encephalopathy infantile treatment review"],
    "PRRT2":   ["PRRT2 benign familial infantile epilepsy treatment review", "PRRT2 paroxysmal kinesigenic dyskinesia"],
    "TBC1D24": ["TBC1D24 DOORS syndrome focal epilepsy treatment review"],
    "ALDH7A1": ["ALDH7A1 pyridoxine dependent epilepsy treatment review"],
}


def _api_params(**kwargs) -> dict:
    p = {**kwargs}
    if NCBI_API_KEY:
        p["api_key"] = NCBI_API_KEY
    return p


def fetch_abstract_text(pmid: str) -> Optional[str]:
    """Fetch full abstract text for a PubMed PMID."""
    try:
        r = requests.get(EFETCH_URL, params=_api_params(
            db="pubmed", id=pmid, rettype="abstract", retmode="text"
        ), timeout=15)
        text = r.text.strip()
        return text if len(text) > 100 else None
    except Exception as e:
        print(f"    Fetch error PMID {pmid}: {e}")
        return None


def search_best_review(gene: str, queries: list) -> Optional[str]:
    """Search PubMed for the best available review paper for a gene."""
    for query in queries:
        try:
            r = requests.get(ESEARCH_URL, params=_api_params(
                db="pubmed", term=query, retmode="json",
                retmax=3, sort="relevance"
            ), timeout=10)
            ids = r.json().get("esearchresult", {}).get("idlist", [])
            for pmid in ids:
                abstract = fetch_abstract_text(pmid)
                if abstract and gene in abstract.upper()[:800]:
                    return pmid
                time.sleep(0.3)
        except Exception:
            pass
        time.sleep(0.35)
    return None


def format_knowledge_file(gene: str, pmid: str, abstract_text: str, is_genereview: bool) -> str:
    """Format fetched content as a structured knowledge-base text file."""
    source_label = "GeneReviews (NCBI Bookshelf)" if is_genereview else "PubMed Clinical Review"
    lines = [
        f"Gene: {gene}",
        f"PMID: {pmid}",
        f"Source: {source_label}",
        f"URL: https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
        "",
        "=== CLINICAL CONTENT ===",
        "",
        abstract_text,
        "",
    ]
    return "\n".join(lines)


def fetch_all_genereview(output_dir: Path = OUTPUT_DIR, delay: float = 0.5) -> Dict[str, str]:
    """
    Fetch clinical content for all epilepsy panel genes.
    Uses verified GeneReviews PMIDs first, then searches for review papers.
    Saves as genereview_{GENE}.txt in output_dir.
    Returns {gene: pmid} for all genes successfully fetched.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    all_genes = list(GENEREVIEW_PMIDS.keys()) + list(FALLBACK_QUERIES.keys())
    found = {}

    for gene in all_genes:
        out_path = output_dir / f"genereview_{gene}.txt"

        if out_path.exists():
            print(f"  {gene}: cached")
            found[gene] = "cached"
            continue

        is_genereview = gene in GENEREVIEW_PMIDS
        pmid = GENEREVIEW_PMIDS.get(gene)

        if pmid:
            print(f"  {gene}: fetching GeneReviews PMID {pmid}...")
            abstract = fetch_abstract_text(pmid)
        else:
            print(f"  {gene}: no GeneReviews — searching for review paper...")
            queries = FALLBACK_QUERIES.get(gene, [f"{gene} epilepsy treatment review"])
            pmid = search_best_review(gene, queries)
            abstract = fetch_abstract_text(pmid) if pmid else None

        if not abstract:
            print(f"  {gene}: no content found, skipping")
            time.sleep(delay)
            continue

        content = format_knowledge_file(gene, pmid, abstract, is_genereview)
        out_path.write_text(content, encoding="utf-8")
        label = "GeneReviews" if is_genereview else "review"
        print(f"  {gene}: saved ({label}, PMID {pmid})")
        found[gene] = pmid
        time.sleep(delay)

    return found


if __name__ == "__main__":
    print("Fetching GeneReviews / clinical reviews for epilepsy gene panel...\n")
    result = fetch_all_genereview()
    fetched = len([v for v in result.values() if v != "cached"])
    cached = len([v for v in result.values() if v == "cached"])
    print(f"\nDone. {fetched} fetched, {cached} cached.")
