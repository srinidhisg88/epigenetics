import React, { useState, useRef, useEffect } from 'react';
import type { VariantInput } from '../types';
import {
  EPILEPSY_GENES,
  CHROMOSOMES,
  CONSEQUENCES,
  VARIANT_TYPES,
  REVIEW_STATUSES,
  ORIGINS
} from '../types';

const API_BASE = process.env.REACT_APP_API_URL || 'http://localhost:8000';

interface VariantFormProps {
  onSubmit: (variant: VariantInput) => void;
  isLoading: boolean;
}

const VariantForm: React.FC<VariantFormProps> = ({ onSubmit, isLoading }) => {
  const [formData, setFormData] = useState<VariantInput>({
    gene: 'SCN1A',
    chromosome: '2',
    position: undefined,
    reference_allele: 'C',
    alternate_allele: 'T',
    consequence: 'missense_variant',
    variant_type: 'single nucleotide variant',
    review_status: 'no assertion criteria provided',
    origin: 'germline'
  });

  const [hgvs, setHgvs] = useState('');
  const [hgvsStatus, setHgvsStatus] = useState<'idle' | 'loading' | 'success' | 'error'>('idle');
  const [hgvsMessage, setHgvsMessage] = useState('');
  const [reviewStatus, setReviewStatus] = useState<'idle' | 'loading' | 'found' | 'not_found'>('idle');
  const debounceTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const reviewTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const normalizeReviewStatus = (raw: string): string => {
    const s = raw.toLowerCase();
    if (s.includes('practice guideline'))    return 'practice guideline';
    if (s.includes('expert panel'))          return 'reviewed by expert panel';
    if (s.includes('multiple submitters'))   return 'criteria provided, multiple submitters, no conflicts';
    if (s.includes('conflicting'))           return 'criteria provided, conflicting classifications';
    if (s.includes('single submitter') || s.includes('criteria provided')) return 'criteria provided, single submitter';
    if (s.includes('no assertion'))          return 'no assertion criteria provided';
    return 'no classification provided';
  };

  // Auto-fetch review status whenever position becomes available
  useEffect(() => {
    const { gene, chromosome, position, reference_allele, alternate_allele } = formData;
    if (!position || !chromosome || !reference_allele || !alternate_allele) {
      setReviewStatus('idle');
      return;
    }

    if (reviewTimer.current) clearTimeout(reviewTimer.current);
    reviewTimer.current = setTimeout(async () => {
      setReviewStatus('loading');
      try {
        const params = new URLSearchParams({
          gene,
          chromosome,
          position:          String(position),
          reference_allele,
          alternate_allele,
        });
        const res = await fetch(`${API_BASE}/review_status?${params}`);
        if (!res.ok) throw new Error();
        const data = await res.json();

        if (data.source === 'clinvar_exact') {
          setFormData(prev => ({ ...prev, review_status: normalizeReviewStatus(data.review_status) }));
          setReviewStatus('found');
        } else {
          setReviewStatus('not_found');
        }
      } catch {
        setReviewStatus('not_found');
      }
    }, 800);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [formData.position, formData.chromosome, formData.reference_allele, formData.alternate_allele, formData.gene]);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    const { name, value } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: name === 'position' ? (value ? parseInt(value) : undefined) : value
    }));
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onSubmit(formData);
  };

  // Auto-resolve HGVS notation → chromosome + position + ref + alt
  const handleHgvsChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = e.target.value;
    setHgvs(val);
    setHgvsStatus('idle');
    setHgvsMessage('');

    if (!val.trim()) return;

    if (debounceTimer.current) clearTimeout(debounceTimer.current);
    debounceTimer.current = setTimeout(async () => {
      setHgvsStatus('loading');
      try {
        const res = await fetch(`${API_BASE}/resolve_hgvs?hgvs=${encodeURIComponent(val.trim())}`);
        if (!res.ok) throw new Error('API error');
        const data = await res.json();

        if (data.success) {
          setFormData(prev => ({
            ...prev,
            chromosome:       data.chromosome,
            position:         data.position,
            reference_allele: data.ref,
            alternate_allele: data.alt,
            ...(data.gene        && EPILEPSY_GENES.includes(data.gene as any) ? { gene: data.gene as any } : {}),
            ...(data.consequence && CONSEQUENCES.includes(data.consequence as any) ? { consequence: data.consequence as any } : {}),
            ...(data.variant_type && VARIANT_TYPES.includes(data.variant_type as any) ? { variant_type: data.variant_type as any } : {}),
          }));
          setHgvsStatus('success');
          setHgvsMessage(data.message);
        } else {
          setHgvsStatus('error');
          setHgvsMessage(data.message);
        }
      } catch {
        setHgvsStatus('error');
        setHgvsMessage('Could not reach the server. Enter coordinates manually.');
      }
    }, 700);
  };

  const exampleVariants = [
    {
      name: 'SCN1A Missense (Pathogenic)',
      data: {
        gene: 'SCN1A',
        chromosome: '2',
        position: 165992332,      // NM_001165963.4:c.4943G>T — Pathogenic/Likely pathogenic (ClinVar)
        reference_allele: 'G',
        alternate_allele: 'T',
        consequence: 'missense_variant',
        variant_type: 'single nucleotide variant',
        review_status: 'criteria provided, multiple submitters, no conflicts',
        origin: 'germline'
      }
    },
    {
      name: 'KCNQ2 Missense (Pathogenic)',
      data: {
        gene: 'KCNQ2',
        chromosome: '20',
        position: 63442429,       // NM_172107.4:c.793G>T — Pathogenic/Likely pathogenic (ClinVar)
        reference_allele: 'G',
        alternate_allele: 'T',
        consequence: 'missense_variant',
        variant_type: 'single nucleotide variant',
        review_status: 'criteria provided, multiple submitters, no conflicts',
        origin: 'de novo (confirmed)'
      }
    },
    {
      name: 'TSC2 Indel (ClinVar)',
      data: {
        gene: 'TSC2',
        chromosome: '16',
        position: 2088293,        // NM_000548.5:c.5238_5255del — real ClinVar variant
        reference_allele: 'AG',
        alternate_allele: 'A',
        consequence: 'frameshift_variant',
        variant_type: 'deletion',
        review_status: 'criteria provided, multiple submitters, no conflicts',
        origin: 'germline'
      }
    },
    {
      name: 'SLC2A1 Synonymous (Benign)',
      data: {
        gene: 'SLC2A1',
        chromosome: '1',
        reference_allele: 'C',
        alternate_allele: 'T',
        consequence: 'synonymous_variant',
        variant_type: 'single nucleotide variant',
        review_status: 'no assertion criteria provided',
        origin: 'germline'
      }
    }
  ];

  const loadExample = (example: typeof exampleVariants[0]) => {
    setFormData(example.data as VariantInput);
    setHgvs('');
    setHgvsStatus('idle');
    setHgvsMessage('');
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-6">

      {/* Quick Examples */}
      <div className="bg-gray-50 p-4 rounded-lg">
        <h3 className="text-sm font-medium text-gray-700 mb-2">Quick Examples</h3>
        <div className="flex flex-wrap gap-2">
          {exampleVariants.map((example, idx) => (
            <button
              key={idx}
              type="button"
              onClick={() => loadExample(example)}
              className="px-3 py-1 text-xs bg-white border border-gray-300 rounded-full hover:bg-blue-50 hover:border-blue-300 transition-colors"
            >
              {example.name}
            </button>
          ))}
        </div>
      </div>

      {/* HGVS Auto-resolver */}
      <div className="bg-blue-50 border border-blue-200 p-4 rounded-lg">
        <label className="block text-sm font-medium text-blue-800 mb-1">
          HGVS Notation
          <span className="ml-2 text-xs font-normal text-blue-500">(optional — auto-fills coordinates below)</span>
        </label>
        <input
          type="text"
          value={hgvs}
          onChange={handleHgvsChange}
          placeholder="e.g., NM_006920.6:c.4849C>T"
          className="w-full px-3 py-2 border border-blue-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 bg-white font-mono text-sm"
        />
        {hgvsStatus === 'loading' && (
          <p className="mt-1 text-xs text-blue-500 animate-pulse">Resolving via Ensembl...</p>
        )}
        {hgvsStatus === 'success' && (
          <p className="mt-1 text-xs text-green-600">✓ {hgvsMessage}</p>
        )}
        {hgvsStatus === 'error' && (
          <p className="mt-1 text-xs text-red-500">✗ {hgvsMessage}</p>
        )}
        {hgvsStatus === 'idle' && !hgvs && (
          <p className="mt-1 text-xs text-gray-400">
            Copy from your lab report. Resolves to chromosome, position, ref and alt automatically.
          </p>
        )}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">

        {/* Gene */}
        <div>
          <label htmlFor="gene" className="block text-sm font-medium text-gray-700 mb-1">
            Gene Symbol *
          </label>
          <select
            id="gene"
            name="gene"
            value={formData.gene}
            onChange={handleChange}
            className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500"
          >
            {EPILEPSY_GENES.map(gene => (
              <option key={gene} value={gene}>{gene}</option>
            ))}
          </select>
        </div>

        {/* Chromosome */}
        <div>
          <label htmlFor="chromosome" className="block text-sm font-medium text-gray-700 mb-1">
            Chromosome *
          </label>
          <select
            id="chromosome"
            name="chromosome"
            value={formData.chromosome}
            onChange={handleChange}
            className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500"
          >
            {CHROMOSOMES.map(chr => (
              <option key={chr} value={chr}>{chr}</option>
            ))}
          </select>
        </div>

        {/* Genomic Position */}
        <div>
          <label htmlFor="position" className="block text-sm font-medium text-gray-700 mb-1">
            Genomic Position
            <span className="ml-2 text-xs font-normal text-gray-400">(GRCh38 — enables exact gnomAD & ClinVar lookup)</span>
          </label>
          <input
            type="number"
            id="position"
            name="position"
            value={formData.position ?? ''}
            onChange={handleChange}
            placeholder="e.g., 166931824"
            className={`w-full px-3 py-2 border rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500
              ${formData.position ? 'border-green-400 bg-green-50' : 'border-gray-300'}`}
          />
          {!formData.position && (
            <p className="mt-1 text-xs text-gray-400">
              Without position: gnomAD skipped, ClinVar uses gene-level search
            </p>
          )}
          {formData.position && (
            <p className="mt-1 text-xs text-green-600">
              ✓ Exact gnomAD & ClinVar lookup enabled
            </p>
          )}
        </div>

        {/* Reference Allele */}
        <div>
          <label htmlFor="reference_allele" className="block text-sm font-medium text-gray-700 mb-1">
            Reference Allele *
          </label>
          <input
            type="text"
            id="reference_allele"
            name="reference_allele"
            value={formData.reference_allele}
            onChange={handleChange}
            placeholder="e.g., C, AG, ATCG"
            className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 uppercase"
          />
        </div>

        {/* Alternate Allele */}
        <div>
          <label htmlFor="alternate_allele" className="block text-sm font-medium text-gray-700 mb-1">
            Alternate Allele *
          </label>
          <input
            type="text"
            id="alternate_allele"
            name="alternate_allele"
            value={formData.alternate_allele}
            onChange={handleChange}
            placeholder="e.g., T, A, GCTA"
            className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 uppercase"
          />
        </div>

        {/* Consequence */}
        <div>
          <label htmlFor="consequence" className="block text-sm font-medium text-gray-700 mb-1">
            Molecular Consequence *
          </label>
          <select
            id="consequence"
            name="consequence"
            value={formData.consequence}
            onChange={handleChange}
            className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500"
          >
            {CONSEQUENCES.map(cons => (
              <option key={cons} value={cons}>
                {cons.replace(/_/g, ' ')}
              </option>
            ))}
          </select>
        </div>

        {/* Variant Type */}
        <div>
          <label htmlFor="variant_type" className="block text-sm font-medium text-gray-700 mb-1">
            Variant Type
          </label>
          <select
            id="variant_type"
            name="variant_type"
            value={formData.variant_type}
            onChange={handleChange}
            className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500"
          >
            {VARIANT_TYPES.map(type => (
              <option key={type} value={type}>{type}</option>
            ))}
          </select>
        </div>

        {/* Review Status */}
        <div>
          <label htmlFor="review_status" className="block text-sm font-medium text-gray-700 mb-1">
            Review Status
            {reviewStatus === 'loading' && (
              <span className="ml-2 text-xs text-blue-500 animate-pulse">Fetching from ClinVar...</span>
            )}
            {reviewStatus === 'found' && (
              <span className="ml-2 text-xs text-green-600">Auto-filled from ClinVar</span>
            )}
            {reviewStatus === 'not_found' && (
              <span className="ml-2 text-xs text-gray-400">Not in ClinVar — set manually</span>
            )}
          </label>
          <select
            id="review_status"
            name="review_status"
            value={formData.review_status}
            onChange={handleChange}
            disabled={reviewStatus === 'loading'}
            className={`w-full px-3 py-2 border rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500
              ${reviewStatus === 'loading'  ? 'bg-gray-100 border-gray-200 cursor-wait' : ''}
              ${reviewStatus === 'found'    ? 'border-green-400 bg-green-50' : ''}
              ${reviewStatus === 'idle' || reviewStatus === 'not_found' ? 'border-gray-300' : ''}
            `}
          >
            {REVIEW_STATUSES.map(status => (
              <option key={status} value={status}>{status}</option>
            ))}
          </select>
          {reviewStatus === 'idle' && (
            <p className="mt-1 text-xs text-gray-400">
              Provide position above for auto-fill, or select manually
            </p>
          )}
        </div>

        {/* Origin */}
        <div>
          <label htmlFor="origin" className="block text-sm font-medium text-gray-700 mb-1">
            Variant Origin
          </label>
          <select
            id="origin"
            name="origin"
            value={formData.origin}
            onChange={handleChange}
            className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500"
          >
            {ORIGINS.map(origin => (
              <option key={origin} value={origin}>{origin}</option>
            ))}
          </select>
          {(formData.origin === 'de novo (confirmed)' || formData.origin === 'de novo') && (
            <p className="mt-1 text-xs text-indigo-600">
              {formData.origin === 'de novo (confirmed)'
                ? 'PS2 (+4 Strong) — parental testing confirms variant absent in both parents.'
                : 'PM6 (+2 Moderate) — de novo assumed but parental testing not performed.'}
            </p>
          )}
        </div>

      </div>

      {/* Submit Button */}
      <div className="pt-4">
        <button
          type="submit"
          disabled={isLoading}
          className={`w-full py-3 px-4 border border-transparent rounded-md shadow-sm text-white font-medium
            ${isLoading
              ? 'bg-gray-400 cursor-not-allowed'
              : 'bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500'
            } transition-colors`}
        >
          {isLoading ? (
            <span className="flex items-center justify-center">
              <svg className="animate-spin -ml-1 mr-3 h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
              </svg>
              Analyzing...
            </span>
          ) : (
            'Predict Pathogenicity'
          )}
        </button>
      </div>
    </form>
  );
};

export default VariantForm;
