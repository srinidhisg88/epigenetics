import React, { useState } from 'react';
import Sidebar from './components/Sidebar';
import VariantForm from './components/VariantForm';
import PredictionResult from './components/PredictionResult';
import ChatInterface from './components/ChatInterface';
import LiteratureDashboard from './components/LiteratureDashboard';
import DisclaimerModal from './components/DisclaimerModal';
import { analyzeVariant } from './services/api';
import type { VariantInput, FullAnalysisResponse, Source } from './types';
import './App.css';

type TabType = 'analysis' | 'chat' | 'literature';

// Initial message for chat when RAG response is available
interface RAGChatMessage {
  gene: string;
  variant: string;
  prediction: string;
  confidence: number;
  consequence: string;
  ragResponse: string;
  sources: Source[];
}

function App() {
  const [activeTab, setActiveTab] = useState<TabType>('analysis');
  const [analysisResult, setAnalysisResult] = useState<FullAnalysisResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // RAG chat data - populated when pathogenic variant is analyzed
  const [ragChatData, setRagChatData] = useState<RAGChatMessage | null>(null);

  const handleAnalysis = async (variant: VariantInput) => {
    setIsLoading(true);
    setError(null);
    setRagChatData(null);

    try {
      const result = await analyzeVariant(variant);
      setAnalysisResult(result);

      // If pathogenic with RAG response, auto-switch to chat
      if (result.is_pathogenic && result.rag_response) {
        setRagChatData({
          gene: result.variant_info.gene,
          variant: `${result.variant_info.reference_allele}>${result.variant_info.alternate_allele}`,
          prediction: result.prediction,
          confidence: result.confidence,
          consequence: result.variant_info.consequence,
          ragResponse: result.rag_response,
          sources: result.sources || []
        });
        // Auto-switch to chat tab
        setActiveTab('chat');
      }
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to get prediction. Is the API running?');
      setAnalysisResult(null);
    } finally {
      setIsLoading(false);
    }
  };

  const handleClearRagData = () => {
    setRagChatData(null);
  };

  const handleBackToAnalysis = () => {
    setActiveTab('analysis');
  };

  return (
    <div className="flex h-screen bg-gray-100">
      {/* Session disclaimer modal */}
      <DisclaimerModal />

      {/* Sidebar */}
      <Sidebar />

      {/* Main Content */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Tab Navigation */}
        <div className="bg-white border-b">
          <div className="px-6">
            <nav className="flex space-x-8">
              <button
                onClick={() => setActiveTab('analysis')}
                className={`py-4 px-1 border-b-2 font-medium text-sm transition-colors ${
                  activeTab === 'analysis'
                    ? 'border-blue-500 text-blue-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                }`}
              >
                <span className="flex items-center gap-2">
                  <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
                    <path fillRule="evenodd" d="M7 2a1 1 0 00-.707 1.707L7 4.414v3.758a1 1 0 01-.293.707l-4 4C.077 14.586-.372 15.5.293 16.5A1 1 0 001.5 17h17a1 1 0 001.207-.5c.665-1 .216-1.914-.5-2.621l-4-4a1 1 0 01-.293-.707V4.414l.707-.707A1 1 0 0015 2H7z" clipRule="evenodd" />
                  </svg>
                  Variant Analysis
                </span>
              </button>
              <button
                onClick={() => setActiveTab('chat')}
                className={`py-4 px-1 border-b-2 font-medium text-sm transition-colors ${
                  activeTab === 'chat'
                    ? 'border-blue-500 text-blue-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                }`}
              >
                <span className="flex items-center gap-2">
                  <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
                    <path fillRule="evenodd" d="M18 10c0 3.866-3.582 7-8 7a8.841 8.841 0 01-4.083-.98L2 17l1.338-3.123C2.493 12.767 2 11.434 2 10c0-3.866 3.582-7 8-7s8 3.134 8 7zM7 9H5v2h2V9zm8 0h-2v2h2V9zM9 9h2v2H9V9z" clipRule="evenodd" />
                  </svg>
                  Diagnostic Results
                  {ragChatData && (
                    <span className="ml-1 px-2 py-0.5 text-xs bg-red-100 text-red-600 rounded-full">
                      Pathogenic
                    </span>
                  )}
                </span>
              </button>
              <button
                onClick={() => setActiveTab('literature')}
                className={`py-4 px-1 border-b-2 font-medium text-sm transition-colors ${
                  activeTab === 'literature'
                    ? 'border-blue-500 text-blue-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                }`}
              >
                <span className="flex items-center gap-2">
                  <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
                    <path d="M9 4.804A7.968 7.968 0 005.5 4c-1.255 0-2.443.29-3.5.804v10A7.969 7.969 0 015.5 14c1.669 0 3.218.51 4.5 1.385A7.962 7.962 0 0114.5 14c1.255 0 2.443.29 3.5.804v-10A7.968 7.968 0 0014.5 4c-1.255 0-2.443.29-3.5.804V12a1 1 0 11-2 0V4.804z" />
                  </svg>
                  Literature
                </span>
              </button>
            </nav>
          </div>
        </div>

        {/* Persistent research disclaimer banner */}
        <div className="bg-amber-50 border-b border-amber-200 px-6 py-1.5 flex items-center gap-2 text-xs text-amber-800">
          <svg className="w-3.5 h-3.5 shrink-0 text-amber-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
              d="M12 9v2m0 4h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" />
          </svg>
          <span>
            <strong>Research prototype — not clinically validated.</strong>{' '}
            Outputs must be verified by a qualified clinical geneticist before any diagnostic use.
          </span>
        </div>

        {/* Content Area */}
        <div className="flex-1 overflow-y-auto">
          {activeTab === 'literature' ? (
            <LiteratureDashboard />
          ) : activeTab === 'analysis' ? (
            <div className="max-w-4xl mx-auto p-6">
              <div className="mb-6">
                <h2 className="text-2xl font-bold text-gray-900">Variant Pathogenicity Analysis</h2>
                <p className="text-gray-600 mt-1">
                  Enter variant details to predict pathogenicity. If pathogenic, treatment recommendations will be shown automatically.
                </p>
              </div>

              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                {/* Form */}
                <div className="bg-white rounded-lg shadow-md p-6">
                  <h3 className="text-lg font-medium text-gray-900 mb-4">Variant Information</h3>
                  <VariantForm onSubmit={handleAnalysis} isLoading={isLoading} />
                </div>

                {/* Result Preview */}
                <div>
                  {error && (
                    <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-4">
                      <div className="flex">
                        <div className="flex-shrink-0">
                          <svg className="h-5 w-5 text-red-400" viewBox="0 0 20 20" fill="currentColor">
                            <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
                          </svg>
                        </div>
                        <div className="ml-3">
                          <h3 className="text-sm font-medium text-red-800">Error</h3>
                          <p className="text-sm text-red-700 mt-1">{error}</p>
                        </div>
                      </div>
                    </div>
                  )}

                  {isLoading ? (
                    <div className="bg-white rounded-lg shadow-md p-8">
                      <div className="flex flex-col items-center justify-center space-y-4">
                        {/* Animated DNA helix */}
                        <div className="relative w-16 h-16">
                          <div className="absolute inset-0 flex items-center justify-center">
                            <div className="w-16 h-16 border-4 border-blue-200 border-t-blue-600 rounded-full animate-spin"></div>
                          </div>
                          <div className="absolute inset-0 flex items-center justify-center">
                            <svg className="w-8 h-8 text-blue-600" fill="currentColor" viewBox="0 0 20 20">
                              <path d="M10 3.5a1.5 1.5 0 013 0V4a1 1 0 001 1h3a1 1 0 011 1v3a1 1 0 01-1 1h-.5a1.5 1.5 0 000 3h.5a1 1 0 011 1v3a1 1 0 01-1 1h-3a1 1 0 01-1-1v-.5a1.5 1.5 0 00-3 0v.5a1 1 0 01-1 1H6a1 1 0 01-1-1v-3a1 1 0 00-1-1h-.5a1.5 1.5 0 010-3H4a1 1 0 001-1V6a1 1 0 011-1h3a1 1 0 001-1v-.5z" />
                            </svg>
                          </div>
                        </div>

                        {/* Loading text with animated dots */}
                        <div className="text-center">
                          <h3 className="text-lg font-semibold text-gray-900 mb-2">
                            Analyzing Variant
                            <span className="inline-flex ml-1">
                              <span className="animate-bounce" style={{ animationDelay: '0ms' }}>.</span>
                              <span className="animate-bounce" style={{ animationDelay: '150ms' }}>.</span>
                              <span className="animate-bounce" style={{ animationDelay: '300ms' }}>.</span>
                            </span>
                          </h3>
                          <div className="space-y-1.5 text-sm text-gray-600">
                            <p className="flex items-center justify-center gap-2">
                              <span className="inline-block w-2 h-2 bg-blue-600 rounded-full animate-pulse"></span>
                              Processing 93 molecular features
                            </p>
                            <p className="flex items-center justify-center gap-2">
                              <span className="inline-block w-2 h-2 bg-blue-600 rounded-full animate-pulse" style={{ animationDelay: '200ms' }}></span>
                              Running XGBoost prediction model
                            </p>
                            <p className="flex items-center justify-center gap-2">
                              <span className="inline-block w-2 h-2 bg-blue-600 rounded-full animate-pulse" style={{ animationDelay: '400ms' }}></span>
                              Retrieving clinical information
                            </p>
                          </div>
                        </div>

                        {/* Progress bar */}
                        <div className="w-full max-w-xs">
                          <div className="h-1.5 bg-gray-200 rounded-full overflow-hidden">
                            <div className="h-full bg-gradient-to-r from-blue-500 to-blue-600 rounded-full animate-pulse"></div>
                          </div>
                        </div>

                        <p className="text-xs text-gray-500 mt-2">
                          This may take 10-30 seconds for pathogenic variants
                        </p>
                      </div>
                    </div>
                  ) : analysisResult ? (
                    <PredictionResult result={analysisResult} />
                  ) : !error && (
                    <div className="bg-gray-50 rounded-lg border-2 border-dashed border-gray-300 p-8 text-center">
                      <svg className="mx-auto h-12 w-12 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                      </svg>
                      <h3 className="mt-2 text-sm font-medium text-gray-900">No prediction yet</h3>
                      <p className="mt-1 text-sm text-gray-500">
                        Enter variant details and click "Predict Pathogenicity" to get started.
                      </p>
                    </div>
                  )}
                </div>
              </div>
            </div>
          ) : activeTab === 'chat' ? (
            <div className="max-w-4xl mx-auto p-6">
              {ragChatData ? (
                // Pathogenic variant - show RAG results
                <div>
                  <div className="mb-6 flex items-center justify-between">
                    <div>
                      <h2 className="text-2xl font-bold text-gray-900">Diagnostic Results</h2>
                      <p className="text-gray-600 mt-1">
                        Treatment recommendations and clinical information for pathogenic variant
                      </p>
                    </div>
                    <button
                      onClick={handleBackToAnalysis}
                      className="px-4 py-2 text-sm bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 transition-colors"
                    >
                      ← New Analysis
                    </button>
                  </div>

                  <ChatInterface
                    ragChatData={ragChatData}
                    onClearRagData={handleClearRagData}
                  />
                </div>
              ) : (
                // No pathogenic variant analyzed
                <div className="text-center py-12">
                  <svg className="mx-auto h-16 w-16 text-gray-300" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                  </svg>
                  <h3 className="mt-4 text-lg font-medium text-gray-900">No Pathogenic Variant Analyzed</h3>
                  <p className="mt-2 text-gray-500 max-w-md mx-auto">
                    Analyze a variant in the "Variant Analysis" tab. If the variant is predicted as pathogenic,
                    treatment recommendations and clinical information will appear here.
                  </p>
                  <button
                    onClick={handleBackToAnalysis}
                    className="mt-6 px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
                  >
                    Go to Variant Analysis
                  </button>
                </div>
              )}
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
}

export default App;
