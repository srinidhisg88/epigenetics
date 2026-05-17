import React, { useState, useEffect } from 'react';
import { checkHealth } from '../services/api';
import type { HealthResponse } from '../types';

const Sidebar: React.FC = () => {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const fetchHealth = async () => {
      try {
        const response = await checkHealth();
        setHealth(response);
      } catch (err) {
        setHealth(null);
      } finally {
        setIsLoading(false);
      }
    };

    fetchHealth();
    // Refresh every 30 seconds
    const interval = setInterval(fetchHealth, 30000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="w-64 bg-gray-900 text-white p-4 flex flex-col h-full">
      {/* Logo/Title */}
      <div className="mb-8">
        <h1 className="text-xl font-bold flex items-center gap-2">
          <span className="text-2xl">🧬</span>
          <span>EpiGenetics</span>
        </h1>
        <p className="text-xs text-gray-400 mt-1">Epilepsy Diagnostic Assistant</p>
      </div>

      {/* Status Section */}
      <div className="mb-6">
        <h2 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-3">System Status</h2>
        {isLoading ? (
          <div className="text-sm text-gray-400">Loading...</div>
        ) : health ? (
          <div className="space-y-2">
            <StatusItem
              label="API Status"
              status={health.status === 'ok'}
              detail={health.status}
            />
            <StatusItem
              label="ML Model"
              status={health.model_loaded}
              detail={health.model_loaded ? 'Loaded' : 'Not loaded'}
            />
            <StatusItem
              label="RAG System"
              status={health.rag_loaded}
              detail={health.rag_loaded ? 'Ready' : 'Not ready'}
            />
          </div>
        ) : (
          <div className="text-sm text-red-400 flex items-center gap-2">
            <span className="w-2 h-2 bg-red-500 rounded-full"></span>
            API Offline
          </div>
        )}
      </div>

      {/* Info Section */}
      <div className="mb-6">
        <h2 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-3">About</h2>
        <div className="text-xs text-gray-400 space-y-2">
          <p>
            <strong className="text-gray-300">Model:</strong> XGBoost classifier trained on 51,060 variants
          </p>
          <p>
            <strong className="text-gray-300">Genes:</strong> 26 epilepsy-related genes
          </p>
          <p>
            <strong className="text-gray-300">Accuracy:</strong> 89.9% overall, 99.2% on high-impact variants
          </p>
        </div>
      </div>

      {/* Supported Genes */}
      <div className="mb-6 flex-1 overflow-hidden">
        <h2 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-3">Supported Genes</h2>
        <div className="flex flex-wrap gap-1 overflow-y-auto max-h-40 text-xs">
          {['SCN1A', 'SCN2A', 'SCN8A', 'SCN9A', 'KCNQ2', 'TSC1', 'TSC2', 'DEPDC5', 'NPRL3', 'MECP2', 'CDKL5', 'PCDH19'].map(gene => (
            <span key={gene} className="px-2 py-0.5 bg-gray-800 rounded text-gray-300">
              {gene}
            </span>
          ))}
          <span className="px-2 py-0.5 text-gray-500">+14 more</span>
        </div>
      </div>

      {/* Footer */}
      <div className="mt-auto pt-4 border-t border-gray-800">
        <p className="text-xs text-gray-500">
          For research use only. Not for clinical diagnosis.
        </p>
        <p className="text-xs text-gray-600 mt-1">
          v1.0.0 | Powered by Groq
        </p>
      </div>
    </div>
  );
};

interface StatusItemProps {
  label: string;
  status: boolean;
  detail: string;
}

const StatusItem: React.FC<StatusItemProps> = ({ label, status, detail }) => (
  <div className="flex items-center justify-between text-sm">
    <span className="text-gray-300">{label}</span>
    <span className={`flex items-center gap-1 ${status ? 'text-green-400' : 'text-red-400'}`}>
      <span className={`w-2 h-2 rounded-full ${status ? 'bg-green-500' : 'bg-red-500'}`}></span>
      {detail}
    </span>
  </div>
);

export default Sidebar;
