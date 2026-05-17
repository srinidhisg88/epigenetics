// Variant input for prediction
export interface VariantInput {
  gene: string;
  chromosome: string;
  position?: number;
  reference_allele: string;
  alternate_allele: string;
  consequence: string;
  variant_type: string;
  review_status: string;
  origin: string;
}

// Prediction response from API
export interface PredictionResponse {
  prediction: 'Pathogenic' | 'Benign';
  confidence: number;
  pathogenic_probability: number;
  benign_probability: number;
  variant_info: {
    gene: string;
    chromosome: string;
    reference_allele: string;
    alternate_allele: string;
    consequence: string;
    variant_type: string;
  };
}

// ACMG criterion entry
export interface ACMGCriterion {
  code: string;
  description: string;
  reason: string;
  points: number;
}

// ACMG classification result
export interface ACMGClassification {
  classification: 'Pathogenic' | 'Likely Pathogenic' | 'VUS' | 'Likely Benign' | 'Benign';
  criteria_met: ACMGCriterion[];
  criteria_not_met: ACMGCriterion[];
  score_breakdown: {
    total: number;
    pathogenic_points: number;
    benign_points: number;
    pathogenic_criteria: string[];
    benign_criteria: string[];
  };
  total_score: number;
  clinical_summary: string;
  context_for_llm: string;
  gene_mechanism: 'LOF' | 'GOF';
}

// Full analysis response (prediction + RAG for pathogenic)
export interface FullAnalysisResponse {
  prediction: 'Pathogenic' | 'Benign';
  confidence: number;
  pathogenic_probability: number;
  benign_probability: number;
  variant_info: {
    gene: string;
    chromosome: string;
    reference_allele: string;
    alternate_allele: string;
    consequence: string;
    variant_type: string;
  };
  is_pathogenic: boolean;
  rag_response: string | null;
  sources: Source[] | null;
  acmg_classification: ACMGClassification | null;
  shap_explanation: Record<string, any> | null;
  gnomad_data: Record<string, any> | null;
  contradictions: Record<string, any> | null;
  uncertainty_analysis: Record<string, any> | null;
}

// Explanation request
export interface ExplainRequest {
  gene: string;
  variant: string;
  prediction: string;
  confidence: number;
  consequence: string;
}

// Source from RAG
export interface Source {
  source: string;
  title: string;
  pmid: string | null;
  url: string | null;
  score: number;
}

// Explanation response
export interface ExplainResponse {
  explanation: string;
  sources: Source[];
}

// Chat message
export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
}

// Chat request
export interface ChatRequest {
  messages: ChatMessage[];
  variant_context?: {
    gene: string;
    variant: string;
    prediction: string;
    confidence: number;
    consequence: string;
  } | null;
}

// Chat response
export interface ChatResponse {
  response: string;
  sources?: Source[] | null;  // Sources for follow-up questions
}

// Health check response
export interface HealthResponse {
  status: string;
  model_loaded: boolean;
  rag_loaded: boolean;
  details: Record<string, any>;
}

// Literature paper
export interface LiteraturePaper {
  pmid: string;
  title: string;
  authors: string;
  journal: string;
  pub_date: string;
  abstract: string;
  summary: string;
  category: string;
  url: string;
}

// Literature response
export interface LiteratureResponse {
  gene: string;
  papers: LiteraturePaper[];
  cached: boolean;
  total_count: number;
}

// Epilepsy genes list
export const EPILEPSY_GENES = [
  // Voltage-gated sodium channels
  'SCN1A', 'SCN2A', 'SCN3A', 'SCN8A', 'SCN9A',
  // Voltage-gated potassium channels
  'KCNQ2', 'KCNQ3',
  // GABA-A receptor subunits
  'GABRA1', 'GABRG2',
  // mTOR pathway
  'TSC1', 'TSC2', 'DEPDC5', 'NPRL3',
  // Neurodevelopmental loci
  'CDKL5', 'MECP2', 'STXBP1', 'ARX', 'FOXG1',
  'PCDH19', 'SLC2A1', 'SLC6A1',
  'CHD2', 'PLCB1', 'PRRT2', 'TBC1D24', 'ALDH7A1',
] as const;

// Chromosomes
export const CHROMOSOMES = [
  '1', '2', '3', '4', '5', '6', '7', '8', '9', '10',
  '11', '12', '13', '14', '15', '16', '17', '18', '19',
  '20', '21', '22', 'X', 'Y'
] as const;

// Variant consequences
export const CONSEQUENCES = [
  'missense_variant',
  'nonsense',
  'frameshift_variant',
  'synonymous_variant',
  'splice_acceptor_variant',
  'splice_donor_variant',
  'inframe_deletion',
  'inframe_insertion',
  'start_lost',
  'stop_lost',
  'stop_gained'
] as const;

// Variant types
export const VARIANT_TYPES = [
  'single nucleotide variant',
  'deletion',
  'insertion',
  'duplication',
  'indel'
] as const;

// Review statuses
export const REVIEW_STATUSES = [
  'no assertion criteria provided',
  'criteria provided, single submitter',
  'criteria provided, multiple submitters',
  'reviewed by expert panel',
  'practice guideline'
] as const;

// Origins
export const ORIGINS = [
  'germline',
  'somatic',
  'de novo (confirmed)',
  'de novo',
  'inherited',
  'unknown'
] as const;
