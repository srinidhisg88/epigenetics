# Multi-Source Knowledge Base Integration

## Overview

The Epilepsy Diagnostic Assistant now integrates **multiple authoritative medical sources** beyond PubMed to provide comprehensive, evidence-based variant interpretations and treatment recommendations.

## 🔬 Integrated Sources

### 1. **ClinVar** - NCBI Variant Database
- **Purpose**: Variant-specific clinical interpretations
- **Coverage**: 2M+ variants with clinical significance assertions
- **Authority**: NIH's public archive of variant-disease relationships
- **Update Frequency**: Monthly releases
- **Cache**: SQLite database (30-day TTL)

**What it provides:**
- Clinical significance (Pathogenic/Benign/VUS)
- Review status (0-4 star rating)
- Multiple submitter interpretations
- Condition associations
- Expert panel consensus

**File**: `backend/clinvar_fetcher.py`

**Usage Example:**
```python
from backend.clinvar_fetcher import get_clinvar_fetcher

fetcher = get_clinvar_fetcher()
variants = fetcher.search_variant(gene="SCN1A", variant="p.Arg1648His")

for v in variants:
    print(f"{v['clinical_significance']} ({v['review_stars']} stars)")
    print(f"Conditions: {v['conditions']}")
    print(f"URL: {v['url']}")
```

---

### 2. **PharmGKB** - Pharmacogenomics Database
- **Purpose**: Drug-gene interaction warnings and recommendations
- **Coverage**: Curated epilepsy drug-gene pairs
- **Authority**: NIH-funded pharmacogenomics knowledge resource
- **Update Frequency**: Real-time (curated data) + weekly TSV updates
- **Storage**: In-memory + SQLite cache

**What it provides:**
- Recommended medications by gene
- Contraindicated drugs (AVOID warnings)
- Context-dependent treatments
- Evidence levels
- Clinical annotations

**File**: `backend/pharmgkb_fetcher.py`

**Curated Interactions:**
- SCN1A: Sodium channel blocker warnings, first-line AEDs
- SCN2A: Context-dependent recommendations (GOF vs. LOF)
- KCNQ2/3: Neonatal seizure treatments
- SLC2A1: Ketogenic diet (primary treatment)
- TSC1/TSC2: mTOR inhibitors
- ALDH7A1: Pyridoxine supplementation
- And more...

**Usage Example:**
```python
from backend.pharmgkb_fetcher import get_pharmgkb_fetcher

fetcher = get_pharmgkb_fetcher()
recommendations = fetcher.get_drug_recommendations(gene="SCN1A")

print("Recommended:", recommendations['recommended'])
print("Contraindicated:", recommendations['contraindicated'])
```

---

### 3. **ILAE Guidelines** - International League Against Epilepsy
- **Purpose**: Evidence-based clinical practice guidelines
- **Coverage**: 26 epilepsy genes, major syndromes
- **Authority**: Global authority on epilepsy classification and treatment
- **Update Frequency**: Manual curation from official ILAE publications
- **Storage**: Text file in knowledge base, indexed in FAISS

**What it provides:**
- Syndrome-specific treatment protocols
- Evidence-level classifications (Level A/B/C)
- Dosing guidelines
- Monitoring recommendations
- Status epilepticus protocols
- Pregnancy considerations

**File**: `data/knowledge_base/ilae_guidelines.txt` (18KB)

**Coverage:**
- Dravet Syndrome (SCN1A)
- SCN2A-related epilepsies
- Benign Familial Neonatal Seizures (KCNQ2/3)
- GLUT1 Deficiency (SLC2A1)
- Tuberous Sclerosis Complex (TSC1/TSC2)
- CDKL5 Deficiency Disorder
- General principles for genetic epilepsies
- Drug-resistant epilepsy management
- Pregnancy and transition care

---

### 4. **PubMed/NCBI Literature** (Existing)
- **Purpose**: Peer-reviewed scientific literature
- **Coverage**: 287 papers + dynamic updates
- **Authority**: NIH's biomedical literature database
- **Update Frequency**: 24-hour cache + manual refresh
- **Storage**: Text files + FAISS vector index

---

## 🏗️ Architecture

### Multi-Source Retriever

**File**: `rag/multi_source_retriever.py`

Coordinates retrieval from all sources and merges results using evidence hierarchy:

```
Priority 1: ClinVar (40% of context)
   ↓
Priority 2: PharmGKB (30% of context)
   ↓
Priority 3: ILAE Guidelines (via PubMed retriever)
   ↓
Priority 4: PubMed Literature (30% of context)
```

**Usage:**
```python
from rag.multi_source_retriever import get_multi_source_retriever

retriever = get_multi_source_retriever(pubmed_retriever=existing_retriever)

results = retriever.retrieve_comprehensive(
    gene="SCN1A",
    variant="p.Arg1648His",
    consequence="missense",
    include_clinvar=True,
    include_pharmgkb=True,
    include_pubmed=True,
    top_k=5
)

# Format for LLM
context = retriever.format_context_for_llm(results, max_length=4000)
```

---

## 🚀 API Integration

### Updated Endpoint: `/analyze_variant`

Now uses multi-source retrieval for pathogenic variants:

**Request:**
```json
{
  "gene": "SCN1A",
  "chromosome": "2",
  "reference_allele": "G",
  "alternate_allele": "A",
  "consequence": "missense_variant",
  "variant_type": "single nucleotide variant"
}
```

**Enhanced Response:**
```json
{
  "prediction": "Pathogenic",
  "confidence": 85.0,
  "rag_response": "## Variant Interpretation\n...",
  "sources": [
    {
      "source": "ClinVar",
      "title": "p.Arg1648His - Pathogenic",
      "url": "https://www.ncbi.nlm.nih.gov/clinvar/variation/12345/",
      "type": "clinvar",
      "score": 1.0
    },
    {
      "source": "PharmGKB",
      "title": "Drug-Gene Interactions for SCN1A",
      "url": "https://www.pharmgkb.org/",
      "type": "pharmgkb",
      "score": 0.95
    },
    {
      "source": "pmid_12345678.txt",
      "title": "Sodium Channel Blockers in Dravet Syndrome",
      "url": "https://pubmed.ncbi.nlm.nih.gov/12345678/",
      "type": "pubmed",
      "score": 0.85
    }
  ]
}
```

---

## 📊 Data Flow

```
User Query (Pathogenic Variant)
    ↓
┌─────────────────────────────────────────┐
│ Multi-Source Retriever                  │
└─────────────────────────────────────────┘
    ↓
┌─────────────┬────────────────┬─────────────────┐
│  ClinVar    │   PharmGKB     │  PubMed + ILAE  │
│  Fetcher    │   Fetcher      │   Retriever     │
└─────────────┴────────────────┴─────────────────┘
    ↓              ↓                   ↓
Variant-specific  Drug-gene       Literature +
evidence          interactions     Guidelines
    ↓              ↓                   ↓
┌─────────────────────────────────────────┐
│ Format & Merge by Evidence Hierarchy    │
└─────────────────────────────────────────┘
    ↓
Combined Context (max 4000 chars)
    ↓
┌─────────────────────────────────────────┐
│ LLM Generator (Llama 3.3 70B)           │
└─────────────────────────────────────────┘
    ↓
Structured Clinical Explanation
```

---

## 🗄️ Caching Strategy

### ClinVar Cache
- **Type**: SQLite database
- **Location**: `cache/clinvar/clinvar_cache.db`
- **TTL**: 30 days
- **Key**: MD5 hash of gene + variant
- **Reason**: ClinVar updates monthly, 30-day cache balances freshness vs. API calls

### PharmGKB Cache
- **Type**: SQLite database
- **Location**: `cache/pharmgkb/pharmgkb_cache.db`
- **TTL**: N/A (curated data is loaded at startup)
- **Reason**: Hand-curated interactions are stable, updates are manual

### PubMed Cache
- **Type**: File-based (JSON)
- **Location**: `cache/literature/`
- **TTL**: 24 hours
- **Reason**: Recent literature changes frequently, daily refresh appropriate

---

## 📈 Knowledge Base Statistics

### Current Coverage

```
Total Documents: 289
├── PubMed Abstracts: 287 papers
├── Treatment Guidelines: 1 file (26 genes)
└── ILAE Guidelines: 1 file (comprehensive)

Total FAISS Chunks: 341
├── Average chunk size: 400 words
├── Embedding model: S-PubMedBert-MS-MARCO (768-dim)
└── Index type: IndexFlatIP (cosine similarity)

External APIs:
├── ClinVar: ~2M variants (on-demand)
├── PharmGKB: 20+ curated drug-gene pairs
└── NCBI E-utilities: Rate-limited (3/sec free, 10/sec with key)
```

---

## 🔧 Configuration

### Environment Variables

Add to `.env` file:

```bash
# NCBI API Key (optional, increases rate limit from 3/sec to 10/sec)
NCBI_API_KEY=your_ncbi_api_key_here

# Entrez email (required for PubMed)
ENTREZ_EMAIL=your_email@example.com

# Groq API Key (required for LLM)
GROQ_API_KEY=your_groq_api_key_here
```

### Get NCBI API Key
1. Create NCBI account: https://www.ncbi.nlm.nih.gov/account/
2. Go to Settings → API Key Management
3. Generate new API key
4. Add to `.env` file

---

## 📝 Evidence Quality Hierarchy

The system prioritizes sources by evidence quality:

```
1. ClinVar (Variant-Specific)
   ├── 4-star: Practice guideline
   ├── 3-star: Expert panel reviewed
   ├── 2-star: Multiple submitters, no conflicts
   ├── 1-star: Criteria provided, single submitter
   └── 0-star: No assertion criteria

2. ILAE Guidelines (Syndrome-Specific)
   ├── Level A: Established (≥2 Class I studies)
   ├── Level B: Probably effective (≥1 Class I)
   ├── Level C: Possibly effective (≥2 Class II)
   └── Level U: Inadequate data

3. PharmGKB (Gene-Level)
   ├── High evidence: Clinical guidelines, FDA labels
   ├── Moderate evidence: Clinical trials
   └── Low evidence: Case reports

4. PubMed Literature (General)
   ├── Systematic reviews & meta-analyses
   ├── Randomized controlled trials
   ├── Cohort studies
   └── Case reports
```

---

## 🧪 Testing the Integration

### Test ClinVar Fetcher
```bash
cd /path/to/epilepsy_diagnostic_assistant
python -c "
from backend.clinvar_fetcher import get_clinvar_fetcher
fetcher = get_clinvar_fetcher()
variants = fetcher.search_variant('SCN1A')
print(f'Found {len(variants)} variants')
for v in variants[:3]:
    print(f'{v[\"variant_name\"]}: {v[\"clinical_significance\"]}')
"
```

### Test PharmGKB Fetcher
```bash
python -c "
from backend.pharmgkb_fetcher import get_pharmgkb_fetcher
fetcher = get_pharmgkb_fetcher()
recommendations = fetcher.get_drug_recommendations('SCN1A')
print('Recommended:', [d['drug'] for d in recommendations['recommended']])
print('Contraindicated:', [d['drug'] for d in recommendations['contraindicated']])
"
```

### Test Multi-Source Retriever
```bash
python -c "
from rag.retriever import get_retriever
from rag.multi_source_retriever import get_multi_source_retriever

pubmed_retriever = get_retriever()
multi_retriever = get_multi_source_retriever(pubmed_retriever)

results = multi_retriever.retrieve_comprehensive(
    gene='SCN1A',
    consequence='missense',
    top_k=3
)

print(f'Sources used: {multi_retriever.get_sources_summary(results)}')
print(f'Context length: {len(results[\"combined_context\"])} chars')
"
```

---

## 🔄 Maintenance & Updates

### Monthly Tasks
1. **ClinVar**: Automatic cache expiration after 30 days
2. **PharmGKB**: Review curated interactions for updates
3. **ILAE**: Check for new position papers/guidelines

### Quarterly Tasks
1. Rebuild FAISS index: `python scripts/build_knowledge_base.py`
2. Review and update treatment guidelines
3. Audit cache database sizes

### Annual Tasks
1. Major ILAE guideline revisions
2. Systematic review of drug-gene interaction evidence
3. Update PharmGKB TSV data (if using downloadable files)

---

## 📚 References

1. **ClinVar**: https://www.ncbi.nlm.nih.gov/clinvar/
2. **PharmGKB**: https://www.pharmgkb.org/
3. **ILAE**: https://www.ilae.org/
4. **PubMed**: https://pubmed.ncbi.nlm.nih.gov/
5. **NCBI E-utilities**: https://www.ncbi.nlm.nih.gov/books/NBK25501/

---

## ⚠️ Important Notes

1. **Rate Limits**: NCBI E-utilities has rate limits (3/sec without key, 10/sec with key). The fetchers implement automatic rate limiting.

2. **Cache Management**: Monitor cache database sizes. ClinVar cache can grow large with heavy use.

3. **API Keys**: Store API keys in `.env` file, never commit to git.

4. **Clinical Use**: This system provides decision support but does NOT replace:
   - Professional medical judgment
   - Genetic counseling
   - Laboratory confirmation
   - Expert consultation

5. **Updates**: Knowledge bases require periodic maintenance to stay current with medical evidence.

---

## 🚀 Future Enhancements

Potential additions:
- ✅ ClinVar (Implemented)
- ✅ PharmGKB (Implemented)
- ✅ ILAE Guidelines (Implemented)
- ⏳ GeneReviews (Expert-authored disease reviews)
- ⏳ gnomAD (Population frequencies)
- ⏳ OMIM (Gene-disease associations)
- ⏳ UpToDate API (Commercial CDS system)
- ⏳ Real-time ACMG variant classification
- ⏳ EpilepsyGene Database integration

---

**Document Version**: 1.0
**Last Updated**: 2026-02-28
**Author**: Epilepsy Diagnostic Assistant Development Team
