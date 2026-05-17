# Epilepsy Diagnostic Assistant

An AI-powered epilepsy genetic variant diagnostic assistant that combines machine learning pathogenicity prediction with RAG-based explanations and a chatbot interface.

## Features

- **Variant Pathogenicity Prediction**: XGBoost model trained on 51,060 epilepsy variants (89.9% accuracy)
- **RAG-Powered Explanations**: Retrieval-augmented generation using medical literature
- **Interactive Chat**: Ask questions about epilepsy genetics and get informed answers
- **26 Epilepsy Genes**: Comprehensive coverage of known epilepsy-related genes
- **Treatment Guidelines**: Gene-specific treatment recommendations

## Project Structure

```
epilepsy_diagnostic_assistant/
├── backend/                    # FastAPI backend
│   └── app.py                  # Main API server
├── frontend/                   # React frontend
│   ├── src/
│   │   ├── components/         # React components
│   │   ├── services/           # API service
│   │   └── types/              # TypeScript types
│   └── package.json
├── rag/                        # RAG pipeline
│   ├── retriever.py            # FAISS-based document retrieval
│   └── generator.py            # Groq LLM response generation
├── scripts/                    # Utility scripts
│   ├── fetch_pubmed.py         # Download PubMed abstracts
│   └── build_knowledge_base.py # Build FAISS index
├── data/
│   ├── knowledge_base/         # Treatment guidelines, PubMed abstracts
│   ├── faiss_index/            # Vector index (generated)
│   └── processed/              # Processed training data
├── models/                     # Trained ML models
│   └── epilepsy_classifier_no_phenotype.pkl
├── requirements.txt            # Python dependencies
└── .env.example                # Environment template
```

## Setup

### 1. Clone and Install Python Dependencies

```bash
cd epilepsy_diagnostic_assistant
pip install -r requirements.txt
```

### 2. Set Up Environment Variables

```bash
cp .env.example .env
# Edit .env and add your GROQ_API_KEY
```

Get your Groq API key from: https://console.groq.com/keys

### 3. Build the Knowledge Base

```bash
# Fetch PubMed abstracts (takes ~5-10 minutes)
python scripts/fetch_pubmed.py

# Build FAISS vector index
python scripts/build_knowledge_base.py
```

### 4. Start the Backend

```bash
cd backend
uvicorn app:app --reload --port 8000
```

The API will be available at http://localhost:8000

### 5. Start the Frontend

```bash
cd frontend
npm install
npm start
```

The frontend will be available at http://localhost:3000

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check and system status |
| `/genes` | GET | List of supported genes |
| `/predict_variant` | POST | Predict variant pathogenicity |
| `/explain_variant` | POST | Get AI explanation for prediction |
| `/chat` | POST | Chat with the assistant |

## Supported Genes (26)

- **Sodium Channels**: SCN1A, SCN2A, SCN3A, SCN8A
- **Potassium Channels**: KCNQ2, KCNQ3
- **GABA Receptors**: GABRA1, GABRG2
- **TSC Complex**: TSC1, TSC2
- **Rett-Related**: MECP2, CDKL5, FOXG1, PCDH19
- **Transporters**: SLC2A1, SLC6A1
- **Others**: ARX, STXBP1, DEPDC5, TBC1D24, LGI1, GRIN2A, CHD2, PRRT2, ALDH7A1, CACNA1A

## Model Performance

- **Overall Accuracy**: 89.9%
- **ROC AUC**: 94.5%
- **Stop-gained Variants**: 99.2% accuracy
- **Frameshift Variants**: 99.9% accuracy

## Technology Stack

- **ML Model**: XGBoost with 93 features
- **Backend**: FastAPI
- **Frontend**: React + TypeScript + Tailwind CSS
- **RAG**: FAISS + Sentence Transformers (PubMedBERT)
- **LLM**: Groq (llama-3.3-70b-versatile)

## Disclaimer

This tool is for **research purposes only**. It is not intended for clinical diagnosis or treatment decisions. Always consult with qualified healthcare professionals for medical advice.

## License

MIT License
