import React, { useState } from 'react';
import type { VariantInput } from '../types';
import {
  EPILEPSY_GENES,
  CHROMOSOMES,
  CONSEQUENCES,
  VARIANT_TYPES,
  REVIEW_STATUSES,
  ORIGINS
} from '../types';

interface VariantFormProps {
  onSubmit: (variant: VariantInput) => void;
  isLoading: boolean;
}

const VariantForm: React.FC<VariantFormProps> = ({ onSubmit, isLoading }) => {
  const [formData, setFormData] = useState<VariantInput>({
    gene: 'SCN1A',
    chromosome: '2',
    reference_allele: 'C',
    alternate_allele: 'T',
    consequence: 'missense_variant',
    variant_type: 'single nucleotide variant',
    review_status: 'no assertion criteria provided',
    origin: 'germline'
  });

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    const { name, value } = e.target;
    setFormData(prev => ({ ...prev, [name]: value }));
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onSubmit(formData);
  };

  // Example variants for quick testing
  const exampleVariants = [
    {
      name: 'SCN1A Nonsense (Pathogenic)',
      data: {
        gene: 'SCN1A',
        chromosome: '2',
        reference_allele: 'C',
        alternate_allele: 'T',
        consequence: 'nonsense',
        variant_type: 'single nucleotide variant',
        review_status: 'criteria provided, multiple submitters',
        origin: 'germline'
      }
    },
    {
      name: 'KCNQ2 Stop-gained (Pathogenic)',
      data: {
        gene: 'KCNQ2',
        chromosome: '20',
        reference_allele: 'C',
        alternate_allele: 'T',
        consequence: 'stop_gained',
        variant_type: 'single nucleotide variant',
        review_status: 'reviewed by expert panel',
        origin: 'de novo (confirmed)'
      }
    },
    {
      name: 'TSC2 Frameshift (Pathogenic)',
      data: {
        gene: 'TSC2',
        chromosome: '16',
        reference_allele: 'AG',
        alternate_allele: 'A',
        consequence: 'frameshift_variant',
        variant_type: 'deletion',
        review_status: 'criteria provided, single submitter',
        origin: 'germline'
      }
    },
    {
      name: 'SLC2A1 Synonymous (Likely Benign)',
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
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      {/* Example variants */}
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
          </label>
          <select
            id="review_status"
            name="review_status"
            value={formData.review_status}
            onChange={handleChange}
            className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500"
          >
            {REVIEW_STATUSES.map(status => (
              <option key={status} value={status}>{status}</option>
            ))}
          </select>
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
