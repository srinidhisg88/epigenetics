# System Architecture - Epilepsy Diagnostic Assistant

## Table of Contents
1. [Overview](#overview)
2. [High-Level Architecture](#high-level-architecture)
3. [Frontend Architecture](#frontend-architecture)
4. [Backend Architecture](#backend-architecture)
5. [Data Flow](#data-flow)
6. [Component Interactions](#component-interactions)
7. [Deployment Architecture](#deployment-architecture)
8. [Security Considerations](#security-considerations)
9. [Scalability](#scalability)
10. [Technology Stack](#technology-stack)

---

## Overview

The Epilepsy Diagnostic Assistant is a full-stack web application that combines machine learning, retrieval-augmented generation (RAG), and modern web technologies to provide clinical decision support for genetic variant analysis in epilepsy patients.

### System Goals
1. **Accurate Prediction**: Classify genetic variants as pathogenic/benign with >90% accuracy
2. **Evidence-Based Recommendations**: Provide treatment guidance backed by medical literature
3. **Interactive Interface**: Enable clinicians to explore and validate findings
4. **Continuous Learning**: Automatically integrate new research findings
5. **Fast Response**: Deliver results in <5 seconds end-to-end

---

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Client Layer (Browser)                       │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────────────────┐   │
│  │   Variant    │  │  Diagnostic  │  │   Literature           │   │
│  │   Analysis   │  │   Results    │  │   Dashboard            │   │
│  └──────────────┘  └──────────────┘  └────────────────────────┘   │
│                      React Frontend (TypeScript)                     │
└─────────────────────────────────────────────────────────────────────┘
                               ↓ HTTPS/REST API
┌─────────────────────────────────────────────────────────────────────┐
│                        API Gateway Layer                             │
│                     FastAPI (Python 3.11+)                          │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────────────────┐   │
│  │   /predict   │  │   /analyze   │  │   /literature/{gene}   │   │
│  │   /chat      │  │   /health    │  │   /generate_report     │   │
│  └──────────────┘  └──────────────┘  └────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
                               ↓
┌─────────────────────────────────────────────────────────────────────┐
│                       Business Logic Layer                           │
│  ┌──────────────────────┐  ┌──────────────────────────────────┐   │
│  │   ML Prediction      │  │   RAG Pipeline                    │   │
│  │   Engine             │  │   ┌─────────────┐  ┌──────────┐  │   │
│  │   ┌────────────┐     │  │   │  Retriever  │  │Generator │  │   │
│  │   │  XGBoost   │     │  │   │   (FAISS)   │  │  (LLM)   │  │   │
│  │   │  Model     │     │  │   └─────────────┘  └──────────┘  │   │
│  │   └────────────┘     │  └──────────────────────────────────┘   │
│  └──────────────────────┘                                           │
└─────────────────────────────────────────────────────────────────────┘
                               ↓
┌─────────────────────────────────────────────────────────────────────┐
│                          Data Layer                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────────────────┐   │
│  │   FAISS      │  │   ML Model   │  │   Literature Cache     │   │
│  │   Vector DB  │  │   (.pkl)     │  │   (JSON)               │   │
│  └──────────────┘  └──────────────┘  └────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
                               ↓
┌─────────────────────────────────────────────────────────────────────┐
│                       External Services                              │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────────────────┐   │
│  │   Groq API   │  │   PubMed     │  │   NCBI E-utilities     │   │
│  │   (LLM)      │  │   Database   │  │   API                  │   │
│  └──────────────┘  └──────────────┘  └────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Frontend Architecture

### Technology Stack
- **Framework**: React 18+ (TypeScript)
- **Build Tool**: Create React App / Vite
- **Styling**: Tailwind CSS
- **HTTP Client**: Axios
- **State Management**: React Hooks (useState, useEffect)
- **Markdown Rendering**: react-markdown + rehype-raw

### Component Hierarchy

```
App.tsx (Root)
├── Sidebar.tsx (Navigation)
├── Tab: Analysis
│   ├── VariantForm.tsx (Input)
│   │   ├── Gene Selector
│   │   ├── Chromosome Selector
│   │   ├── Allele Inputs
│   │   ├── Consequence Selector
│   │   └── Submit Button
│   └── PredictionResult.tsx (ML Output)
│       ├── Pathogenicity Badge
│       ├── Confidence Score
│       └── Probability Chart
├── Tab: Diagnostic Results
│   └── ChatInterface.tsx (RAG + Q&A)
│       ├── Variant Summary Card
│       ├── RAG Response Display
│       │   ├── Clinical Information
│       │   ├── Treatment Recommendations
│       │   └── Sources (Expandable)
│       └── Follow-up Chat
│           ├── Suggested Questions
│           ├── Message History
│           └── Input Field
└── Tab: Literature
    └── LiteratureDashboard.tsx
        ├── Gene Selector
        ├── Fetch Button
        └── Papers List
            ├── Paper Cards
            │   ├── Title & Authors
            │   ├── AI Summary
            │   └── Abstract (Expandable)
            └── Category Badges
```

### State Management Pattern

```typescript
// App.tsx - Top-level state
interface RAGChatData {
  gene: string;
  variant: string;
  prediction: string;
  confidence: number;
  consequence: string;
  ragResponse: string;
  sources: Source[];
}

const [ragChatData, setRagChatData] = useState<RAGChatData | null>(null);
const [activeTab, setActiveTab] = useState<TabType>('analysis');

// Data flow: VariantForm → App → ChatInterface
const handleAnalyze = async (variant: VariantInput) => {
  const result = await analyzeVariant(variant);

  if (result.prediction === "Pathogenic") {
    setRagChatData({
      gene: result.variant_info.gene,
      variant: `${result.variant_info.reference_allele}>${result.variant_info.alternate_allele}`,
      prediction: result.prediction,
      confidence: result.confidence,
      consequence: result.variant_info.consequence,
      ragResponse: result.rag_response,
      sources: result.sources,
    });
    setActiveTab('chat'); // Auto-switch to results
  }
};
```

### API Service Layer

```typescript
// services/api.ts
import axios from 'axios';

const api = axios.create({
  baseURL: process.env.REACT_APP_API_URL || 'http://localhost:8000',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Centralized error handling
api.interceptors.response.use(
  response => response,
  error => {
    console.error('API Error:', error.response?.data);
    return Promise.reject(error);
  }
);

// Typed API functions
export const analyzeVariant = async (
  variant: VariantInput
): Promise<FullAnalysisResponse> => {
  const response = await api.post<FullAnalysisResponse>('/analyze_variant', variant);
  return response.data;
};

export const chat = async (request: ChatRequest): Promise<ChatResponse> => {
  const response = await api.post<ChatResponse>('/chat', request);
  return response.data;
};

export const getLiterature = async (gene: string): Promise<LiteratureResponse> => {
  const response = await api.get<LiteratureResponse>(`/literature/${gene}`);
  return response.data;
};
```

### Routing Strategy

**Single-Page Application (SPA)**:
- No traditional routing (no React Router)
- Tab-based navigation within single page
- State-driven view switching
- Deep linking via URL parameters (optional enhancement)

### Responsive Design

```css
/* Tailwind CSS Breakpoints */
sm: 640px   /* Mobile landscape */
md: 768px   /* Tablets */
lg: 1024px  /* Laptops */
xl: 1280px  /* Desktops */
2xl: 1536px /* Large screens */

/* Layout pattern */
<div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
  {/* Stacks on mobile, side-by-side on desktop */}
</div>
```

---

## Backend Architecture

### Technology Stack
- **Framework**: FastAPI 0.104+
- **Runtime**: Python 3.11+
- **ML Framework**: XGBoost 2.0+, scikit-learn 1.3+
- **RAG**: sentence-transformers, FAISS, Groq
- **Data Fetching**: Biopython (PubMed), requests
- **PDF Generation**: ReportLab 4.0+
- **ASGI Server**: Uvicorn 0.24+

### Layered Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                  Presentation Layer                          │
│  ┌────────────┐  ┌────────────┐  ┌─────────────────────┐   │
│  │  FastAPI   │  │   CORS     │  │   Request           │   │
│  │  Routes    │  │ Middleware │  │   Validation        │   │
│  └────────────┘  └────────────┘  └─────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────────┐
│                  Business Logic Layer                        │
│  ┌──────────────────────┐  ┌──────────────────────────┐    │
│  │  Feature Engineering │  │  Prediction Logic        │    │
│  │  - Gene encoding     │  │  - Model inference       │    │
│  │  - Variant parsing   │  │  - Confidence scoring    │    │
│  │  - Consequence map   │  │  - Result formatting     │    │
│  └──────────────────────┘  └──────────────────────────┘    │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐  │
│  │           RAG Orchestration                          │  │
│  │  ┌─────────────┐  ┌──────────────┐  ┌───────────┐  │  │
│  │  │  Retriever  │→ │  Context     │→ │ Generator │  │  │
│  │  │  Invoker    │  │  Formatter   │  │  Invoker  │  │  │
│  │  └─────────────┘  └──────────────┘  └───────────┘  │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────────┐
│                  Data Access Layer                           │
│  ┌────────────────┐  ┌────────────────┐  ┌─────────────┐   │
│  │  ML Model      │  │  FAISS Index   │  │  Cache      │   │
│  │  Loader        │  │  Manager       │  │  Manager    │   │
│  └────────────────┘  └────────────────┘  └─────────────┘   │
└─────────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────────┐
│                  External Services Layer                     │
│  ┌────────────────┐  ┌────────────────┐  ┌─────────────┐   │
│  │  Groq Client   │  │  PubMed API    │  │  File I/O   │   │
│  └────────────────┘  └────────────────┘  └─────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

### Application Lifecycle

```python
# app.py - Lifespan management
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown logic."""

    # === STARTUP ===
    global retriever, generator, literature_fetcher

    print("Starting Epilepsy Diagnostic Assistant API...")

    # 1. Load gene statistics
    with open(GENE_STATS_PATH) as f:
        gene_stats = json.load(f)

    # 2. Initialize RAG retriever (loads FAISS index)
    retriever = RAGRetriever()
    print(f"  Loaded {retriever.get_stats()['total_chunks']} documents")

    # 3. Initialize RAG generator (connects to Groq)
    generator = RAGGenerator()
    print(f"  Connected to {generator.model}")

    # 4. Initialize literature fetcher
    literature_fetcher = LiteratureFetcher(update_rag=True)

    print("API startup complete\n")

    yield  # Application runs

    # === SHUTDOWN ===
    print("Shutting down API...")
    # Cleanup resources if needed

app = FastAPI(lifespan=lifespan)
```

### CORS Configuration

```python
# Development: Allow all origins
allow_all_cors = os.getenv("CORS_ALLOW_ALL", "true").lower() == "true"

if allow_all_cors:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
else:
    # Production: Specific origins only
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["https://yourdomain.com"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
```

### API Endpoints

#### 1. Health Check
```python
@app.get("/health", response_model=HealthResponse)
async def health_check():
    """System health and component status."""
    return {
        "status": "ok",
        "model_loaded": ml_model is not None,
        "rag_loaded": retriever.is_loaded,
        "details": {
            "ml_features": len(ml_feature_names),
            "rag_chunks": retriever.get_stats()["total_chunks"],
            "rag_generator": "initialized"
        }
    }
```

#### 2. Variant Prediction
```python
@app.post("/predict_variant", response_model=PredictionResponse)
async def predict_variant(variant: VariantInput):
    """ML-only prediction (no RAG)."""

    # 1. Engineer features
    features_df = engineer_features(variant)

    # 2. Predict with XGBoost
    prediction_proba = ml_model.predict_proba(features_df)[0]
    prediction_class = ml_model.predict(features_df)[0]

    # 3. Format response
    return {
        "prediction": "Pathogenic" if prediction_class == 1 else "Benign",
        "confidence": prediction_proba[prediction_class] * 100,
        "variant_info": {...}
    }
```

#### 3. Full Analysis (Prediction + RAG)
```python
@app.post("/analyze_variant", response_model=FullAnalysisResponse)
async def analyze_variant(variant: VariantInput):
    """Combined prediction + treatment recommendations."""

    # 1. ML prediction
    prediction_result = predict_variant(variant)

    # 2. If PATHOGENIC → trigger RAG pipeline
    if prediction_result.prediction == "Pathogenic":
        # 2a. Retrieve relevant documents
        chunks = retriever.retrieve_for_variant(
            gene=variant.gene,
            variant_type=variant.variant_type,
            consequence=variant.consequence,
            top_k=5
        )

        # 2b. Format context
        context = retriever.format_context(chunks)

        # 2c. Generate explanation
        rag_response = generator.generate_explanation(
            variant_detail={...},
            context=context
        )

        # 2d. Format sources
        sources = [
            {
                "title": chunk.get("metadata", {}).get("title"),
                "pmid": chunk.get("metadata", {}).get("pmid"),
                "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                "score": chunk.get("score")
            }
            for chunk in chunks
        ]

        return {
            **prediction_result,
            "rag_response": rag_response,
            "sources": sources
        }

    # 3. If BENIGN → return prediction only
    return prediction_result
```

#### 4. Chat Interface
```python
@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Follow-up Q&A with RAG."""

    # 1. Get variant context from request
    variant_context = request.variant_context

    # 2. Retrieve relevant documents for question
    chunks = retriever.retrieve_for_query(
        query=request.messages[-1]["content"],
        gene=variant_context["gene"],
        top_k=3
    )

    # 3. Format context
    context = retriever.format_context(chunks)

    # 4. Generate response
    response = generator.chat_response(
        messages=request.messages,
        context=context,
        variant_context=variant_context
    )

    return {
        "response": response,
        "sources": [...]
    }
```

#### 5. Literature Fetcher
```python
@app.get("/literature/{gene}", response_model=LiteratureResponse)
async def get_literature(gene: str):
    """Fetch recent PubMed papers for gene."""

    # 1. Validate gene
    if gene.upper() not in EPILEPSY_GENES:
        raise HTTPException(400, "Gene not supported")

    # 2. Check cache (24-hour TTL)
    cache_path = literature_fetcher._get_cache_path(gene)
    if literature_fetcher._is_cache_valid(cache_path):
        return literature_fetcher._load_from_cache(cache_path)

    # 3. Fetch from PubMed
    papers = literature_fetcher.fetch_pubmed_papers(
        gene=gene,
        max_results=20,
        months_back=6
    )

    # 4. Generate AI summaries for each paper
    for paper in papers:
        paper["summary"] = literature_fetcher._generate_summary(
            title=paper["title"],
            abstract=paper["abstract"],
            gene=gene
        )

    # 5. Update RAG knowledge base
    literature_fetcher._update_knowledge_base(papers, gene)

    # 6. Cache results
    literature_fetcher._save_to_cache(cache_path, papers)

    return {
        "gene": gene,
        "papers": papers,
        "cached": False,
        "total_count": len(papers)
    }
```

#### 6. PDF Report Generation
```python
@app.post("/generate_report")
async def generate_report(request: ReportRequest):
    """Generate PDF report with key clinical info."""

    # 1. Extract clinical terms from RAG response
    clinical_info = extract_clinical_info(request.rag_response)

    # 2. Generate PDF with ReportLab
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)

    story = []
    story.append(Paragraph("Epilepsy Genetic Variant Report", title_style))

    # Recommended medications
    if clinical_info['recommended']:
        story.append(Paragraph("✓ Recommended Medications", heading_style))
        for med in clinical_info['recommended']:
            story.append(Paragraph(f"• {med}", body_style))

    # Contraindicated medications
    if clinical_info['contraindicated']:
        story.append(Paragraph("⚠ Contraindicated Medications", heading_style))
        for med in clinical_info['contraindicated']:
            story.append(Paragraph(f"• {med}", warning_style))

    # Build PDF
    doc.build(story)

    # 3. Return as download
    buffer.seek(0)
    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=report.pdf"}
    )
```

---

## Data Flow

### 1. Variant Analysis Flow

```
User Input (Frontend)
    ↓
VariantForm validates input
    ↓
POST /analyze_variant
    ↓
Feature Engineering (93 features)
    ↓
XGBoost Model Prediction
    ↓
[Decision: Pathogenic?]
    ↓ YES                    ↓ NO
RAG Pipeline                Return prediction only
    ↓                           ↓
Retrieve (FAISS)           Frontend displays
    ↓                       benign result
Format Context
    ↓
Generate (Groq LLM)
    ↓
Format Sources
    ↓
Return full analysis
    ↓
Frontend switches to Chat tab
    ↓
Display RAG response + sources
```

### 2. Chat Interaction Flow

```
User asks follow-up question
    ↓
POST /chat with message history
    ↓
Extract last user message
    ↓
Retrieve relevant docs (FAISS)
    ↓
Format context
    ↓
Generate response (Groq LLM)
    ↓
Return response + sources
    ↓
Frontend appends to message history
    ↓
User sees answer with citations
```

### 3. Literature Update Flow

```
User selects gene + clicks Fetch
    ↓
GET /literature/{gene}
    ↓
Check 24-hour cache
    ↓ MISS
Fetch from PubMed (Biopython)
    ↓
Parse article metadata
    ↓
Generate AI summaries (Groq LLM)
    ↓
Categorize by publication type
    ↓
Update FAISS knowledge base
    ↓
Cache results (JSON)
    ↓
Return papers to frontend
    ↓
Display in literature dashboard
```

---

## Component Interactions

### Sequence Diagram: Full Variant Analysis

```
User    Frontend    API Gateway    ML Engine    RAG Retriever    RAG Generator    Groq API
 │          │            │              │              │               │              │
 │  Submit  │            │              │              │               │              │
 ├─────────>│            │              │              │               │              │
 │          │  POST      │              │              │               │              │
 │          ├───────────>│              │              │               │              │
 │          │            │   Predict    │              │               │              │
 │          │            ├─────────────>│              │               │              │
 │          │            │<─────────────┤              │               │              │
 │          │            │  [Pathogenic]│              │               │              │
 │          │            │              │              │               │              │
 │          │            │              │   Retrieve   │               │              │
 │          │            ├─────────────────────────────>│               │              │
 │          │            │<─────────────────────────────┤               │              │
 │          │            │              │    Chunks    │               │              │
 │          │            │              │              │               │              │
 │          │            │              │              │   Generate    │              │
 │          │            ├──────────────────────────────────────────────>│              │
 │          │            │              │              │               │   LLM Call   │
 │          │            │              │              │               ├─────────────>│
 │          │            │              │              │               │<─────────────┤
 │          │            │<──────────────────────────────────────────────┤              │
 │          │            │              │              │    Response   │              │
 │          │  Response  │              │              │               │              │
 │          │<───────────┤              │              │               │              │
 │  Display │            │              │              │               │              │
 │<─────────┤            │              │              │               │              │
```

---

## Deployment Architecture

### Development Environment

```yaml
# docker-compose.yml (future enhancement)
version: '3.8'

services:
  frontend:
    build: ./frontend
    ports:
      - "3000:3000"
    environment:
      - REACT_APP_API_URL=http://localhost:8000
    volumes:
      - ./frontend/src:/app/src

  backend:
    build: ./backend
    ports:
      - "8000:8000"
    environment:
      - GROQ_API_KEY=${GROQ_API_KEY}
      - ENTREZ_EMAIL=${ENTREZ_EMAIL}
      - NCBI_API_KEY=${NCBI_API_KEY}
    volumes:
      - ./backend:/app
      - ./data:/app/data
      - ./models:/app/models
```

### Production Deployment

```
┌──────────────────────────────────────────────────────────┐
│                     Load Balancer                         │
│                  (AWS ALB / Nginx)                        │
└──────────────────────────────────────────────────────────┘
                        ↓
        ┌───────────────┴───────────────┐
        ↓                               ↓
┌───────────────┐              ┌───────────────┐
│   Frontend    │              │   Frontend    │
│   (Nginx)     │              │   (Nginx)     │
│   Port 80     │              │   Port 80     │
└───────────────┘              └───────────────┘
        ↓                               ↓
        └───────────────┬───────────────┘
                        ↓
┌──────────────────────────────────────────────────────────┐
│                    API Gateway                            │
│                   (AWS API Gateway)                       │
└──────────────────────────────────────────────────────────┘
                        ↓
        ┌───────────────┴───────────────┐
        ↓                               ↓
┌───────────────┐              ┌───────────────┐
│   Backend     │              │   Backend     │
│   (Uvicorn)   │              │   (Uvicorn)   │
│   Port 8000   │              │   Port 8000   │
└───────────────┘              └───────────────┘
        ↓                               ↓
        └───────────────┬───────────────┘
                        ↓
┌──────────────────────────────────────────────────────────┐
│                   Shared Data Layer                       │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │   S3/EFS     │  │   ElastiCache│  │   CloudWatch │  │
│  │ (FAISS Index)│  │   (Redis)    │  │   (Logs)     │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  │
└──────────────────────────────────────────────────────────┘
```

### Containerization

```dockerfile
# backend/Dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose port
EXPOSE 8000

# Run application
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
```

```dockerfile
# frontend/Dockerfile
FROM node:18-alpine AS build

WORKDIR /app

# Install dependencies
COPY package*.json ./
RUN npm ci

# Build application
COPY . .
RUN npm run build

# Production stage
FROM nginx:alpine
COPY --from=build /app/build /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
```

---

## Security Considerations

### 1. API Security
- **CORS**: Configurable origins (strict in production)
- **Rate Limiting**: Prevent API abuse (future enhancement)
- **Input Validation**: Pydantic models enforce schemas
- **API Keys**: Groq/NCBI keys in environment variables (not hardcoded)

### 2. Data Privacy
- **No PHI Storage**: System does not store patient identifiable information
- **Variant Data**: Only genetic sequences (no names/IDs)
- **Logs**: Sanitize logs to remove sensitive data
- **HIPAA Compliance**: Architecture supports HIPAA requirements

### 3. Authentication (Future)
```python
# Example JWT authentication
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer

security = HTTPBearer()

def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    # Verify JWT token
    if not verify_jwt(token):
        raise HTTPException(status_code=401, detail="Invalid token")
    return decode_jwt(token)

@app.post("/analyze_variant")
async def analyze_variant(
    variant: VariantInput,
    user: dict = Depends(verify_token)
):
    # Protected endpoint
    ...
```

---

## Scalability

### Horizontal Scaling
- **Stateless Backend**: Multiple API instances behind load balancer
- **Shared Vector Store**: FAISS index on shared file system (EFS/S3)
- **Cache Layer**: Redis for literature cache
- **CDN**: Static frontend assets via CloudFront/Cloudflare

### Vertical Scaling
- **CPU-Intensive**: Feature engineering, FAISS search
- **Memory-Intensive**: ML model loading (~500MB), FAISS index (~2GB)
- **Recommended**: 4 vCPU, 8GB RAM per backend instance

### Performance Optimizations
1. **Model Loading**: Load once at startup (not per request)
2. **Embedding Cache**: Pre-computed embeddings in FAISS
3. **Response Caching**: Cache RAG responses for identical queries
4. **Async I/O**: FastAPI async endpoints for concurrent requests
5. **Connection Pooling**: Reuse HTTP connections to Groq API

---

## Technology Stack

### Frontend
| Component | Technology | Version | Purpose |
|-----------|-----------|---------|---------|
| Framework | React | 18+ | UI framework |
| Language | TypeScript | 4.9+ | Type safety |
| Styling | Tailwind CSS | 3.3+ | Utility-first CSS |
| HTTP Client | Axios | 1.4+ | API requests |
| Markdown | react-markdown | 8.0+ | Render formatted text |

### Backend
| Component | Technology | Version | Purpose |
|-----------|-----------|---------|---------|
| Framework | FastAPI | 0.104+ | API framework |
| Runtime | Python | 3.11+ | Core language |
| ML Library | XGBoost | 2.0+ | Gradient boosting |
| Embedding | sentence-transformers | 2.2+ | Text embeddings |
| Vector DB | FAISS | 1.7+ | Similarity search |
| LLM API | Groq | 0.4+ | Text generation |
| PubMed | Biopython | 1.81+ | Literature fetching |
| PDF | ReportLab | 4.0+ | Report generation |
| Server | Uvicorn | 0.24+ | ASGI server |

### Data & Models
| Component | Details |
|-----------|---------|
| ML Model | XGBoost (93 features, binary classifier) |
| Embedding Model | all-MiniLM-L6-v2 (384 dimensions) |
| LLM | Llama 3.3 70B (Groq-hosted) |
| Vector Index | FAISS Flat IP (cosine similarity) |
| Document Store | JSON (chunks + metadata) |

### External Services
| Service | Purpose | Rate Limit |
|---------|---------|------------|
| Groq API | LLM inference | 30 req/min (free tier) |
| PubMed E-utilities | Literature fetching | 10 req/sec (with API key) |
| NCBI Entrez | Article details | 3 req/sec (no key) |

---

## Monitoring & Observability

### Health Checks
```python
@app.get("/health")
async def health_check():
    return {
        "status": "ok",
        "timestamp": datetime.now().isoformat(),
        "components": {
            "ml_model": "loaded" if ml_model else "error",
            "rag_retriever": "loaded" if retriever else "error",
            "rag_generator": "loaded" if generator else "error",
        }
    }
```

### Logging
```python
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('app.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

# Example usage
logger.info(f"Variant analyzed: {gene} - {prediction}")
logger.error(f"RAG retrieval failed: {str(e)}")
```

### Metrics (Future Enhancement)
- Request latency (p50, p95, p99)
- Prediction accuracy over time
- RAG retrieval quality
- Error rates by endpoint
- User engagement metrics

---

## References

1. FastAPI Documentation: https://fastapi.tiangolo.com/
2. React Documentation: https://react.dev/
3. FAISS Documentation: https://faiss.ai/
4. Groq API: https://console.groq.com/docs
5. PubMed E-utilities: https://www.ncbi.nlm.nih.gov/books/NBK25501/
