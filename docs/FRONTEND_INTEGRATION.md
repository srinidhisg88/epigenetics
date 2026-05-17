# Frontend Integration Guide - Multi-Source Links

## Overview

The backend now provides **clickable URLs** for all sources (ClinVar, PharmGKB, PubMed) in the API response. This document shows exactly what the frontend receives and how to display the links.

---

## API Response Structure

### Endpoint: `POST /analyze_variant`

**Example Request:**
```json
{
  "gene": "SCN1A",
  "chromosome": "2",
  "reference_allele": "G",
  "alternate_allele": "A",
  "consequence": "missense_variant",
  "variant_type": "single nucleotide variant",
  "review_status": "criteria provided, single submitter",
  "origin": "germline"
}
```

**Example Response:**
```json
{
  "prediction": "Pathogenic",
  "confidence": 85.2,
  "pathogenic_probability": 0.852,
  "benign_probability": 0.148,
  "variant_info": {
    "gene": "SCN1A",
    "chromosome": "2",
    "reference_allele": "G",
    "alternate_allele": "A",
    "consequence": "missense_variant",
    "variant_type": "single nucleotide variant"
  },
  "is_pathogenic": true,
  "rag_response": "## 🧬 Variant Interpretation\n\nThis SCN1A missense variant is predicted as Pathogenic with 85.2% confidence...",
  "sources": [
    {
      "source": "ClinVar",
      "title": "NM_001165963.4(SCN1A):c.1645T>G (p.Tyr549Asp) - Pathogenic",
      "url": "https://www.ncbi.nlm.nih.gov/clinvar/variation/12345/",
      "score": 1.0,
      "type": "clinvar"
    },
    {
      "source": "PharmGKB",
      "title": "Drug-Gene Interactions for SCN1A",
      "url": "https://www.pharmgkb.org/gene/SCN1A",
      "score": 0.95,
      "type": "pharmgkb"
    },
    {
      "source": "pmid_29778428.txt",
      "title": "Sodium channel blockers in Dravet syndrome",
      "pmid": "29778428",
      "url": "https://pubmed.ncbi.nlm.nih.gov/29778428/",
      "score": 0.87,
      "type": "pubmed"
    },
    {
      "source": "ilae_guidelines.txt",
      "title": "ILAE Treatment Guidelines",
      "url": null,
      "score": 0.84,
      "type": "pubmed"
    }
  ]
}
```

---

## Source Types & URL Patterns

### 1. **ClinVar Sources**

**Identifier**: `"type": "clinvar"`

**URL Patterns:**

```javascript
// Best case: Specific variation ID
"url": "https://www.ncbi.nlm.nih.gov/clinvar/variation/12345/"

// Fallback 1: Accession number
"url": "https://www.ncbi.nlm.nih.gov/clinvar/VCV000012345/"

// Fallback 2: Gene search (if no ID available)
"url": "https://www.ncbi.nlm.nih.gov/clinvar/?term=SCN1A[gene]"
```

**Title Format:**
```
"{variant_name} - {clinical_significance}"

Examples:
- "NM_001165963.4(SCN1A):c.1645T>G (p.Tyr549Asp) - Pathogenic"
- "NM_006920.5(SCN2A):c.2161G>A (p.Glu721Lys) - Likely pathogenic"
```

**Display Recommendation:**
```html
<div class="source-card clinvar">
  <div class="source-header">
    <img src="/icons/clinvar-logo.png" alt="ClinVar" />
    <span class="source-type">ClinVar</span>
    <span class="confidence-badge">★★★★</span>
  </div>
  <h4>{title}</h4>
  <a href="{url}" target="_blank" rel="noopener noreferrer">
    View in ClinVar →
  </a>
</div>
```

---

### 2. **PharmGKB Sources**

**Identifier**: `"type": "pharmgkb"`

**URL Pattern:**
```javascript
// Gene-specific page
"url": "https://www.pharmgkb.org/gene/{GENE}"

Examples:
- "https://www.pharmgkb.org/gene/SCN1A"
- "https://www.pharmgkb.org/gene/KCNQ2"
- "https://www.pharmgkb.org/gene/TSC1"
```

**Title Format:**
```
"Drug-Gene Interactions for {GENE}"

Examples:
- "Drug-Gene Interactions for SCN1A"
- "Drug-Gene Interactions for SCN2A"
```

**Display Recommendation:**
```html
<div class="source-card pharmgkb">
  <div class="source-header">
    <img src="/icons/pharmgkb-logo.png" alt="PharmGKB" />
    <span class="source-type">PharmGKB</span>
    <span class="badge warning">Drug Interactions</span>
  </div>
  <h4>{title}</h4>
  <a href="{url}" target="_blank" rel="noopener noreferrer">
    View Drug Interactions →
  </a>
</div>
```

---

### 3. **PubMed Sources**

**Identifier**: `"type": "pubmed"` (default)

**URL Pattern:**
```javascript
// PubMed article (if pmid exists)
"url": "https://pubmed.ncbi.nlm.nih.gov/{PMID}/"

// Local file (if pmid is null)
"url": null

Examples:
- "https://pubmed.ncbi.nlm.nih.gov/29778428/"
- "https://pubmed.ncbi.nlm.nih.gov/32102148/"
- null (for ILAE guidelines, treatment_guidelines.txt)
```

**Title Format:**
```
"{article_title}"

Examples:
- "Sodium channel blockers in Dravet syndrome"
- "Treatment guidelines for genetic epilepsies"
- "ILAE Treatment Guidelines" (for local files)
```

**Display Recommendation:**
```html
<div class="source-card pubmed">
  <div class="source-header">
    <img src="/icons/pubmed-logo.png" alt="PubMed" />
    <span class="source-type">PubMed</span>
    {#if pmid}
      <span class="badge">PMID: {pmid}</span>
    {/if}
  </div>
  <h4>{title}</h4>
  {#if url}
    <a href="{url}" target="_blank" rel="noopener noreferrer">
      View Article →
    </a>
  {:else}
    <span class="badge gray">Internal Guideline</span>
  {/if}
</div>
```

---

## React Component Example

```jsx
import React from 'react';

const SourceCard = ({ source }) => {
  const getSourceIcon = (type) => {
    switch(type) {
      case 'clinvar':
        return '🧬'; // or <img src="/icons/clinvar.png" />
      case 'pharmgkb':
        return '💊'; // or <img src="/icons/pharmgkb.png" />
      case 'pubmed':
        return '📚'; // or <img src="/icons/pubmed.png" />
      default:
        return '📄';
    }
  };

  const getSourceClass = (type) => {
    return `source-card source-${type || 'default'}`;
  };

  const getConfidenceBadge = (score) => {
    if (score >= 0.9) return '⭐⭐⭐⭐';
    if (score >= 0.8) return '⭐⭐⭐';
    if (score >= 0.7) return '⭐⭐';
    return '⭐';
  };

  return (
    <div className={getSourceClass(source.type)}>
      <div className="source-header">
        <span className="source-icon">{getSourceIcon(source.type)}</span>
        <span className="source-name">{source.source}</span>
        <span className="confidence-badge">{getConfidenceBadge(source.score)}</span>
      </div>

      <h4 className="source-title">{source.title}</h4>

      {/* Display PMID for PubMed articles */}
      {source.pmid && (
        <div className="source-meta">
          <span className="badge">PMID: {source.pmid}</span>
        </div>
      )}

      {/* Display link if URL exists */}
      {source.url ? (
        <a
          href={source.url}
          target="_blank"
          rel="noopener noreferrer"
          className="source-link"
        >
          {source.type === 'clinvar' && 'View in ClinVar →'}
          {source.type === 'pharmgkb' && 'View Drug Interactions →'}
          {source.type === 'pubmed' && 'Read Article →'}
        </a>
      ) : (
        <span className="badge badge-gray">Internal Guideline</span>
      )}
    </div>
  );
};

// Usage in parent component
const VariantResults = ({ results }) => {
  return (
    <div className="variant-results">
      <div className="prediction-section">
        <h2>Prediction: {results.prediction}</h2>
        <p>Confidence: {results.confidence}%</p>
      </div>

      <div className="rag-response">
        <h3>Clinical Interpretation</h3>
        <div dangerouslySetInnerHTML={{ __html: marked(results.rag_response) }} />
      </div>

      <div className="sources-section">
        <h3>Evidence Sources</h3>
        <div className="sources-grid">
          {results.sources.map((source, index) => (
            <SourceCard key={index} source={source} />
          ))}
        </div>
      </div>
    </div>
  );
};

export default VariantResults;
```

---

## CSS Styling Example

```css
/* Source Cards */
.source-card {
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  padding: 16px;
  background: white;
  transition: all 0.2s;
}

.source-card:hover {
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
  transform: translateY(-2px);
}

/* Type-specific colors */
.source-card.source-clinvar {
  border-left: 4px solid #3b82f6; /* Blue */
}

.source-card.source-pharmgkb {
  border-left: 4px solid #f59e0b; /* Orange */
}

.source-card.source-pubmed {
  border-left: 4px solid #10b981; /* Green */
}

/* Source Header */
.source-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
}

.source-icon {
  font-size: 24px;
}

.source-name {
  font-weight: 600;
  color: #374151;
}

.confidence-badge {
  margin-left: auto;
  font-size: 14px;
}

/* Source Title */
.source-title {
  font-size: 14px;
  font-weight: 500;
  color: #1f2937;
  margin-bottom: 12px;
  line-height: 1.4;
}

/* Source Link */
.source-link {
  display: inline-flex;
  align-items: center;
  color: #3b82f6;
  text-decoration: none;
  font-size: 14px;
  font-weight: 500;
  transition: color 0.2s;
}

.source-link:hover {
  color: #2563eb;
  text-decoration: underline;
}

/* Badges */
.badge {
  display: inline-block;
  padding: 4px 8px;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 500;
}

.badge.warning {
  background-color: #fef3c7;
  color: #92400e;
}

.badge.gray,
.badge-gray {
  background-color: #f3f4f6;
  color: #6b7280;
}

/* Sources Grid */
.sources-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: 16px;
  margin-top: 16px;
}
```

---

## URL Validation

All URLs are guaranteed to be valid or `null`. Here's the validation logic:

```javascript
// Frontend validation (optional, but good practice)
const validateSourceUrl = (source) => {
  if (!source.url) {
    return false; // No URL, display as internal source
  }

  const validDomains = [
    'ncbi.nlm.nih.gov',
    'pubmed.ncbi.nlm.nih.gov',
    'pharmgkb.org'
  ];

  try {
    const url = new URL(source.url);
    return validDomains.some(domain => url.hostname.includes(domain));
  } catch {
    return false;
  }
};
```

---

## Handling Edge Cases

### Case 1: ClinVar variant with no URL
```json
{
  "source": "ClinVar",
  "title": "SCN1A variant - Uncertain significance",
  "url": "https://www.ncbi.nlm.nih.gov/clinvar/?term=SCN1A[gene]",
  "type": "clinvar"
}
```
**Frontend**: Link goes to ClinVar search for that gene

### Case 2: ILAE guidelines (no external URL)
```json
{
  "source": "ilae_guidelines.txt",
  "title": "ILAE Treatment Guidelines",
  "url": null,
  "type": "pubmed"
}
```
**Frontend**: Display as "Internal Guideline" badge, no clickable link

### Case 3: PharmGKB gene page
```json
{
  "source": "PharmGKB",
  "title": "Drug-Gene Interactions for SCN1A",
  "url": "https://www.pharmgkb.org/gene/SCN1A",
  "type": "pharmgkb"
}
```
**Frontend**: Link goes directly to gene page on PharmGKB

---

## Testing URLs

### Manual Testing

```bash
# Test the API
curl -X POST http://localhost:8000/analyze_variant \
  -H "Content-Type: application/json" \
  -d '{
    "gene": "SCN1A",
    "chromosome": "2",
    "reference_allele": "G",
    "alternate_allele": "A",
    "consequence": "missense_variant",
    "variant_type": "single nucleotide variant"
  }' | jq '.sources'

# Expected output:
# [
#   {
#     "source": "ClinVar",
#     "title": "...",
#     "url": "https://www.ncbi.nlm.nih.gov/clinvar/...",
#     "type": "clinvar"
#   },
#   {
#     "source": "PharmGKB",
#     "title": "Drug-Gene Interactions for SCN1A",
#     "url": "https://www.pharmgkb.org/gene/SCN1A",
#     "type": "pharmgkb"
#   },
#   ...
# ]
```

### Verify URLs are clickable

1. Copy a URL from the API response
2. Paste in browser
3. Should open the correct page

**Example URLs to test:**
- ClinVar: https://www.ncbi.nlm.nih.gov/clinvar/variation/123456/
- PharmGKB: https://www.pharmgkb.org/gene/SCN1A
- PubMed: https://pubmed.ncbi.nlm.nih.gov/29778428/

---

## Source Priority Display

You may want to visually indicate which sources are more reliable:

```jsx
const getSourcePriority = (type, score) => {
  if (type === 'clinvar' && score >= 0.9) {
    return { level: 'highest', label: 'High Confidence Evidence' };
  } else if (type === 'pharmgkb') {
    return { level: 'high', label: 'Drug Interaction Warning' };
  } else if (score >= 0.8) {
    return { level: 'medium', label: 'Supporting Evidence' };
  } else {
    return { level: 'low', label: 'Additional Context' };
  }
};
```

---

## Complete Example Response

Here's what your frontend will receive for a typical pathogenic SCN1A variant:

```json
{
  "prediction": "Pathogenic",
  "confidence": 87.3,
  "pathogenic_probability": 0.873,
  "benign_probability": 0.127,
  "variant_info": {
    "gene": "SCN1A",
    "chromosome": "2",
    "reference_allele": "G",
    "alternate_allele": "A",
    "consequence": "missense_variant",
    "variant_type": "single nucleotide variant"
  },
  "is_pathogenic": true,
  "rag_response": "## 🧬 Variant Interpretation\n\nThis <span class=\"gene\">SCN1A</span> missense variant...",
  "sources": [
    {
      "source": "ClinVar",
      "title": "NM_001165963.4(SCN1A):c.1645T>G (p.Tyr549Asp) - Pathogenic",
      "url": "https://www.ncbi.nlm.nih.gov/clinvar/variation/485322/",
      "score": 1.0,
      "type": "clinvar"
    },
    {
      "source": "ClinVar",
      "title": "NM_001165963.4(SCN1A):c.2839G>A (p.Glu947Lys) - Likely pathogenic",
      "url": "https://www.ncbi.nlm.nih.gov/clinvar/variation/512093/",
      "score": 1.0,
      "type": "clinvar"
    },
    {
      "source": "PharmGKB",
      "title": "Drug-Gene Interactions for SCN1A",
      "url": "https://www.pharmgkb.org/gene/SCN1A",
      "score": 0.95,
      "type": "pharmgkb"
    },
    {
      "source": "pmid_29778428.txt",
      "title": "Treatment of Dravet syndrome",
      "pmid": "29778428",
      "url": "https://pubmed.ncbi.nlm.nih.gov/29778428/",
      "score": 0.87,
      "type": "pubmed"
    },
    {
      "source": "ilae_guidelines.txt",
      "title": "ILAE Treatment Guidelines",
      "url": null,
      "score": 0.84,
      "type": "pubmed"
    }
  ]
}
```

---

## Summary

✅ **All sources have proper URLs:**
- **ClinVar**: Direct variant page or gene search
- **PharmGKB**: Gene-specific page (e.g., `/gene/SCN1A`)
- **PubMed**: Direct article link (e.g., `/29778428/`)
- **ILAE/Internal**: `url: null` (display as internal guideline)

✅ **Frontend receives:**
- `url` field for all sources (string or null)
- `type` field to identify source category
- `title` field for display
- `score` field for confidence

✅ **Links are clickable and go to the right place:**
- ClinVar → Specific variant interpretation page
- PharmGKB → Gene drug interaction page
- PubMed → Full article abstract

**Your frontend can now display beautiful, clickable source cards with proper attribution!** 🎨
