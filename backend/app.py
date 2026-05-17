"""
FastAPI Backend for Epilepsy Diagnostic Assistant.

Provides endpoints for:
- Variant pathogenicity prediction (XGBoost model)
- Variant explanation generation (RAG + LLM)
- Chat interface for clinician questions
"""

import os
import sys
from pathlib import Path
from typing import List, Dict, Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
import joblib
import pandas as pd
import numpy as np
from dotenv import load_dotenv
from io import BytesIO
from datetime import datetime
import re

# Load environment variables first
load_dotenv()

# ============================================================================
# IMPORTANT: Load ML model BEFORE importing RAG to avoid FAISS/torch segfault
# ============================================================================

# Configuration
BASE_DIR = Path(__file__).parent.parent

def resolve_path(path_str: str) -> str:
    """Resolve a path, making it absolute relative to BASE_DIR if relative."""
    path = Path(path_str)
    if not path.is_absolute():
        path = BASE_DIR / path
    return str(path.resolve())


def resolve_chunk_source(source_file: str, text: str = "") -> tuple:
    """
    Given a chunk source filename, return (pmid, url) for display in the UI.
    Handles PubMed pmid_*.txt files and GeneReviews genereview_*.txt files.
    For GeneReviews, the URL is extracted from the file's own 'URL:' line.
    """
    import re as _re
    pmid = None
    url = None

    if source_file.startswith("pmid_") and source_file.endswith(".txt"):
        pmid = source_file[5:-4]
        url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"

    elif source_file.startswith("genereview_") and source_file.endswith(".txt"):
        # PMID is embedded in the GeneReviews file content
        pmid_m = _re.search(r'PMID:\s*(\d+)', text)
        if pmid_m:
            pmid = pmid_m.group(1)
            url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
        else:
            gene = source_file[len("genereview_"):-4]
            url = f"https://www.ncbi.nlm.nih.gov/books/NBK1116/?term={gene}"

    elif source_file.startswith("https://pubmed.ncbi.nlm.nih.gov/"):
        # Source stored as full URL (from older fetch process)
        url = source_file.rstrip("/")
        pmid_m = _re.search(r'/(\d+)/?$', url)
        if pmid_m:
            pmid = pmid_m.group(1)

    return pmid, url

MODEL_PATH = resolve_path(os.getenv("MODEL_PATH", "models/epilepsy_classifier_no_phenotype.pkl"))
GENE_STATS_PATH = BASE_DIR / "data" / "processed" / "gene_statistics.json"
GENE_DISEASE_CSV = BASE_DIR / "data" / "knowledge_base" / "gene_disease_mapping.csv"

# ── Epilepsy keyword filter ───────────────────────────────────────────────────
_EPILEPSY_KEYWORDS = {
    "epilepsy", "epileptic", "seizure", "encephalopathy",
    "dravet", "spasm", "gefs", "myoclonic", "lennox", "rett",
    "tuberous", "glut1", "kcnq", "stxbp1", "pcdh19", "cdkl5",
    "febrile", "neonatal convulsion", "infantile convulsion",
}

def _is_epilepsy_disease(disease: str) -> bool:
    dl = disease.lower()
    return any(kw in dl for kw in _EPILEPSY_KEYWORDS)


def load_gene_disease_map(csv_path: Path) -> dict:
    """
    Parse gene_disease_mapping.csv and return {gene: [unique epilepsy diseases]}.
    Filters out non-epilepsy phenotypes and deduplicates per gene.
    """
    import csv as _csv
    gene_map: dict = {}
    if not csv_path.exists():
        return gene_map
    try:
        with open(csv_path, newline="", encoding="utf-8") as f:
            reader = _csv.DictReader(f)
            for row in reader:
                gene = row.get("GeneSymbol", "").strip()
                phenotypes = row.get("PhenotypeList", "")
                if not gene:
                    continue
                # Split on pipe or semicolon (CSV uses both)
                parts = re.split(r'[|;]', phenotypes)
                for p in parts:
                    p = p.strip()
                    if p and _is_epilepsy_disease(p) and p.lower() not in ("not provided", "inborn genetic diseases"):
                        gene_map.setdefault(gene, [])
                        if p not in gene_map[gene]:
                            gene_map[gene].append(p)
        print(f"[Startup] Gene-disease map loaded: {len(gene_map)} genes")
    except Exception as e:
        print(f"[Startup] Warning: could not load gene_disease_mapping.csv: {e}")
    return gene_map


GENE_DISEASE_MAP: dict = load_gene_disease_map(GENE_DISEASE_CSV)

# Load ML model at module level BEFORE RAG imports
ml_model = None
ml_feature_names = None
gene_stats = None

print(f"[Startup] Loading ML model from {MODEL_PATH}...")
if Path(MODEL_PATH).exists():
    try:
        _model_data = joblib.load(MODEL_PATH)
        ml_model = _model_data['model']
        ml_feature_names = _model_data.get('feature_names', [])
        print(f"[Startup] ML model loaded successfully with {len(ml_feature_names)} features")
    except Exception as e:
        print(f"[Startup] Error loading ML model: {e}")
else:
    print(f"[Startup] ML model file not found: {MODEL_PATH}")

# NOW import RAG modules (after ML model is loaded)
sys.path.insert(0, str(BASE_DIR))
from rag.retriever import RAGRetriever
from rag.generator import RAGGenerator
from rag.multi_source_retriever import MultiSourceRetriever
from backend.literature_fetcher import LiteratureFetcher
from backend.clinvar_fetcher import ClinVarFetcher
from backend.pharmgkb_fetcher import PharmGKBFetcher
from backend.gnomad_fetcher import GnomADFetcher, get_gnomad_fetcher
from backend.shap_explainer import SHAPExplainer, get_shap_explainer
from backend.confidence_resolver import (
    ConfidenceResolver, ContradictionDetector,
    get_confidence_resolver, get_contradiction_detector
)
from backend.acmg_classifier import ACMGClassifier, get_acmg_classifier

# RAG components (loaded in lifespan)
retriever: Optional[RAGRetriever] = None
generator: Optional[RAGGenerator] = None
multi_source_retriever: Optional[MultiSourceRetriever] = None
literature_fetcher: Optional[LiteratureFetcher] = None
clinvar_fetcher: Optional[ClinVarFetcher] = None
pharmgkb_fetcher: Optional[PharmGKBFetcher] = None
gnomad_fetcher: Optional[GnomADFetcher] = None
shap_explainer: Optional[SHAPExplainer] = None
confidence_resolver: Optional[ConfidenceResolver] = None
contradiction_detector: Optional[ContradictionDetector] = None
acmg_classifier: Optional[ACMGClassifier] = None


# ============================================================================
# Pydantic Models for Request/Response
# ============================================================================

class VariantInput(BaseModel):
    """Input model for variant prediction."""
    gene: str = Field(..., description="Gene symbol (e.g., SCN1A)")
    chromosome: str = Field(..., description="Chromosome (e.g., 1, 2, X)")
    position: Optional[int] = Field(None, description="Genomic position")
    reference_allele: str = Field(..., description="Reference allele")
    alternate_allele: str = Field(..., description="Alternate allele")
    consequence: str = Field(..., description="Variant consequence (e.g., missense, nonsense)")
    variant_type: str = Field(default="single nucleotide variant", description="Variant type")
    review_status: str = Field(default="no assertion criteria provided", description="Review status")
    origin: str = Field(default="germline", description="Variant origin")


class PredictionResponse(BaseModel):
    """Response model for variant prediction."""
    prediction: str = Field(..., description="Pathogenic or Benign")
    confidence: float = Field(..., description="Confidence percentage")
    pathogenic_probability: float
    benign_probability: float
    variant_info: Dict


class FullAnalysisResponse(BaseModel):
    """Response model for full analysis (prediction + RAG for pathogenic)."""
    prediction: str
    confidence: float
    pathogenic_probability: float
    benign_probability: float
    variant_info: Dict
    # RAG fields (only populated if pathogenic)
    rag_response: Optional[str] = None
    sources: Optional[List[Dict]] = None
    is_pathogenic: bool
    # New fields for novelty features
    shap_explanation: Optional[Dict] = None
    gnomad_data: Optional[Dict] = None
    contradictions: Optional[Dict] = None
    uncertainty_analysis: Optional[Dict] = None
    acmg_classification: Optional[Dict] = None


class ExplainRequest(BaseModel):
    """Request model for variant explanation."""
    gene: str
    variant: str
    prediction: str
    confidence: float
    consequence: str


class ExplainResponse(BaseModel):
    """Response model for variant explanation."""
    explanation: str
    sources: List[Dict]


class ChatMessage(BaseModel):
    """Single chat message."""
    role: str = Field(..., description="'user' or 'assistant'")
    content: str


class ChatRequest(BaseModel):
    """Request model for chat."""
    messages: List[ChatMessage]
    variant_context: Optional[Dict] = None


class ChatResponse(BaseModel):
    """Response model for chat."""
    response: str
    sources: Optional[List[Dict]] = None  # Include sources for follow-up questions


class PDFReportRequest(BaseModel):
    """Request model for PDF report generation."""
    variant_info: Dict = Field(..., description="Variant information")
    prediction: str
    confidence: float
    rag_response: str = Field(..., description="LLM-generated clinical information")
    sources: List[Dict] = Field(default_factory=list, description="Sources from RAG")
    chat_history: Optional[List[Dict]] = Field(default_factory=list, description="Follow-up Q&A")


class HealthResponse(BaseModel):
    """Response model for health check."""
    status: str
    model_loaded: bool
    rag_loaded: bool
    details: Dict


class LiteraturePaper(BaseModel):
    """Literature paper model."""
    pmid: str
    title: str
    authors: str
    journal: str
    pub_date: str
    abstract: str
    summary: str
    category: str
    url: str


class LiteratureResponse(BaseModel):
    """Response model for literature endpoint."""
    gene: str
    papers: List[LiteraturePaper]
    cached: bool
    total_count: int


# All 26 epilepsy genes
EPILEPSY_GENES = [
    # Voltage-gated sodium channels
    'SCN1A', 'SCN2A', 'SCN3A', 'SCN8A', 'SCN9A',
    # Voltage-gated potassium channels
    'KCNQ2', 'KCNQ3',
    # GABA-A receptor subunits
    'GABRA1', 'GABRG2',
    # mTOR pathway
    'TSC1', 'TSC2', 'DEPDC5', 'NPRL3',
    # Neurodevelopmental loci
    'CDKL5', 'MECP2', 'STXBP1', 'ARX', 'FOXG1',
    'PCDH19', 'SLC2A1', 'SLC6A1',
    'CHD2', 'PLCB1', 'PRRT2', 'TBC1D24', 'ALDH7A1',
]

CHROMOSOMES = ['1', '2', '3', '4', '5', '6', '7', '8', '9', '10',
               '11', '12', '13', '14', '15', '16', '17', '18', '19',
               '20', '21', '22', 'X', 'Y']

CONSEQUENCES = [
    'missense_variant', 'nonsense', 'frameshift_variant', 'synonymous_variant',
    'splice_acceptor_variant', 'splice_donor_variant', 'inframe_deletion',
    'inframe_insertion', 'start_lost', 'stop_lost', 'stop_gained'
]


# ============================================================================
# Lifespan Management
# ============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load RAG components on startup, cleanup on shutdown."""
    global gene_stats, retriever, generator, literature_fetcher
    global multi_source_retriever, clinvar_fetcher, pharmgkb_fetcher
    global gnomad_fetcher, shap_explainer, confidence_resolver, contradiction_detector
    global acmg_classifier

    print("=" * 60)
    print("Starting Epilepsy Diagnostic Assistant API")
    print("=" * 60)
    print(f"ML Model: {'loaded' if ml_model else 'not loaded'}")
    print(f"ML Features: {len(ml_feature_names) if ml_feature_names else 0}")

    # Load gene statistics
    try:
        if GENE_STATS_PATH.exists():
            import json
            with open(GENE_STATS_PATH, 'r') as f:
                gene_stats = json.load(f)
            print(f"Gene statistics loaded")
    except Exception as e:
        print(f"Warning: Could not load gene statistics: {e}")

    # Initialize RAG components
    try:
        print("\nInitializing RAG retriever...")
        retriever = RAGRetriever()
        if retriever.load():
            print("  RAG retriever loaded successfully")
        else:
            print("  Warning: RAG retriever not fully loaded")
    except Exception as e:
        print(f"  Warning: Could not initialize RAG retriever: {e}")
        retriever = None

    try:
        print("\nInitializing RAG generator...")
        generator = RAGGenerator()
        print("  RAG generator initialized")
    except Exception as e:
        print(f"  Warning: Could not initialize RAG generator: {e}")
        generator = None

    # Initialize ClinVar fetcher
    try:
        print("\nInitializing ClinVar Fetcher...")
        clinvar_fetcher = ClinVarFetcher()
        print("  ClinVar fetcher initialized")
    except Exception as e:
        print(f"  Warning: Could not initialize ClinVar Fetcher: {e}")
        clinvar_fetcher = None

    # Initialize PharmGKB fetcher
    try:
        print("\nInitializing PharmGKB Fetcher...")
        pharmgkb_fetcher = PharmGKBFetcher()
        print("  PharmGKB fetcher initialized")
    except Exception as e:
        print(f"  Warning: Could not initialize PharmGKB Fetcher: {e}")
        pharmgkb_fetcher = None

    # Initialize gnomAD Fetcher
    try:
        print("\nInitializing gnomAD Fetcher...")
        gnomad_fetcher = get_gnomad_fetcher()
        print("  gnomAD fetcher initialized")
    except Exception as e:
        print(f"  Warning: Could not initialize gnomAD Fetcher: {e}")
        gnomad_fetcher = None

    # Initialize Multi-Source Retriever (now includes gnomAD)
    try:
        print("\nInitializing Multi-Source Retriever...")
        multi_source_retriever = MultiSourceRetriever(
            pubmed_retriever=retriever,
            clinvar_fetcher=clinvar_fetcher,
            pharmgkb_fetcher=pharmgkb_fetcher,
            gnomad_fetcher=gnomad_fetcher
        )
        print("  Multi-Source retriever initialized")
    except Exception as e:
        print(f"  Warning: Could not initialize Multi-Source Retriever: {e}")
        multi_source_retriever = None

    # Initialize SHAP Explainer
    if ml_model and ml_feature_names:
        try:
            print("\nInitializing SHAP Explainer...")
            shap_explainer = get_shap_explainer(ml_model, ml_feature_names)
            print("  SHAP explainer initialized")
        except Exception as e:
            print(f"  Warning: Could not initialize SHAP Explainer: {e}")
            shap_explainer = None

    # Initialize Confidence Resolver and Contradiction Detector
    try:
        confidence_resolver = get_confidence_resolver()
        contradiction_detector = get_contradiction_detector()
        print("  Confidence resolver and contradiction detector initialized")
    except Exception as e:
        print(f"  Warning: Could not initialize confidence/contradiction modules: {e}")
        confidence_resolver = None
        contradiction_detector = None

    # Initialize ACMG Classifier
    try:
        acmg_classifier = get_acmg_classifier()
        print("  ACMG classifier initialized")
    except Exception as e:
        print(f"  Warning: Could not initialize ACMG classifier: {e}")
        acmg_classifier = None

    # Initialize literature fetcher
    try:
        print("\nInitializing Literature Fetcher...")
        literature_fetcher = LiteratureFetcher(update_rag=True)
        print("  Literature fetcher initialized")
    except Exception as e:
        print(f"  Warning: Could not initialize Literature Fetcher: {e}")
        literature_fetcher = None

    print("\n" + "=" * 60)
    print("API startup complete")
    print("=" * 60 + "\n")

    yield

    # Cleanup
    print("Shutting down API...")


# ============================================================================
# FastAPI Application
# ============================================================================

app = FastAPI(
    title="Epilepsy Diagnostic Assistant API",
    description="ML-based variant pathogenicity prediction with RAG-powered explanations",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware for React frontend
# Allow all origins for development (set CORS_ALLOW_ALL=false in production)
allow_all_cors = os.getenv("CORS_ALLOW_ALL", "true").lower() == "true"

if allow_all_cors:
    # Development mode - allow all origins
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,  # Must be False when allow_origins is ["*"]
        allow_methods=["*"],
        allow_headers=["*"],
    )
else:
    # Production mode - specific origins only
    allowed_origins = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]

    # Add custom origins from environment variable if specified
    custom_origins = os.getenv("CORS_ORIGINS", "").split(",")
    for origin in custom_origins:
        if origin.strip():
            allowed_origins.append(origin.strip())

    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


# ============================================================================
# Feature Engineering (simplified for API)
# ============================================================================

def engineer_features(variant: VariantInput) -> pd.DataFrame:
    """
    Engineer the 93 features expected by epilepsy_classifier_no_phenotype.pkl.

    All features are derived deterministically from the 7 clinical inputs:
    gene, chromosome, reference_allele, alternate_allele, consequence,
    variant_type, review_status, origin. No new input fields are needed.
    """
    features = {}
    gene_upper = variant.gene.upper()
    vt_lower = variant.variant_type.lower()
    consequence_lower = variant.consequence.lower()
    review_lower = variant.review_status.lower()

    # ---- Gene statistics (from training data) ----
    if gene_stats and 'gene_pathogenicity_rate' in gene_stats:
        features['gene_pathogenicity_rate'] = gene_stats['gene_pathogenicity_rate'].get(gene_upper, 0.5)
    else:
        features['gene_pathogenicity_rate'] = 0.5

    if gene_stats and 'gene_sample_count' in gene_stats:
        features['gene_sample_count'] = gene_stats['gene_sample_count'].get(gene_upper, 500)
    else:
        features['gene_sample_count'] = 500

    # ---- Gene family flags (deterministic from gene name) ----
    SODIUM_CHANNEL_GENES = {'SCN1A', 'SCN2A', 'SCN3A', 'SCN8A', 'SCN9A'}
    GABA_RECEPTOR_GENES = {'GABRA1', 'GABRG2'}
    ION_CHANNEL_GENES = {'SCN1A', 'SCN2A', 'SCN3A', 'SCN8A', 'SCN9A', 'KCNQ2', 'KCNQ3'}
    TSC_COMPLEX_GENES = {'TSC1', 'TSC2'}

    features['is_sodium_channel'] = 1 if gene_upper in SODIUM_CHANNEL_GENES else 0
    features['is_gaba_receptor'] = 1 if gene_upper in GABA_RECEPTOR_GENES else 0
    features['is_ion_channel'] = 1 if gene_upper in ION_CHANNEL_GENES else 0
    features['is_tsc_complex'] = 1 if gene_upper in TSC_COMPLEX_GENES else 0

    # ---- Gene one-hot encoding (26 genes) ----
    for gene in EPILEPSY_GENES:
        features[f'gene_{gene}'] = 1 if gene_upper == gene else 0

    # ---- Allele-based variant type flags ----
    ref_len = len(variant.reference_allele)
    alt_len = len(variant.alternate_allele)

    features['is_snp'] = 1 if ref_len == 1 and alt_len == 1 else 0
    features['is_deletion'] = 1 if ref_len > alt_len else 0
    features['is_insertion'] = 1 if ref_len < alt_len else 0
    features['is_duplication'] = 1 if 'dup' in vt_lower or 'duplication' in vt_lower else 0
    features['is_indel'] = 1 if features['is_deletion'] or features['is_insertion'] else 0
    features['is_single_nucleotide'] = features['is_snp']

    # ---- Variant type one-hot (Title-case keys as in training data) ----
    # Exact keys the model expects: type_Deletion, type_Duplication, type_Indel,
    # type_Insertion, type_Inversion, type_Microsatellite, type_Translocation,
    # type_Variation, type_copy number gain, type_copy number loss,
    # type_protein only, type_single nucleotide variant
    type_map = {
        'type_Deletion': 'deletion',
        'type_Duplication': 'duplication',
        'type_Indel': 'indel',
        'type_Insertion': 'insertion',
        'type_Inversion': 'inversion',
        'type_Microsatellite': 'microsatellite',
        'type_Translocation': 'translocation',
        'type_Variation': 'variation',
        'type_copy number gain': 'copy number gain',
        'type_copy number loss': 'copy number loss',
        'type_protein only': 'protein only',
        'type_single nucleotide variant': 'single nucleotide variant',
    }
    for feat_key, match_str in type_map.items():
        features[feat_key] = 1 if match_str in vt_lower else 0

    # ---- Consequence flags ----
    features['is_frameshift'] = 1 if 'frameshift' in consequence_lower else 0
    features['is_nonsense'] = 1 if 'nonsense' in consequence_lower or 'stop_gained' in consequence_lower else 0
    features['is_missense'] = 1 if 'missense' in consequence_lower else 0
    features['is_splice'] = 1 if 'splice' in consequence_lower else 0
    features['is_synonymous'] = 1 if 'synonymous' in consequence_lower else 0
    features['is_inframe'] = 1 if 'inframe' in consequence_lower else 0
    features['is_start_loss'] = 1 if 'start_lost' in consequence_lower else 0
    features['is_stop_loss'] = 1 if 'stop_lost' in consequence_lower else 0

    features['severe_consequence_count'] = sum([
        features['is_frameshift'],
        features['is_nonsense'],
        features['is_splice'],
        features['is_start_loss']
    ])

    # ---- Genomic position (optional field) ----
    features['position'] = variant.position if variant.position is not None else 0
    features['position_in_gene'] = 0  # unknown without transcript annotation
    features['is_early_in_gene'] = 0
    features['is_late_in_gene'] = 0

    # ---- Chromosome one-hot (only chromosomes present in training data) ----
    # Model has: chr_1, chr_2, chr_3, chr_4, chr_5, chr_8, chr_9, chr_12,
    #            chr_14, chr_15, chr_16, chr_20, chr_22, chr_X, chr_na
    MODEL_CHROMOSOMES = ['1', '2', '3', '4', '5', '8', '9', '12',
                         '14', '15', '16', '20', '22', 'X', 'na']
    chrom_val = variant.chromosome.strip()
    for chrom in MODEL_CHROMOSOMES:
        features[f'chr_{chrom}'] = 1 if chrom_val == chrom else 0

    # ---- Review status features ----
    features['review_score'] = 0
    if 'practice guideline' in review_lower:
        features['review_score'] = 4
    elif 'expert panel' in review_lower:
        features['review_score'] = 3
    elif 'multiple submitters' in review_lower:
        features['review_score'] = 2
    elif 'criteria provided' in review_lower:
        features['review_score'] = 1

    features['has_expert_review'] = 1 if features['review_score'] >= 3 else 0
    features['has_multiple_submitters'] = 1 if 'multiple' in review_lower else 0
    features['has_criteria'] = 1 if 'criteria provided' in review_lower else 0

    # num_submitters proxy: derive from review_score (matches training data distribution)
    score_to_submitters = {0: 1, 1: 1, 2: 5, 3: 15, 4: 30}
    features['num_submitters'] = score_to_submitters[features['review_score']]
    features['log_num_submitters'] = float(np.log1p(features['num_submitters']))

    # ---- Allele length features (correct names: ref_length, alt_length) ----
    features['ref_length'] = ref_len
    features['alt_length'] = alt_len
    features['allele_length_diff'] = abs(ref_len - alt_len)

    # ---- SNP transition/transversion ----
    if features['is_snp']:
        ref = variant.reference_allele.upper()
        alt = variant.alternate_allele.upper()
        transitions = {('A', 'G'), ('G', 'A'), ('C', 'T'), ('T', 'C')}
        features['is_transition'] = 1 if (ref, alt) in transitions else 0
        features['is_transversion'] = 1 - features['is_transition']
    else:
        features['is_transition'] = 0
        features['is_transversion'] = 0

    # ---- Origin features ----
    features['is_germline'] = 1 if 'germline' in variant.origin.lower() else 0
    features['is_de_novo'] = 1 if 'de novo' in variant.origin.lower() else 0

    # ---- Assembly (assume GRCh38 for new clinical submissions) ----
    features['is_grch38'] = 1
    features['is_grch37'] = 0

    # ---- Build DataFrame in model's expected feature order ----
    df = pd.DataFrame([features])

    if ml_feature_names:
        for col in ml_feature_names:
            if col not in df.columns:
                df[col] = 0
        df = df[ml_feature_names]

    return df


# ============================================================================
# API Endpoints
# ============================================================================

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Check API health and component status."""
    return HealthResponse(
        status="ok",
        model_loaded=ml_model is not None,
        rag_loaded=retriever is not None and retriever.is_loaded,
        details={
            "ml_model": "loaded" if ml_model else "not loaded",
            "ml_features": len(ml_feature_names) if ml_feature_names else 0,
            "rag_retriever": retriever.get_stats() if retriever else {"loaded": False},
            "rag_generator": "initialized" if generator else "not initialized"
        }
    )


@app.get("/genes")
async def get_genes():
    """Get list of supported epilepsy genes."""
    return {"genes": EPILEPSY_GENES}


@app.get("/consequences")
async def get_consequences():
    """Get list of supported variant consequences."""
    return {"consequences": CONSEQUENCES}


@app.post("/predict_variant", response_model=PredictionResponse)
async def predict_variant(variant: VariantInput):
    """
    Predict pathogenicity of a genetic variant.

    Uses the trained XGBoost model to classify the variant as
    Pathogenic or Benign with a confidence score.
    """
    if ml_model is None:
        raise HTTPException(status_code=503, detail="ML model not loaded")

    # Validate gene
    if variant.gene.upper() not in EPILEPSY_GENES:
        raise HTTPException(
            status_code=400,
            detail=f"Gene '{variant.gene}' not supported. Supported genes: {EPILEPSY_GENES}"
        )

    try:
        # Engineer features
        features_df = engineer_features(variant)

        # Predict
        prediction_proba = ml_model.predict_proba(features_df)[0]
        prediction_class = ml_model.predict(features_df)[0]

        # Get probabilities
        pathogenic_prob = float(prediction_proba[1])
        benign_prob = float(prediction_proba[0])

        # Determine prediction label and confidence
        if prediction_class == 1:
            prediction_label = "Pathogenic"
            confidence = pathogenic_prob * 100
        else:
            prediction_label = "Benign"
            confidence = benign_prob * 100

        return PredictionResponse(
            prediction=prediction_label,
            confidence=round(confidence, 2),
            pathogenic_probability=round(pathogenic_prob, 4),
            benign_probability=round(benign_prob, 4),
            variant_info={
                "gene": variant.gene.upper(),
                "chromosome": variant.chromosome,
                "reference_allele": variant.reference_allele,
                "alternate_allele": variant.alternate_allele,
                "consequence": variant.consequence,
                "variant_type": variant.variant_type
            }
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Prediction error: {str(e)}")


@app.post("/analyze_variant", response_model=FullAnalysisResponse)
async def analyze_variant(variant: VariantInput):
    """
    Full variant analysis: ML prediction + SHAP + gnomAD + RAG + contradiction detection.

    Workflow:
    1. Predicts pathogenicity using XGBoost ML model
    2. Computes SHAP explainability for every prediction
    3. Queries gnomAD for population allele frequency
    4. If PATHOGENIC or UNCERTAIN (0.3-0.7): triggers multi-source RAG
    5. Detects contradictions between ML, ClinVar, gnomAD
    6. If uncertain: builds confidence-resolution context for LLM
    """
    if ml_model is None:
        raise HTTPException(status_code=503, detail="ML model not loaded")

    # Validate gene
    if variant.gene.upper() not in EPILEPSY_GENES:
        raise HTTPException(
            status_code=400,
            detail=f"Gene '{variant.gene}' not supported. Supported genes: {EPILEPSY_GENES}"
        )

    try:
        # Engineer features
        features_df = engineer_features(variant)

        # Predict
        prediction_proba = ml_model.predict_proba(features_df)[0]
        prediction_class = ml_model.predict(features_df)[0]

        # Get probabilities
        pathogenic_prob = float(prediction_proba[1])
        benign_prob = float(prediction_proba[0])

        # Determine prediction label and confidence
        is_pathogenic = prediction_class == 1
        if is_pathogenic:
            prediction_label = "Pathogenic"
            confidence = pathogenic_prob * 100
        else:
            prediction_label = "Benign"
            confidence = benign_prob * 100

        variant_info = {
            "gene": variant.gene.upper(),
            "chromosome": variant.chromosome,
            "reference_allele": variant.reference_allele,
            "alternate_allele": variant.alternate_allele,
            "consequence": variant.consequence,
            "variant_type": variant.variant_type
        }

        # Initialize response fields
        rag_response = None
        sources = None
        shap_result = None
        gnomad_result = None
        contradiction_result = None
        uncertainty_result = None
        acmg_result = None

        # --- SHAP Explanation (always, for every prediction) ---
        if shap_explainer:
            try:
                print("\nComputing SHAP explanation...")
                shap_result = shap_explainer.explain(features_df, top_n=5)
                print(f"  Top SHAP contributor: {shap_result['top_contributors'][0]['description']}")
            except Exception as shap_err:
                print(f"SHAP error (non-fatal): {shap_err}")
                shap_result = None

        # --- gnomAD Population Frequency ---
        if gnomad_fetcher and variant.position:
            try:
                print(f"\nQuerying gnomAD for {variant.chromosome}:{variant.position}...")
                gnomad_result = gnomad_fetcher.get_variant_frequency(
                    chromosome=variant.chromosome,
                    position=variant.position,
                    reference=variant.reference_allele,
                    alternate=variant.alternate_allele,
                    genome_version="GRCh38"
                )
                print(f"  gnomAD: found={gnomad_result.get('found')}, AF={gnomad_result.get('allele_frequency')}")
            except Exception as gnomad_err:
                print(f"gnomAD error (non-fatal): {gnomad_err}")
                gnomad_result = None

        # --- ACMG/AMP Classification (runs after SHAP + gnomAD are available) ---
        if acmg_classifier:
            try:
                print("\nRunning ACMG/AMP classification...")
                acmg_result = acmg_classifier.classify(
                    gene=variant.gene.upper(),
                    consequence=variant.consequence,
                    origin=variant.origin,
                    gnomad_data=gnomad_result,
                    clinvar_data=None,  # will be enriched after RAG; pre-run with available data
                    shap_data=shap_result,
                    variant_type=variant.variant_type,
                    reference_allele=variant.reference_allele,
                    alternate_allele=variant.alternate_allele,
                )
                print(f"  ACMG: {acmg_result['classification']} "
                      f"(score={acmg_result['total_score']:+d}, "
                      f"criteria={[c['code'] for c in acmg_result['criteria_met']]})")
            except Exception as acmg_err:
                print(f"ACMG error (non-fatal): {acmg_err}")
                acmg_result = None

        # --- Confidence-Aware RAG: determine if ML is uncertain ---
        is_uncertain = False
        if confidence_resolver:
            is_uncertain = confidence_resolver.is_uncertain(pathogenic_prob)
            if is_uncertain:
                print(f"\n⚠️ ML prediction is UNCERTAIN (pathogenic_prob={pathogenic_prob:.3f})")

        # Trigger RAG if PATHOGENIC or if ML is UNCERTAIN (confidence-aware RAG)
        should_run_rag = (is_pathogenic or is_uncertain) and generator

        multi_results = None
        if should_run_rag:
            try:
                # Use multi-source retriever if available, fallback to single source
                if multi_source_retriever:
                    # Retrieve from all sources (now including gnomAD)
                    print("\nUsing Multi-Source Retriever...")
                    multi_results = multi_source_retriever.retrieve_comprehensive(
                        gene=variant.gene.upper(),
                        variant=None,
                        consequence=variant.consequence,
                        include_clinvar=True,
                        include_pharmgkb=True,
                        include_pubmed=True,
                        include_gnomad=True,
                        chromosome=variant.chromosome,
                        position=variant.position,
                        reference_allele=variant.reference_allele,
                        alternate_allele=variant.alternate_allele,
                        genome_version="GRCh38",
                        top_k=7
                    )

                    # Format context for LLM
                    context = multi_source_retriever.format_context_for_llm(multi_results, max_length=8000)

                    print(f"Sources used: {multi_source_retriever.get_sources_summary(multi_results)}")

                elif retriever and retriever.is_loaded:
                    # Fallback to PubMed-only retrieval
                    print("\nUsing PubMed-only retrieval...")
                    chunks = retriever.retrieve_for_variant(
                        gene=variant.gene.upper(),
                        variant_type=variant.variant_type,
                        consequence=variant.consequence,
                        top_k=7
                    )
                    context = retriever.format_context(chunks)
                else:
                    print("\nNo retriever available, skipping RAG")
                    context = ""

                # --- Append SHAP context to LLM prompt ---
                if shap_result and shap_result.get("context_for_llm"):
                    context += "\n\n" + shap_result["context_for_llm"]

                # --- Contradiction Detection ---
                clinvar_data = None
                if multi_results and 'clinvar' in multi_results.get('sources', {}):
                    clinvar_data = multi_results['sources']['clinvar']

                # Re-run ACMG now that ClinVar data is available
                if acmg_classifier and clinvar_data:
                    try:
                        acmg_result = acmg_classifier.classify(
                            gene=variant.gene.upper(),
                            consequence=variant.consequence,
                            origin=variant.origin,
                            gnomad_data=gnomad_result,
                            clinvar_data=clinvar_data,
                            shap_data=shap_result,
                            variant_type=variant.variant_type,
                            reference_allele=variant.reference_allele,
                            alternate_allele=variant.alternate_allele,
                        )
                        print(f"  ACMG (with ClinVar): {acmg_result['classification']} "
                              f"(score={acmg_result['total_score']:+d})")
                        context += "\n\n" + acmg_result["context_for_llm"]
                    except Exception as acmg_err:
                        print(f"ACMG re-run error (non-fatal): {acmg_err}")
                elif acmg_result:
                    # No ClinVar but ACMG ran earlier — still inject context
                    context += "\n\n" + acmg_result["context_for_llm"]

                if contradiction_detector:
                    try:
                        contradiction_result = contradiction_detector.detect_contradictions(
                            ml_prediction=prediction_label,
                            ml_confidence=confidence,
                            pathogenic_prob=pathogenic_prob,
                            clinvar_data=clinvar_data,
                            gnomad_data=gnomad_result,
                            gene=variant.gene.upper(),
                            consequence=variant.consequence,
                        )
                        if contradiction_result.get("has_contradictions"):
                            print(f"  ⚠️ {contradiction_result['count']} contradiction(s) detected "
                                  f"(severity: {contradiction_result['severity']})")
                            # Append contradiction warnings to LLM context
                            context += "\n\n" + contradiction_result["context_for_llm"]
                    except Exception as contra_err:
                        print(f"Contradiction detection error (non-fatal): {contra_err}")

                # --- Uncertainty Analysis (confidence-aware RAG) ---
                if is_uncertain and confidence_resolver:
                    try:
                        uncertainty_result = confidence_resolver.build_uncertainty_context(
                            pathogenic_prob=pathogenic_prob,
                            gene=variant.gene.upper(),
                            consequence=variant.consequence,
                            gnomad_data=gnomad_result,
                            clinvar_data=clinvar_data,
                            shap_data=shap_result,
                        )
                        # Append uncertainty prompt to LLM context
                        context += uncertainty_result.get("additional_prompt", "")
                        print(f"  Uncertainty suggested: {uncertainty_result.get('suggested_classification')}")
                    except Exception as unc_err:
                        print(f"Uncertainty analysis error (non-fatal): {unc_err}")

                # Generate explanation with treatment focus
                variant_detail = {
                    "gene": variant.gene.upper(),
                    "variant": f"{variant.reference_allele}>{variant.alternate_allele}",
                    "prediction": prediction_label,
                    "confidence": round(confidence, 2),
                    "consequence": variant.consequence
                }

                if context:
                    known_diseases = GENE_DISEASE_MAP.get(variant.gene.upper(), [])
                    rag_response = generator.generate_explanation(
                        variant_detail, context, known_diseases=known_diseases or None
                    )
                else:
                    rag_response = "Retrieval system unavailable. Please consult clinical guidelines."

                # Format sources
                sources = []

                # Add ClinVar sources if available
                if multi_results and 'clinvar' in multi_results.get('sources', {}):
                    for cv_variant in multi_results['sources']['clinvar']['variants'][:3]:
                        sources.append({
                            "source": "ClinVar",
                            "title": f"{cv_variant['variant_name']} - {cv_variant['clinical_significance']}",
                            "url": cv_variant['url'],
                            "score": 1.0,
                            "type": "clinvar"
                        })

                # Add PharmGKB sources if available
                if multi_results and 'pharmgkb' in multi_results.get('sources', {}):
                    gene_upper = variant.gene.upper()
                    pharmgkb_url = f"https://www.pharmgkb.org/search?query={gene_upper}"
                    sources.append({
                        "source": "PharmGKB",
                        "title": f"Drug-Gene Interactions for {gene_upper}",
                        "url": pharmgkb_url,
                        "score": 0.95,
                        "type": "pharmgkb"
                    })

                # Add gnomAD source if available
                if gnomad_result and gnomad_result.get("variant_id"):
                    sources.append({
                        "source": "gnomAD",
                        "title": f"Population Frequency - {gnomad_result['variant_id']}",
                        "url": f"https://gnomad.broadinstitute.org/variant/{gnomad_result['variant_id']}?dataset={gnomad_result.get('dataset', 'gnomad_r4')}",
                        "score": 0.90,
                        "type": "gnomad"
                    })

                # Add PubMed sources
                if multi_results and 'pubmed' in multi_results.get('sources', {}):
                    chunks = multi_results['sources']['pubmed']['chunks']
                elif retriever:
                    chunks = retriever.retrieve_for_variant(
                        gene=variant.gene.upper(),
                        variant_type=variant.variant_type,
                        consequence=variant.consequence,
                        top_k=3
                    )
                else:
                    chunks = []

                for chunk in chunks:
                    source_file = chunk["source"]
                    title = chunk.get("title", "")
                    pmid, url = resolve_chunk_source(source_file, chunk.get("text", ""))

                    sources.append({
                        "source": source_file,
                        "title": title,
                        "pmid": pmid,
                        "url": url,
                        "score": round(chunk["score"], 4)
                    })

            except Exception as rag_error:
                print(f"RAG error (non-fatal): {rag_error}")
                rag_response = f"Unable to retrieve additional information: {str(rag_error)}"

        return FullAnalysisResponse(
            prediction=prediction_label,
            confidence=round(confidence, 2),
            pathogenic_probability=round(pathogenic_prob, 4),
            benign_probability=round(benign_prob, 4),
            variant_info=variant_info,
            is_pathogenic=is_pathogenic,
            rag_response=rag_response,
            sources=sources,
            shap_explanation=shap_result,
            gnomad_data=gnomad_result,
            contradictions=contradiction_result,
            uncertainty_analysis=uncertainty_result,
            acmg_classification=acmg_result,
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis error: {str(e)}")


@app.post("/explain_variant", response_model=ExplainResponse)
async def explain_variant(request: ExplainRequest):
    """
    Generate an explanation for a variant prediction.

    Uses RAG to retrieve relevant context and LLM to generate
    a clinically-relevant explanation.
    """
    if retriever is None or not retriever.is_loaded:
        raise HTTPException(status_code=503, detail="RAG retriever not loaded")

    if generator is None:
        raise HTTPException(status_code=503, detail="RAG generator not initialized")

    try:
        # Retrieve relevant context
        chunks = retriever.retrieve_for_variant(
            gene=request.gene,
            variant_type="",
            consequence=request.consequence,
            top_k=7
        )

        # Format context
        context = retriever.format_context(chunks)

        # Generate explanation
        variant_info = {
            "gene": request.gene,
            "variant": request.variant,
            "prediction": request.prediction,
            "confidence": request.confidence,
            "consequence": request.consequence
        }

        known_diseases = GENE_DISEASE_MAP.get(request.gene.upper(), [])
        explanation = generator.generate_explanation(
            variant_info, context, known_diseases=known_diseases or None
        )

        # Format sources with PubMed URLs
        sources = []
        for chunk in chunks:
            source_file = chunk["source"]
            title = chunk.get("title", "")

            pmid, url = resolve_chunk_source(source_file, chunk.get("text", ""))

            sources.append({
                "source": source_file,
                "title": title,
                "pmid": pmid,
                "url": url,
                "score": round(chunk["score"], 4)
            })

        return ExplainResponse(explanation=explanation, sources=sources)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Explanation error: {str(e)}")


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Chat with the epilepsy genetics assistant.

    Supports multi-turn conversation with optional variant context.
    """
    if generator is None:
        raise HTTPException(status_code=503, detail="RAG generator not initialized")

    try:
        # Get the last user message for retrieval
        user_messages = [m for m in request.messages if m.role == "user"]
        last_query = user_messages[-1].content if user_messages else ""

        # Check if question is very basic/general that doesn't need literature sources
        # Examples: "what is this gene?", "hello", "thanks"
        query_lower = last_query.lower().strip()
        is_basic_question = (
            # Very short questions (likely greetings or simple queries)
            len(query_lower.split()) <= 3 and any(word in query_lower for word in [
                'what is', 'what are', 'hello', 'hi', 'thanks', 'thank you', 'ok', 'okay'
            ]) or
            # Pure definition questions without clinical context
            (query_lower.startswith('what is') and '?' in query_lower and
             not any(clinical_term in query_lower for clinical_term in [
                 'treatment', 'medication', 'contraindicated', 'recommended',
                 'seizure', 'epilepsy', 'syndrome', 'variant'
             ]))
        )

        # Retrieve sources for ALL questions EXCEPT basic ones
        retrieved_context = None
        sources = []

        if last_query and not is_basic_question:
            # Try to extract gene from query or variant context
            gene = None
            if request.variant_context and request.variant_context.get('gene'):
                gene = request.variant_context['gene']
            else:
                # Try to detect gene mention in query
                query_upper = last_query.upper()
                for supported_gene in EPILEPSY_GENES:
                    if supported_gene in query_upper:
                        gene = supported_gene
                        break

            # Use multi-source retriever if gene is identified
            if multi_source_retriever and gene:
                print(f"\nUsing Multi-Source Retriever for {gene}...")
                multi_results = multi_source_retriever.retrieve_comprehensive(
                    gene=gene,
                    variant=None,
                    consequence=last_query,  # Use query as context
                    include_clinvar=True,
                    include_pharmgkb=True,
                    include_pubmed=True,
                    top_k=3
                )

                # Format context for LLM
                retrieved_context = multi_source_retriever.format_context_for_llm(multi_results, max_length=3000)

                print(f"Sources used: {multi_source_retriever.get_sources_summary(multi_results)}")

                # Add PubMed sources FIRST (most useful for chat follow-ups)
                if 'pubmed' in multi_results.get('sources', {}):
                    chunks = multi_results['sources']['pubmed']['chunks']
                    for chunk in chunks[:3]:  # Top 3 PubMed sources
                        source_file = chunk["source"]
                        title = chunk.get("title", "")

                        pmid, url = resolve_chunk_source(source_file, chunk.get("text", ""))

                        sources.append({
                            "source": source_file,
                            "title": title,
                            "pmid": pmid,
                            "url": url,
                            "score": round(chunk["score"], 4),
                            "type": "pubmed"
                        })

                # Add PharmGKB source if available
                if 'pharmgkb' in multi_results.get('sources', {}):
                    pharmgkb_url = f"https://www.pharmgkb.org/search?query={gene}"
                    sources.append({
                        "source": "PharmGKB",
                        "title": f"Drug-Gene Interactions for {gene}",
                        "url": pharmgkb_url,
                        "score": 0.95,
                        "type": "pharmgkb"
                    })

                # Add ClinVar sources (filter for Pathogenic/Likely Pathogenic, max 2)
                if 'clinvar' in multi_results.get('sources', {}):
                    clinvar_variants = multi_results['sources']['clinvar']['variants']

                    # Filter to only Pathogenic or Likely Pathogenic variants
                    pathogenic_variants = [
                        v for v in clinvar_variants
                        if 'pathogenic' in v['clinical_significance'].lower()
                        and 'conflicting' not in v['clinical_significance'].lower()
                    ]

                    # If no pathogenic, show top 1 highest-rated variant
                    if not pathogenic_variants:
                        pathogenic_variants = sorted(
                            clinvar_variants[:5],
                            key=lambda x: x['review_stars'],
                            reverse=True
                        )[:1]

                    # Add max 2 pathogenic variants
                    for cv_variant in pathogenic_variants[:2]:
                        sources.append({
                            "source": "ClinVar",
                            "title": f"{cv_variant['variant_name'][:60]}... - {cv_variant['clinical_significance']}",
                            "url": cv_variant['url'],
                            "score": 1.0,
                            "type": "clinvar"
                        })

            # Fallback to PubMed-only retrieval if no gene identified
            elif retriever and retriever.is_loaded:
                print("\nUsing PubMed-only retrieval (no gene identified)...")
                chunks = retriever.retrieve(last_query, top_k=3)

                # Only use sources if relevance score is decent (>0.25)
                if chunks and chunks[0]["score"] > 0.25:
                    retrieved_context = retriever.format_context(chunks, max_length=2000)

                    # Format PubMed sources
                    for chunk in chunks:
                        source_file = chunk["source"]
                        title = chunk.get("title", "")

                        pmid, url = resolve_chunk_source(source_file, chunk.get("text", ""))

                        sources.append({
                            "source": source_file,
                            "title": title,
                            "pmid": pmid,
                            "url": url,
                            "score": round(chunk["score"], 4),
                            "type": "pubmed"
                        })

        # --- Inject variant analysis features into chat context ---
        # If variant_context carries ACMG/SHAP/gnomAD/contradiction data from
        # a prior /analyze_variant call, enrich the retrieved_context so the
        # LLM can answer follow-up questions with the full clinical picture.
        vctx = request.variant_context or {}
        extra_context_parts = []

        # ACMG classification
        acmg = vctx.get("acmg_classification")
        if acmg and acmg.get("criteria_met"):
            extra_context_parts.append(acmg.get("context_for_llm", ""))

        # SHAP clinical evidence
        shap = vctx.get("shap_explanation")
        if shap and shap.get("context_for_llm"):
            extra_context_parts.append(shap["context_for_llm"])

        # gnomAD population frequency
        gnomad = vctx.get("gnomad_data")
        if gnomad and gnomad_fetcher:
            try:
                gnomad_ctx = gnomad_fetcher.format_for_context(gnomad)
                extra_context_parts.append(gnomad_ctx)
            except Exception:
                pass

        # Contradiction warnings
        contradictions = vctx.get("contradictions")
        if contradictions and contradictions.get("has_contradictions"):
            extra_context_parts.append(contradictions.get("context_for_llm", ""))

        # Uncertainty analysis
        uncertainty = vctx.get("uncertainty_analysis")
        if uncertainty and uncertainty.get("is_uncertain"):
            extra_context_parts.append(uncertainty.get("additional_prompt", ""))

        # Merge all extra context with retrieved_context
        if extra_context_parts:
            extra_block = "\n\n".join(p for p in extra_context_parts if p)
            if retrieved_context:
                retrieved_context = extra_block + "\n\n" + retrieved_context
            else:
                retrieved_context = extra_block

        # Convert messages to dict format
        messages_dict = [{"role": m.role, "content": m.content} for m in request.messages]

        # Generate response
        response = generator.chat(
            messages=messages_dict,
            variant_context=request.variant_context,
            retrieved_context=retrieved_context
        )

        return ChatResponse(response=response, sources=sources)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Chat error: {str(e)}")


@app.post("/generate_report")
async def generate_pdf_report(request: PDFReportRequest):
    """
    Generate a PDF report for medical workers.

    Includes:
    - Variant information and prediction
    - Clinical recommendations (concise, medical terms)
    - Sources with PubMed links
    - Disclaimer
    """
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import inch
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
        from reportlab.lib import colors
        from reportlab.lib.enums import TA_CENTER

        # Create PDF in memory
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter,
                              topMargin=0.75*inch, bottomMargin=0.75*inch,
                              leftMargin=0.75*inch, rightMargin=0.75*inch)

        # Styles
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=18,
            textColor=colors.HexColor('#1e40af'),
            spaceAfter=12,
            alignment=TA_CENTER
        )
        heading_style = ParagraphStyle(
            'CustomHeading',
            parent=styles['Heading2'],
            fontSize=14,
            textColor=colors.HexColor('#1e40af'),
            spaceAfter=8,
            spaceBefore=12
        )
        body_style = ParagraphStyle(
            'CustomBody',
            parent=styles['BodyText'],
            fontSize=10,
            spaceAfter=6
        )

        # Parse AI response to extract key clinical terms
        def extract_clinical_info(rag_text):
            """Extract key clinical information from RAG response."""
            # Clean HTML/markdown
            clean_text = re.sub(r'<span class="[^"]*">([^<]*)</span>', r'\1', rag_text)
            clean_text = re.sub(r'[🧬📋💊⚠️✓🔬]', '', clean_text)

            # Extract sections
            recommended_meds = []
            contraindicated_meds = []
            clinical_features = []

            # Split by lines
            lines = clean_text.split('\n')
            current_section = None

            for line in lines:
                line = line.strip()
                if not line or line.startswith('##'):
                    continue

                # Detect sections
                line_lower = line.lower()
                if 'first-line' in line_lower or 'recommended' in line_lower:
                    current_section = 'recommended'
                    continue
                elif 'contraindicated' in line_lower or 'avoid' in line_lower:
                    current_section = 'contraindicated'
                    continue
                elif 'clinical' in line_lower or 'phenotype' in line_lower or 'syndrome' in line_lower:
                    current_section = 'clinical'
                    continue

                # Extract medication names (capitalize first letter)
                if current_section == 'recommended':
                    # Look for medication patterns
                    meds = re.findall(r'\b([A-Z][a-z]+(?:azepam|azine|ate|pine|ide|ol|oxin))\b', line)
                    recommended_meds.extend(meds)
                    # Also look for bullet points
                    if line.startswith('•') or line.startswith('-') or line.startswith('*'):
                        med_text = line.lstrip('•-* ').split(':')[0].split('(')[0].strip()
                        if med_text and len(med_text) < 30:
                            recommended_meds.append(med_text)

                elif current_section == 'contraindicated':
                    # Extract contraindicated medications
                    meds = re.findall(r'\b([A-Z][a-z]+(?:azepam|azine|ate|pine|ide|ol|oxin))\b', line)
                    contraindicated_meds.extend(meds)
                    if line.startswith('•') or line.startswith('-') or line.startswith('*'):
                        med_text = line.lstrip('•-* ').split(':')[0].split('(')[0].strip()
                        if med_text and len(med_text) < 30:
                            contraindicated_meds.append(med_text)

                elif current_section == 'clinical':
                    # Extract clinical features
                    if line.startswith('•') or line.startswith('-') or line.startswith('*'):
                        feature = line.lstrip('•-* ').strip()
                        if feature and len(feature) < 100:
                            clinical_features.append(feature)

            # Remove duplicates while preserving order
            recommended_meds = list(dict.fromkeys(recommended_meds))
            contraindicated_meds = list(dict.fromkeys(contraindicated_meds))
            clinical_features = list(dict.fromkeys(clinical_features))

            return {
                'recommended': recommended_meds[:8],  # Limit to 8
                'contraindicated': contraindicated_meds[:8],
                'clinical': clinical_features[:6]  # Limit to 6
            }

        # Extract clinical information
        clinical_info = extract_clinical_info(request.rag_response)

        # Build content
        story = []

        # Title
        story.append(Paragraph("Epilepsy Genetic Variant Report", title_style))
        story.append(Spacer(1, 0.3*inch))

        # Recommended Medications
        if clinical_info['recommended']:
            story.append(Paragraph("✓ Recommended Medications", heading_style))
            for med in clinical_info['recommended']:
                story.append(Paragraph(f"• {med}", body_style))
            story.append(Spacer(1, 0.2*inch))

        # Contraindicated Medications
        if clinical_info['contraindicated']:
            warning_style = ParagraphStyle(
                'Warning',
                parent=body_style,
                textColor=colors.HexColor('#991b1b')
            )
            story.append(Paragraph("⚠ Contraindicated Medications (AVOID)", heading_style))
            for med in clinical_info['contraindicated']:
                story.append(Paragraph(f"• {med}", warning_style))
            story.append(Spacer(1, 0.2*inch))

        # Clinical Features
        if clinical_info['clinical']:
            story.append(Paragraph("Clinical Features", heading_style))
            for feature in clinical_info['clinical']:
                story.append(Paragraph(f"• {feature}", body_style))
            story.append(Spacer(1, 0.2*inch))

        # Sources
        if request.sources:
            story.append(Paragraph("References", heading_style))
            for idx, source in enumerate(request.sources[:5], 1):  # Limit to 5 sources
                source_text = f"[{idx}] "
                if source.get('title'):
                    source_text += f"{source['title']}. "
                if source.get('pmid'):
                    source_text += f"PMID: {source['pmid']}. "
                if source.get('url'):
                    source_text += f"<link href='{source['url']}'>{source['url']}</link>"

                story.append(Paragraph(source_text, body_style))

            story.append(Spacer(1, 0.2*inch))

        # Disclaimer
        story.append(Spacer(1, 0.3*inch))
        disclaimer_style = ParagraphStyle(
            'Disclaimer',
            parent=styles['BodyText'],
            fontSize=8,
            textColor=colors.HexColor('#6b7280'),
            borderWidth=1,
            borderColor=colors.HexColor('#d1d5db'),
            borderPadding=8,
            spaceAfter=6
        )
        disclaimer_text = """
        <b>DISCLAIMER:</b> This report is generated by an AI-assisted diagnostic tool and is intended
        for informational purposes only. It should not replace professional medical judgment, clinical
        evaluation, or genetic counseling. Treatment decisions should be made by qualified healthcare
        professionals based on comprehensive patient assessment, current clinical guidelines, and
        individual patient factors. This tool uses machine learning predictions and may not account
        for all clinical variables. Always consult with a medical geneticist or epilepsy specialist
        for clinical decision-making.
        """
        story.append(Paragraph(disclaimer_text, disclaimer_style))

        # Footer
        footer_style = ParagraphStyle(
            'Footer',
            parent=styles['BodyText'],
            fontSize=8,
            textColor=colors.HexColor('#9ca3af'),
            alignment=TA_CENTER
        )
        story.append(Spacer(1, 0.1*inch))
        story.append(Paragraph(f"Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", footer_style))

        # Build PDF
        doc.build(story)
        buffer.seek(0)

        # Return as streaming response
        return StreamingResponse(
            buffer,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename=epilepsy_report_{request.variant_info.get('gene', 'variant')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
            }
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"PDF generation error: {str(e)}")


@app.get("/literature/{gene}", response_model=LiteratureResponse)
async def get_literature(gene: str):
    """
    Fetch recent literature for a specific gene from PubMed.

    This endpoint:
    1. Checks 24-hour cache first
    2. Fetches fresh papers from PubMed if cache expired
    3. Generates AI summaries for each paper
    4. Categorizes by publication type
    5. Automatically updates RAG knowledge base with new papers

    Args:
        gene: Gene symbol (e.g., 'SCN1A')

    Returns:
        List of recent papers with AI-generated summaries
    """
    # Validate gene
    gene_upper = gene.upper()
    if gene_upper not in EPILEPSY_GENES:
        raise HTTPException(
            status_code=400,
            detail=f"Gene '{gene}' not supported. Supported genes: {EPILEPSY_GENES}"
        )

    if literature_fetcher is None:
        raise HTTPException(status_code=503, detail="Literature fetcher not initialized")

    try:
        # Check if cache is valid
        cache_path = literature_fetcher._get_cache_path(gene_upper)
        is_cached = literature_fetcher._is_cache_valid(cache_path)

        # Fetch papers (will use cache if valid, otherwise fetch fresh)
        papers = literature_fetcher.fetch_pubmed_papers(
            gene=gene_upper,
            max_results=20,
            months_back=6
        )

        return LiteratureResponse(
            gene=gene_upper,
            papers=[LiteraturePaper(**paper) for paper in papers],
            cached=is_cached,
            total_count=len(papers)
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Literature fetch error: {str(e)}")


# ============================================================================
# Main Entry Point
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )
