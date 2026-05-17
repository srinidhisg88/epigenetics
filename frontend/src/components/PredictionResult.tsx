import React from 'react';
import type { FullAnalysisResponse } from '../types';
import ACMGPanel from './ACMGPanel';

interface PredictionResultProps {
  result: FullAnalysisResponse;
}

const PredictionResult: React.FC<PredictionResultProps> = ({ result }) => {
  const isPathogenic = result.is_pathogenic;
  const confidenceColor = result.confidence >= 80 ? 'text-green-600' : result.confidence >= 60 ? 'text-yellow-600' : 'text-gray-600';

  return (
    <div className="bg-white rounded-lg shadow-md overflow-hidden">
      {/* Prediction Header */}
      <div className={`p-6 ${isPathogenic ? 'bg-red-50 border-b-4 border-red-500' : 'bg-green-50 border-b-4 border-green-500'}`}>
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-lg font-semibold text-gray-900">
              {result.variant_info.gene}
            </h3>
            <p className="text-sm text-gray-600">
              {result.variant_info.reference_allele} &rarr; {result.variant_info.alternate_allele} ({result.variant_info.consequence.replace(/_/g, ' ')})
            </p>
          </div>
          <div className="text-right">
            <span className={`inline-flex items-center px-4 py-2 rounded-full text-lg font-bold ${
              isPathogenic ? 'bg-red-100 text-red-800' : 'bg-green-100 text-green-800'
            }`}>
              {isPathogenic ? '⚠' : '✓'} {result.prediction}
            </span>
          </div>
        </div>
      </div>

      {/* Confidence Scores */}
      <div className="p-6 border-b">
        <h4 className="text-sm font-medium text-gray-700 mb-4">Confidence Scores</h4>

        {/* Overall Confidence */}
        <div className="mb-4">
          <div className="flex justify-between text-sm mb-1">
            <span className="font-medium">Overall Confidence</span>
            <span className={`font-bold ${confidenceColor}`}>{result.confidence.toFixed(1)}%</span>
          </div>
          <div className="w-full bg-gray-200 rounded-full h-2">
            <div
              className={`h-2 rounded-full ${result.confidence >= 80 ? 'bg-green-500' : result.confidence >= 60 ? 'bg-yellow-500' : 'bg-gray-500'}`}
              style={{ width: `${result.confidence}%` }}
            ></div>
          </div>
        </div>

        {/* Probability Bars */}
        <div className="grid grid-cols-2 gap-4">
          <div>
            <div className="flex justify-between text-xs mb-1">
              <span className="text-red-600">Pathogenic</span>
              <span>{(result.pathogenic_probability * 100).toFixed(1)}%</span>
            </div>
            <div className="w-full bg-gray-200 rounded-full h-2">
              <div
                className="bg-red-500 h-2 rounded-full"
                style={{ width: `${result.pathogenic_probability * 100}%` }}
              ></div>
            </div>
          </div>
          <div>
            <div className="flex justify-between text-xs mb-1">
              <span className="text-green-600">Benign</span>
              <span>{(result.benign_probability * 100).toFixed(1)}%</span>
            </div>
            <div className="w-full bg-gray-200 rounded-full h-2">
              <div
                className="bg-green-500 h-2 rounded-full"
                style={{ width: `${result.benign_probability * 100}%` }}
              ></div>
            </div>
          </div>
        </div>
      </div>

      {/* Variant Details */}
      <div className="p-6 bg-gray-50">
        <h4 className="text-sm font-medium text-gray-700 mb-3">Variant Details</h4>
        <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
          <dt className="text-gray-500">Gene:</dt>
          <dd className="font-medium">{result.variant_info.gene}</dd>
          <dt className="text-gray-500">Chromosome:</dt>
          <dd className="font-medium">{result.variant_info.chromosome}</dd>
          <dt className="text-gray-500">Change:</dt>
          <dd className="font-medium font-mono">{result.variant_info.reference_allele} → {result.variant_info.alternate_allele}</dd>
          <dt className="text-gray-500">Consequence:</dt>
          <dd className="font-medium">{result.variant_info.consequence.replace(/_/g, ' ')}</dd>
          <dt className="text-gray-500">Type:</dt>
          <dd className="font-medium">{result.variant_info.variant_type}</dd>
        </dl>
      </div>

      {/* Next Steps Indicator */}
      {isPathogenic && (
        <div className="p-4 bg-red-50 border-t border-red-200">
          <div className="flex items-center gap-2 text-red-700">
            <svg className="h-5 w-5 animate-pulse" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7l5 5m0 0l-5 5m5-5H6" />
            </svg>
            <span className="text-sm font-medium">
              Fetching treatment recommendations... Check "Diagnostic Results" tab
            </span>
          </div>
        </div>
      )}

      {!isPathogenic && (
        <div className="p-4 bg-green-50 border-t border-green-200">
          <p className="text-sm text-green-700">
            <strong>Benign prediction:</strong> No additional treatment recommendations needed.
            The variant is predicted to be non-pathogenic.
          </p>
        </div>
      )}

      {/* ACMG Classification Panel */}
      {result.acmg_classification && (
        <div className="p-4 border-t">
          <ACMGPanel
            acmg={result.acmg_classification}
            gene={result.variant_info.gene}
          />
        </div>
      )}
    </div>
  );
};

export default PredictionResult;
