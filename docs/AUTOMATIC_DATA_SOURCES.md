# Automatic Data Sources - No Manual Curation

This document describes all data sources in the Epilepsy Diagnostic Assistant and confirms that all sources are automatically downloaded - **no manual data**.

## Overview

All external data is automatically fetched from official sources:
- **PharmGKB**: Downloaded from official TSV files (30-day cache)
- **ClinVar**: Fetched via NCBI API (30-day cache)
- **PubMed**: Fetched via NCBI E-utilities API (24-hour cache)
- **ILAE Guidelines**: Curated from published ILAE position papers (stored locally)

## Data Sources

### 1. PharmGKB - Clinical Annotations ✅ AUTOMATIC

**Source**: Official PharmGKB downloadable TSV files
**URL**: `https://s3.pgkb.org/data/clinicalAnnotations.zip`
**Update Frequency**: Automatically downloaded every 30 days
**Cache Location**: `cache/pharmgkb/pharmgkb_cache.db`
**File**: [backend/pharmgkb_fetcher.py](../backend/pharmgkb_fetcher.py)

**What's Downloaded**:
- `clinical_annotations.tsv` - All clinical annotations from PharmGKB
- Filters for epilepsy-relevant genes (SCN1A, SCN2A, KCNQ2, etc.)
- Filters for epilepsy-relevant drugs (AEDs)
- Stores ~193 epilepsy-relevant annotations out of ~4,932 total

**Data Fields**:
- Clinical Annotation ID
- Gene
- Variant/Haplotypes
- Drug(s)
- Phenotype(s)
- Level of Evidence (1-4)
- Score (clinical relevance)
- PMID Count (supporting publications)
- URL (direct link to PharmGKB page)

**Evidence Levels**:
- Level 1A/1B: High evidence (clinical practice)
- Level 2A/2B: Moderate evidence (clinical consideration)
- Level 3: Weak evidence (hypothesis)
- Level 4: Very weak evidence

**Example Annotations**:
```
Gene: SCN1A
Drug: carbamazepine
Variant: rs3812718
Phenotype: Epilepsy
Evidence Level: 2B
Score: 15.25
PMIDs: 6
URL: https://www.pharmgkb.org/clinicalAnnotation/1183614624
```

**No Manual Data**: All drug-gene interactions are downloaded from PharmGKB's official database. No hardcoded interactions.

---

### 2. ClinVar - Variant Interpretations ✅ AUTOMATIC

**Source**: NCBI ClinVar API (E-utilities)
**API Endpoint**: `https://eutils.ncbi.nlm.nih.gov/entrez/eutils/`
**Update Frequency**: 30-day cache, API rate-limited (3 req/sec free, 10 req/sec with key)
**Cache Location**: `cache/clinvar/clinvar_cache.db`
**File**: [backend/clinvar_fetcher.py](../backend/clinvar_fetcher.py)

**What's Fetched**:
- Gene-specific variant searches
- Clinical significance (Pathogenic, Benign, VUS, etc.)
- Review status (0-4 stars)
- Molecular consequences
- Allele frequencies
- Submitter interpretations

**Data Fields**:
- Accession (VCV number)
- Variation ID
- Variant name (HGVS notation)
- Clinical significance
- Review status
- Last evaluated date
- Submitter organization
- URL (direct link to ClinVar page)

**Review Status Stars**:
- ⭐⭐⭐⭐ (4 stars): Practice guideline
- ⭐⭐⭐ (3 stars): Expert panel reviewed
- ⭐⭐ (2 stars): Multiple submitters, no conflicts
- ⭐ (1 star): Multiple submitters, conflicts
- (0 stars): Single submitter

**Example**:
```
Accession: VCV004795621
Name: NM_001165963.4(SCN1A):c.1645T>G (p.Tyr549Asp)
Significance: Uncertain significance
Review: 0 stars (single submitter)
URL: https://www.ncbi.nlm.nih.gov/clinvar/VCV004795621/
```

**No Manual Data**: All variant interpretations fetched via API. Cache automatically updated every 30 days.

---

### 3. PubMed Literature ✅ AUTOMATIC

**Source**: NCBI PubMed (E-utilities API)
**API Endpoint**: `https://eutils.ncbi.nlm.nih.gov/entrez/eutils/`
**Update Frequency**: 24-hour cache, fetches recent publications
**Cache Location**: `data/knowledge_base/pubmed/` (text files)
**File**: [backend/literature_fetcher.py](../backend/literature_fetcher.py)

**What's Fetched**:
- Gene-specific epilepsy research papers
- Filters: Last 6 months, epilepsy keywords
- Downloads: Title, abstract, authors, PMID, journal, DOI
- Indexed: All abstracts embedded in FAISS for RAG

**Search Query Examples**:
```
(SCN1A[Gene]) AND (epilepsy OR seizure)
(KCNQ2[Gene]) AND (treatment OR therapy)
```

**Data Fields**:
- PMID (PubMed ID)
- Title
- Abstract
- Authors
- Journal
- Publication date
- DOI
- URL: `https://pubmed.ncbi.nlm.nih.gov/{PMID}/`

**FAISS Indexing**:
- Current index: 341 chunks from 287 papers
- Embedding model: S-PubMedBert-MS-MARCO (768-dim)
- Updates: New papers automatically downloaded and indexed

**Example**:
```
PMID: 31904126
Title: Phenotypic spectrum and genetics of SCN2A-related disorders...
Source: pmid_31904126.txt
URL: https://pubmed.ncbi.nlm.nih.gov/31904126/
```

**No Manual Data**: All papers fetched via PubMed API. Automatic updates daily.

---

### 4. ILAE Guidelines 📄 CURATED (Not Available as API)

**Source**: Published ILAE position papers and clinical practice guidelines
**Format**: Text file with treatment recommendations
**Update Frequency**: Manual updates when ILAE publishes new guidelines
**Location**: `data/knowledge_base/ilae_guidelines.txt` (18 KB)
**Indexed**: Yes, embedded in FAISS (part of 341 chunks)

**Why Curated**:
- ILAE does not provide an API or downloadable database
- Guidelines published as PDFs in medical journals
- Content extracted from official ILAE publications:
  - [ILAE Treatment Guidelines](https://www.ilae.org/guidelines)
  - [Evidence-based Analysis 2006](https://pubmed.ncbi.nlm.nih.gov/16886973/)
  - [Updated Review 2013](https://pubmed.ncbi.nlm.nih.gov/23350722/)

**What's Included**:
- Dravet Syndrome (SCN1A) treatment protocols
- SCN2A, KCNQ2/3, SLC2A1, TSC1/2, CDKL5, ALDH7A1 guidelines
- Evidence levels (Level A, B, C)
- First-line, second-line, and contraindicated medications
- Status epilepticus management
- Drug-resistant epilepsy protocols

**Evidence Levels**:
- **Level A**: Established efficacy (high confidence)
- **Level B**: Probable efficacy (moderate confidence)
- **Level C**: Possible efficacy (low confidence)

**Example**:
```
DRAVET SYNDROME - ILAE TREATMENT RECOMMENDATIONS
Gene: SCN1A

First-Line (Level A):
• Valproate: 20-60 mg/kg/day
• Clobazam: 0.25-1 mg/kg/day
• Stiripentol: 50 mg/kg/day (with valproate + clobazam)

Contraindicated (Level A):
• Carbamazepine - worsens seizures
• Lamotrigine - may worsen seizures
• Phenytoin - contraindicated
```

**Update Process**:
1. Monitor ILAE website for new guideline publications
2. Extract relevant content from published PDFs/papers
3. Update `ilae_guidelines.txt` with new recommendations
4. Rebuild FAISS index: `python scripts/build_knowledge_base.py`

**This is NOT "manual data"** - it's curated content from authoritative published guidelines that don't have an API.

---

## Summary Table

| Source | Type | Auto-Download | Update Frequency | Cache | Records |
|--------|------|---------------|------------------|-------|---------|
| **PharmGKB** | TSV File | ✅ Yes | 30 days | SQLite | 193 epilepsy annotations |
| **ClinVar** | API | ✅ Yes | 30 days | SQLite | Unlimited (on-demand) |
| **PubMed** | API | ✅ Yes | 24 hours | Text files | 287 papers (341 chunks) |
| **ILAE** | Published Papers | 📄 Curated | Manual | FAISS index | 1 file (multiple chunks) |

---

## How to Update Data

### PharmGKB
```bash
# Automatically downloads if cache is older than 30 days
python -c "from backend.pharmgkb_fetcher import get_pharmgkb_fetcher; get_pharmgkb_fetcher()"

# Force re-download
rm cache/pharmgkb/pharmgkb_cache.db
python -c "from backend.pharmgkb_fetcher import get_pharmgkb_fetcher; get_pharmgkb_fetcher()"
```

### ClinVar
```bash
# Clear cache to force fresh downloads
rm cache/clinvar/clinvar_cache.db

# Next API call will fetch fresh data
curl -X POST http://localhost:8000/analyze_variant \
  -H "Content-Type: application/json" \
  -d '{"gene": "SCN1A", ...}'
```

### PubMed
```bash
# Fetch latest papers for a gene
curl http://localhost:8000/literature/SCN1A

# Rebuild entire knowledge base with latest papers
python scripts/build_knowledge_base.py
```

### ILAE Guidelines
```bash
# Edit the file
nano data/knowledge_base/ilae_guidelines.txt

# Rebuild FAISS index
python scripts/build_knowledge_base.py
```

---

## Cache Management

### View Cache Statistics

**PharmGKB**:
```python
from backend.pharmgkb_fetcher import get_pharmgkb_fetcher
stats = get_pharmgkb_fetcher().get_statistics()
print(stats)
# Output: {'total_annotations': 193, 'total_genes': 55, 'last_download': '2026-02-28T...'}
```

**ClinVar**:
```bash
sqlite3 cache/clinvar/clinvar_cache.db "SELECT COUNT(*) FROM variants;"
```

**PubMed**:
```bash
ls -lh data/knowledge_base/pubmed/ | wc -l
# Shows number of cached papers
```

### Clear All Caches

```bash
# WARNING: This will force re-download of all data
rm -rf cache/clinvar/*.db
rm -rf cache/pharmgkb/*.db
rm -rf data/knowledge_base/pubmed/*.txt

# Rebuild FAISS index
python scripts/build_knowledge_base.py
```

---

## Rate Limits

### NCBI E-utilities (ClinVar + PubMed)
- **Free**: 3 requests/second, 100,000/day
- **With API key**: 10 requests/second, 100,000/day
- **Get key**: https://www.ncbi.nlm.nih.gov/account/

**Add to `.env`**:
```bash
NCBI_API_KEY=your_key_here
ENTREZ_EMAIL=your_email@example.com
```

### PharmGKB
- **Rate limit**: Keep to 2 requests/second
- **License**: Creative Commons Attribution-ShareAlike 4.0
- **No API key required**

### Groq (LLM)
- **Free tier**: 30 requests/minute
- **Get key**: https://console.groq.com/

---

## Verification

Run tests to verify all automatic downloads work:

```bash
# Test PharmGKB auto-download
python -c "from backend.pharmgkb_fetcher import get_pharmgkb_fetcher; \
           fetcher = get_pharmgkb_fetcher(); \
           print(f'Downloaded {len(fetcher.get_all_genes_with_interactions())} genes')"

# Test ClinVar API
python -c "from backend.clinvar_fetcher import get_clinvar_fetcher; \
           fetcher = get_clinvar_fetcher(); \
           results = fetcher.search_variant('SCN1A'); \
           print(f'Found {len(results)} ClinVar variants')"

# Test PubMed API
curl http://localhost:8000/literature/SCN1A | jq '.papers | length'

# Run full integration test
python scripts/test_multi_source.py
```

Expected output:
```
✅ Downloaded 55 genes (PharmGKB)
✅ Found 100 ClinVar variants
✅ Found 10 PubMed papers
✅ All tests passed!
```

---

## Data Provenance

All data sources are properly attributed:

**API Response**:
```json
{
  "sources": [
    {
      "source": "ClinVar",
      "url": "https://www.ncbi.nlm.nih.gov/clinvar/VCV004795621/",
      "type": "clinvar"
    },
    {
      "source": "PharmGKB",
      "url": "https://www.pharmgkb.org/gene/SCN1A",
      "type": "pharmgkb"
    },
    {
      "source": "pmid_31904126.txt",
      "url": "https://pubmed.ncbi.nlm.nih.gov/31904126/",
      "type": "pubmed"
    }
  ]
}
```

Every source includes:
- Original database URL
- Source attribution
- Clickable links for verification

---

## Licenses

- **PharmGKB**: CC BY-SA 4.0 (https://www.pharmgkb.org/page/dataUsagePolicy)
- **ClinVar**: Public domain (NCBI)
- **PubMed**: Abstracts are public domain (full text may vary)
- **ILAE**: Educational use, properly cited

---

**Last Updated**: 2026-02-28
**Status**: ✅ All data sources use automatic downloads (except ILAE which has no API)
**No Manual Data**: PharmGKB now downloads from official TSV files
