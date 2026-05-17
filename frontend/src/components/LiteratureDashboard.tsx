import React, { useState } from 'react';
import { getLiterature } from '../services/api';
import { EPILEPSY_GENES, LiteraturePaper } from '../types';

interface LiteratureDashboardProps {
  // Optional: Pass a default gene from parent
  defaultGene?: string;
}

const LiteratureDashboard: React.FC<LiteratureDashboardProps> = ({ defaultGene }) => {
  const [selectedGene, setSelectedGene] = useState<string>(defaultGene || 'SCN1A');
  const [papers, setPapers] = useState<LiteraturePaper[]>([]);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [cached, setCached] = useState<boolean>(false);
  const [expandedPapers, setExpandedPapers] = useState<Set<string>>(new Set());

  const handleFetchLiterature = async () => {
    setLoading(true);
    setError(null);
    setPapers([]);

    try {
      const response = await getLiterature(selectedGene);
      setPapers(response.papers);
      setCached(response.cached);
      setExpandedPapers(new Set());
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to fetch literature');
      console.error('Literature fetch error:', err);
    } finally {
      setLoading(false);
    }
  };

  const togglePaperExpansion = (pmid: string) => {
    const newExpanded = new Set(expandedPapers);
    if (newExpanded.has(pmid)) {
      newExpanded.delete(pmid);
    } else {
      newExpanded.add(pmid);
    }
    setExpandedPapers(newExpanded);
  };

  const getCategoryColor = (category: string): string => {
    const colorMap: Record<string, string> = {
      'Meta-analysis': 'bg-purple-100 text-purple-800',
      'Randomized Controlled Trial': 'bg-blue-100 text-blue-800',
      'Systematic Review': 'bg-green-100 text-green-800',
      'Review': 'bg-yellow-100 text-yellow-800',
      'Case Report': 'bg-orange-100 text-orange-800',
      'Other': 'bg-gray-100 text-gray-800'
    };
    return colorMap[category] || 'bg-gray-100 text-gray-800';
  };

  const getCategoryIcon = (category: string): string => {
    const iconMap: Record<string, string> = {
      'Meta-analysis': '📊',
      'Randomized Controlled Trial': '🧪',
      'Systematic Review': '🔍',
      'Review': '📚',
      'Case Report': '📋',
      'Other': '📄'
    };
    return iconMap[category] || '📄';
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 p-6">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="bg-white rounded-lg shadow-lg p-6 mb-6">
          <h1 className="text-3xl font-bold text-gray-900 mb-2">
            📚 Recent Literature Updates
          </h1>
          <p className="text-gray-600">
            Explore recent PubMed publications on epilepsy genetics with AI-generated summaries.
            Papers are automatically added to the knowledge base for improved variant analysis.
          </p>
        </div>

        {/* Controls */}
        <div className="bg-white rounded-lg shadow-lg p-6 mb-6">
          <div className="flex flex-col md:flex-row gap-4 items-end">
            {/* Gene Selector */}
            <div className="flex-1">
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Select Gene
              </label>
              <select
                value={selectedGene}
                onChange={(e) => setSelectedGene(e.target.value)}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                disabled={loading}
              >
                {EPILEPSY_GENES.map((gene) => (
                  <option key={gene} value={gene}>
                    {gene}
                  </option>
                ))}
              </select>
            </div>

            {/* Fetch Button */}
            <button
              onClick={handleFetchLiterature}
              disabled={loading}
              className={`px-6 py-2 rounded-lg font-medium transition-colors ${
                loading
                  ? 'bg-gray-300 text-gray-500 cursor-not-allowed'
                  : 'bg-blue-600 text-white hover:bg-blue-700'
              }`}
            >
              {loading ? (
                <span className="flex items-center">
                  <svg className="animate-spin -ml-1 mr-2 h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                  </svg>
                  Fetching...
                </span>
              ) : (
                'Fetch Literature'
              )}
            </button>
          </div>

          {/* Cache indicator */}
          {papers.length > 0 && (
            <div className="mt-4 text-sm text-gray-600">
              {cached ? (
                <span className="flex items-center">
                  ⚡ Loaded from cache (refreshed within 24 hours)
                </span>
              ) : (
                <span className="flex items-center">
                  🔄 Fresh data fetched from PubMed & added to knowledge base
                </span>
              )}
            </div>
          )}
        </div>

        {/* Error */}
        {error && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-6">
            <p className="text-red-800 font-medium">❌ {error}</p>
          </div>
        )}

        {/* Papers List */}
        {papers.length > 0 ? (
          <div className="space-y-4">
            {papers.map((paper) => {
              const isExpanded = expandedPapers.has(paper.pmid);

              return (
                <div
                  key={paper.pmid}
                  className="bg-white rounded-lg shadow-md hover:shadow-lg transition-shadow"
                >
                  <div className="p-6">
                    {/* Header */}
                    <div className="flex items-start justify-between mb-3">
                      <div className="flex-1">
                        <div className="flex items-center gap-2 mb-2">
                          <span
                            className={`inline-flex items-center px-3 py-1 rounded-full text-xs font-medium ${getCategoryColor(
                              paper.category
                            )}`}
                          >
                            {getCategoryIcon(paper.category)} {paper.category}
                          </span>
                          <a
                            href={paper.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-blue-600 hover:text-blue-800 text-sm font-medium"
                          >
                            PMID: {paper.pmid} ↗
                          </a>
                        </div>
                        <h3 className="text-xl font-semibold text-gray-900 mb-2">
                          {paper.title}
                        </h3>
                        <div className="text-sm text-gray-600">
                          <p className="mb-1">{paper.authors}</p>
                          <p>
                            <span className="font-medium">{paper.journal}</span> • {paper.pub_date}
                          </p>
                        </div>
                      </div>
                    </div>

                    {/* AI Summary */}
                    <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-3">
                      <h4 className="text-sm font-semibold text-blue-900 mb-2">
                        AI Summary
                      </h4>
                      <p className="text-gray-800 text-sm leading-relaxed">
                        {paper.summary}
                      </p>
                    </div>

                    {/* Abstract (Expandable) */}
                    <div>
                      <button
                        onClick={() => togglePaperExpansion(paper.pmid)}
                        className="text-blue-600 hover:text-blue-800 font-medium text-sm flex items-center"
                      >
                        {isExpanded ? '▼' : '▶'} {isExpanded ? 'Hide' : 'Show'} Full Abstract
                      </button>
                      {isExpanded && (
                        <div className="mt-3 p-4 bg-gray-50 rounded-lg text-sm text-gray-700 leading-relaxed">
                          {paper.abstract}
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        ) : !loading && papers.length === 0 ? (
          <div className="bg-white rounded-lg shadow-lg p-12 text-center">
            <div className="text-6xl mb-4">📚</div>
            <h3 className="text-xl font-semibold text-gray-900 mb-2">
              Select a gene and fetch literature
            </h3>
            <p className="text-gray-600">
              View recent PubMed publications with AI-generated summaries and clinical insights.
            </p>
          </div>
        ) : null}

        {/* Loading state */}
        {loading && (
          <div className="bg-white rounded-lg shadow-lg p-12 text-center">
            <svg className="animate-spin h-12 w-12 text-blue-600 mx-auto mb-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
            <p className="text-gray-600 text-lg">
              Fetching recent publications for {selectedGene}...
            </p>
            <p className="text-gray-500 text-sm mt-2">
              This may take a few moments
            </p>
          </div>
        )}
      </div>
    </div>
  );
};

export default LiteratureDashboard;
