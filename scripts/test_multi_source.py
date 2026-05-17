#!/usr/bin/env python3
"""
Test script for multi-source integration.
Verifies ClinVar, PharmGKB, and Multi-Source Retriever functionality.
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.clinvar_fetcher import get_clinvar_fetcher
from backend.pharmgkb_fetcher import get_pharmgkb_fetcher
from rag.retriever import get_retriever
from rag.multi_source_retriever import get_multi_source_retriever


def test_clinvar():
    """Test ClinVar fetcher."""
    print("=" * 60)
    print("Testing ClinVar Fetcher")
    print("=" * 60)

    fetcher = get_clinvar_fetcher()

    # Test 1: Search for SCN1A variants
    print("\n[Test 1] Searching for SCN1A pathogenic variants...")
    variants = fetcher.search_variant(gene="SCN1A")

    if variants:
        print(f"✓ Found {len(variants)} variants")
        top_variant = variants[0]
        print(f"\nTop variant:")
        print(f"  Name: {top_variant['variant_name']}")
        print(f"  Significance: {top_variant['clinical_significance']}")
        print(f"  Review: {top_variant['review_stars']} stars")
        print(f"  URL: {top_variant['url']}")
    else:
        print("✗ No variants found (may need NCBI_API_KEY in .env)")

    # Test 2: Get gene summary
    print("\n[Test 2] Getting SCN1A summary...")
    summary = fetcher.get_gene_summary("SCN1A", limit=5)
    print(f"✓ Total variants: {summary.get('total_variants', 0)}")

    return len(variants) > 0 if variants else False


def test_pharmgkb():
    """Test PharmGKB fetcher."""
    print("\n" + "=" * 60)
    print("Testing PharmGKB Fetcher")
    print("=" * 60)

    fetcher = get_pharmgkb_fetcher()

    # Test 1: Get drug-gene interactions
    print("\n[Test 1] Getting drug-gene interactions for SCN1A...")
    interactions = fetcher.get_drug_gene_interactions("SCN1A")
    print(f"✓ Found {len(interactions)} interactions")

    # Test 2: Get recommendations
    print("\n[Test 2] Getting drug recommendations for SCN1A...")
    recommendations = fetcher.get_drug_recommendations("SCN1A")

    print(f"\n✓ Recommended drugs: {len(recommendations.get('recommended', []))}")
    for drug in recommendations.get('recommended', [])[:3]:
        print(f"  • {drug['drug']}: {drug['description'][:60]}...")

    print(f"\n⚠️  Contraindicated drugs: {len(recommendations.get('contraindicated', []))}")
    for drug in recommendations.get('contraindicated', [])[:3]:
        print(f"  • {drug['drug']}: {drug['description'][:60]}...")

    return len(interactions) > 0


def test_multi_source_retriever():
    """Test multi-source retriever."""
    print("\n" + "=" * 60)
    print("Testing Multi-Source Retriever")
    print("=" * 60)

    # Load PubMed retriever
    print("\n[Setup] Loading PubMed retriever...")
    pubmed_retriever = get_retriever()

    if not pubmed_retriever.is_loaded:
        print("✗ PubMed retriever not loaded. Run scripts/build_knowledge_base.py first.")
        return False

    print("✓ PubMed retriever loaded")

    # Initialize multi-source retriever
    print("\n[Setup] Initializing multi-source retriever...")
    multi_retriever = get_multi_source_retriever(pubmed_retriever)
    print("✓ Multi-source retriever initialized")

    # Test comprehensive retrieval
    print("\n[Test] Retrieving comprehensive information for SCN1A...")
    results = multi_retriever.retrieve_comprehensive(
        gene="SCN1A",
        consequence="missense",
        include_clinvar=True,
        include_pharmgkb=True,
        include_pubmed=True,
        top_k=3
    )

    # Check sources
    sources_used = results['metadata']['sources_queried']
    print(f"\n✓ Sources queried: {', '.join(sources_used)}")

    # Display results by source
    if 'clinvar' in results.get('sources', {}):
        cv_count = results['sources']['clinvar']['count']
        print(f"  • ClinVar: {cv_count} variants")

    if 'pharmgkb' in results.get('sources', {}):
        pgkb = results['sources']['pharmgkb']
        total_drugs = (
            len(pgkb.get('efficacy', [])) +
            len(pgkb.get('toxicity', [])) +
            len(pgkb.get('dosage', [])) +
            len(pgkb.get('other', []))
        )
        print(f"  • PharmGKB: {total_drugs} drug interactions")

    if 'pubmed' in results.get('sources', {}):
        pubmed_count = results['sources']['pubmed']['count']
        print(f"  • PubMed: {pubmed_count} literature chunks")

    # Format context
    print("\n[Test] Formatting context for LLM...")
    context = multi_retriever.format_context_for_llm(results, max_length=4000)
    print(f"✓ Context length: {len(context)} characters")

    # Summary
    print(f"\n✓ Sources summary: {multi_retriever.get_sources_summary(results)}")

    return len(sources_used) > 0


def main():
    """Run all tests."""
    print("\n")
    print("╔" + "=" * 58 + "╗")
    print("║" + " " * 10 + "MULTI-SOURCE INTEGRATION TEST" + " " * 19 + "║")
    print("╚" + "=" * 58 + "╝")

    results = {
        'ClinVar': False,
        'PharmGKB': False,
        'Multi-Source Retriever': False
    }

    try:
        results['ClinVar'] = test_clinvar()
    except Exception as e:
        print(f"\n✗ ClinVar test failed: {e}")

    try:
        results['PharmGKB'] = test_pharmgkb()
    except Exception as e:
        print(f"\n✗ PharmGKB test failed: {e}")

    try:
        results['Multi-Source Retriever'] = test_multi_source_retriever()
    except Exception as e:
        print(f"\n✗ Multi-Source Retriever test failed: {e}")

    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)

    all_passed = True
    for component, passed in results.items():
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{component:30s} {status}")
        if not passed:
            all_passed = False

    print("=" * 60)

    if all_passed:
        print("\n🎉 All tests passed! Multi-source integration is working.")
        return 0
    else:
        print("\n⚠️  Some tests failed. Check configuration and dependencies.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
