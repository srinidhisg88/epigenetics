#!/usr/bin/env python3
"""
Test script to verify all frontend URLs are properly generated.
Simulates what the React frontend will receive from the API.
"""

import sys
import json
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.clinvar_fetcher import get_clinvar_fetcher
from backend.pharmgkb_fetcher import get_pharmgkb_fetcher
from rag.retriever import get_retriever
from rag.multi_source_retriever import get_multi_source_retriever


def test_source_urls():
    """Test that all sources generate proper URLs."""
    print("=" * 70)
    print("FRONTEND URL GENERATION TEST")
    print("=" * 70)

    gene = "SCN1A"

    # Initialize components
    print(f"\nInitializing components for gene: {gene}...\n")
    clinvar_fetcher = get_clinvar_fetcher()
    pharmgkb_fetcher = get_pharmgkb_fetcher()
    pubmed_retriever = get_retriever()
    multi_retriever = get_multi_source_retriever(pubmed_retriever)

    # Get comprehensive results
    results = multi_retriever.retrieve_comprehensive(
        gene=gene,
        consequence="missense",
        include_clinvar=True,
        include_pharmgkb=True,
        include_pubmed=True,
        top_k=3
    )

    # Simulate API response sources
    sources = []

    print("1. ClinVar Sources:")
    print("-" * 70)
    if 'clinvar' in results.get('sources', {}):
        for i, cv_variant in enumerate(results['sources']['clinvar']['variants'][:3], 1):
            source = {
                "source": "ClinVar",
                "title": f"{cv_variant['variant_name'][:60]}... - {cv_variant['clinical_significance']}",
                "url": cv_variant['url'],
                "score": 1.0,
                "type": "clinvar"
            }
            sources.append(source)

            print(f"   [{i}] Title: {source['title']}")
            print(f"       URL:   {source['url']}")
            print(f"       Type:  {source['type']}")

            # Validate URL
            if source['url'] and ('clinvar' in source['url'] or 'ncbi.nlm.nih.gov' in source['url']):
                print(f"       ✅ URL is valid and clickable")
            else:
                print(f"       ❌ URL might be invalid: {source['url']}")
            print()

    print("\n2. PharmGKB Sources:")
    print("-" * 70)
    if 'pharmgkb' in results.get('sources', {}):
        pharmgkb_url = f"https://www.pharmgkb.org/gene/{gene}"
        source = {
            "source": "PharmGKB",
            "title": f"Drug-Gene Interactions for {gene}",
            "url": pharmgkb_url,
            "score": 0.95,
            "type": "pharmgkb"
        }
        sources.append(source)

        print(f"   [1] Title: {source['title']}")
        print(f"       URL:   {source['url']}")
        print(f"       Type:  {source['type']}")

        # Validate URL
        if source['url'] and 'pharmgkb.org' in source['url']:
            print(f"       ✅ URL is valid and clickable")
        else:
            print(f"       ❌ URL might be invalid: {source['url']}")
        print()

    print("\n3. PubMed Sources:")
    print("-" * 70)
    if 'pubmed' in results.get('sources', {}):
        for i, chunk in enumerate(results['sources']['pubmed']['chunks'][:3], 1):
            source_file = chunk["source"]
            title = chunk.get("title", "Unknown")

            # Extract PMID
            pmid = None
            url = None
            if source_file.startswith("pmid_") and source_file.endswith(".txt"):
                pmid = source_file[5:-4]
                url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"

            source = {
                "source": source_file,
                "title": title[:70] + "..." if len(title) > 70 else title,
                "pmid": pmid,
                "url": url,
                "score": round(chunk["score"], 4),
                "type": "pubmed"
            }
            sources.append(source)

            print(f"   [{i}] Title: {source['title']}")
            print(f"       PMID:  {source['pmid']}")
            print(f"       URL:   {source['url']}")
            print(f"       Type:  {source['type']}")

            # Validate URL
            if source['url'] and 'pubmed.ncbi.nlm.nih.gov' in source['url']:
                print(f"       ✅ URL is valid and clickable")
            elif source['url'] is None:
                print(f"       ℹ️  Internal guideline (no external URL)")
            else:
                print(f"       ❌ URL might be invalid: {source['url']}")
            print()

    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)

    total_sources = len(sources)
    sources_with_urls = len([s for s in sources if s['url']])
    sources_without_urls = total_sources - sources_with_urls

    print(f"\nTotal sources: {total_sources}")
    print(f"  ✅ With URLs: {sources_with_urls}")
    print(f"  ℹ️  Without URLs (internal): {sources_without_urls}")

    # Validate all URLs
    print("\nURL Validation:")
    valid_domains = ['ncbi.nlm.nih.gov', 'pubmed.ncbi.nlm.nih.gov', 'pharmgkb.org', 'clinvar']

    all_urls_valid = True
    for source in sources:
        if source['url']:
            is_valid = any(domain in source['url'] for domain in valid_domains)
            if not is_valid:
                print(f"  ❌ Invalid URL: {source['url']}")
                all_urls_valid = False

    if all_urls_valid:
        print("  ✅ All URLs are valid and point to trusted medical sources")
    else:
        print("  ❌ Some URLs may be invalid")

    # Generate sample JSON response
    print("\n" + "=" * 70)
    print("SAMPLE API RESPONSE (What Frontend Receives)")
    print("=" * 70)

    sample_response = {
        "prediction": "Pathogenic",
        "confidence": 87.3,
        "pathogenic_probability": 0.873,
        "benign_probability": 0.127,
        "variant_info": {
            "gene": gene,
            "chromosome": "2",
            "reference_allele": "G",
            "alternate_allele": "A",
            "consequence": "missense_variant",
            "variant_type": "single nucleotide variant"
        },
        "is_pathogenic": True,
        "rag_response": "## 🧬 Variant Interpretation\n\nThis SCN1A missense variant...",
        "sources": sources[:5]  # Show first 5 sources
    }

    print(json.dumps(sample_response, indent=2))

    print("\n" + "=" * 70)
    print("TEST RESULT")
    print("=" * 70)

    if all_urls_valid and sources_with_urls >= 3:
        print("\n✅ SUCCESS: All URLs are properly generated!")
        print("   Frontend can display clickable source links.")
        return 0
    else:
        print("\n❌ FAILURE: Some URLs may not be properly generated.")
        return 1


if __name__ == "__main__":
    sys.exit(test_source_urls())
