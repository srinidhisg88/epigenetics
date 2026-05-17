import axios from 'axios';
import type {
  VariantInput,
  PredictionResponse,
  FullAnalysisResponse,
  ExplainRequest,
  ExplainResponse,
  ChatRequest,
  ChatResponse,
  HealthResponse,
  LiteratureResponse
} from '../types';

// API base URL - configurable via environment variable
const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

// Create axios instance with default config
const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 120000, // 120 second timeout for LLM responses
});

// Health check
export const checkHealth = async (): Promise<HealthResponse> => {
  const response = await api.get<HealthResponse>('/health');
  return response.data;
};

// Get list of supported genes
export const getGenes = async (): Promise<string[]> => {
  const response = await api.get<{ genes: string[] }>('/genes');
  return response.data.genes;
};

// Get list of supported consequences
export const getConsequences = async (): Promise<string[]> => {
  const response = await api.get<{ consequences: string[] }>('/consequences');
  return response.data.consequences;
};

// Predict variant pathogenicity (simple prediction only)
export const predictVariant = async (variant: VariantInput): Promise<PredictionResponse> => {
  const response = await api.post<PredictionResponse>('/predict_variant', variant);
  return response.data;
};

// Full analysis: Prediction + RAG (if pathogenic)
export const analyzeVariant = async (variant: VariantInput): Promise<FullAnalysisResponse> => {
  const response = await api.post<FullAnalysisResponse>('/analyze_variant', variant);
  return response.data;
};

// Get explanation for a variant prediction
export const explainVariant = async (request: ExplainRequest): Promise<ExplainResponse> => {
  const response = await api.post<ExplainResponse>('/explain_variant', request);
  return response.data;
};

// Chat with the assistant
export const chat = async (request: ChatRequest): Promise<ChatResponse> => {
  const response = await api.post<ChatResponse>('/chat', request);
  return response.data;
};

// Generate PDF report
export const generatePDFReport = async (reportData: {
  variant_info: any;
  prediction: string;
  confidence: number;
  rag_response: string;
  sources: any[];
  chat_history?: any[];
}): Promise<Blob> => {
  const response = await api.post('/generate_report', reportData, {
    responseType: 'blob',
  });
  return response.data;
};

// Get recent literature for a gene
export const getLiterature = async (gene: string): Promise<LiteratureResponse> => {
  const response = await api.get<LiteratureResponse>(`/literature/${gene}`);
  return response.data;
};

// Export the api instance for custom requests
export default api;
