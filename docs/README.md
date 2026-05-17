# Documentation

Welcome to the technical documentation for the Epilepsy Diagnostic Assistant.

## Available Documentation

### 1. [RAG Implementation](./RAG_IMPLEMENTATION.md)
Comprehensive guide to the Retrieval-Augmented Generation (RAG) pipeline.

**Contents**:
- Document ingestion and chunking strategy
- Embedding model (sentence-transformers)
- Vector store (FAISS) architecture
- Retrieval system with gene-specific optimization
- LLM generation with Groq API
- Literature auto-update system from PubMed
- Performance optimizations and evaluation metrics

**Read this if you want to understand**:
- How the system retrieves relevant medical literature
- How treatment recommendations are generated
- The RAG pipeline architecture and components
- Literature fetching and knowledge base updates

---

### 2. [System Architecture](./SYSTEM_ARCHITECTURE.md)
High-level overview of the entire system architecture.

**Contents**:
- Frontend architecture (React + TypeScript)
- Backend architecture (FastAPI + Python)
- Component interactions and data flow
- API endpoints and request/response patterns
- Deployment architecture
- Security considerations
- Scalability strategies
- Technology stack details

**Read this if you want to understand**:
- How the frontend and backend communicate
- The overall system design and component hierarchy
- API endpoint specifications
- Deployment and production considerations
- Technology choices and rationale

---

### 3. [ML Model Documentation](./ML_MODEL_DOCUMENTATION.md)
In-depth technical documentation of the machine learning model.

**Contents**:
- Problem formulation and clinical context
- Dataset composition (ClinVar variants)
- Feature engineering (93 features explained)
- XGBoost model architecture and hyperparameters
- Training process and hyperparameter tuning
- Evaluation metrics and performance analysis
- Model deployment and inference
- Future improvements and enhancements

**Read this if you want to understand**:
- How the pathogenicity prediction model works
- Feature engineering process
- Model training and evaluation
- Performance metrics and error analysis
- Clinical validation and accuracy

---

## Quick Reference

### For Developers
1. Start with [System Architecture](./SYSTEM_ARCHITECTURE.md) for overall system understanding
2. Read [RAG Implementation](./RAG_IMPLEMENTATION.md) to understand the RAG pipeline
3. Review [ML Model Documentation](./ML_MODEL_DOCUMENTATION.md) for prediction model details

### For Data Scientists
1. Start with [ML Model Documentation](./ML_MODEL_DOCUMENTATION.md) for model details
2. Read [RAG Implementation](./RAG_IMPLEMENTATION.md) for retrieval and generation
3. Review [System Architecture](./SYSTEM_ARCHITECTURE.md) for deployment context

### For Medical Professionals
1. Start with [ML Model Documentation](./ML_MODEL_DOCUMENTATION.md) - see "Clinical Context" section
2. Review "Model Performance" section for accuracy metrics
3. Read [RAG Implementation](./RAG_IMPLEMENTATION.md) - see "Prompt Engineering" for how recommendations are generated

### For System Administrators
1. Start with [System Architecture](./SYSTEM_ARCHITECTURE.md) - see "Deployment Architecture" section
2. Review "Security Considerations" and "Scalability" sections
3. Check "Monitoring & Observability" for operational guidance

---

## Additional Resources

### Main README
See [../README.md](../README.md) for:
- Project overview
- Installation instructions
- Quick start guide
- Usage examples

### Code Examples
- Frontend: [../frontend/src/](../frontend/src/)
- Backend: [../backend/](../backend/)
- RAG Pipeline: [../backend/rag/](../backend/rag/)
- Model Training: [../scripts/](../scripts/)

### API Documentation
When the backend is running, visit:
- **Interactive API Docs**: http://localhost:8000/docs
- **Alternative Docs**: http://localhost:8000/redoc

---

## Document Status

| Document | Last Updated | Status |
|----------|--------------|--------|
| RAG Implementation | 2026-02-26 | ✅ Complete |
| System Architecture | 2026-02-26 | ✅ Complete |
| ML Model Documentation | 2026-02-26 | ✅ Complete |

---

## Contributing to Documentation

If you find errors or want to improve the documentation:

1. **Small fixes**: Edit the markdown files directly
2. **Major updates**: Create a pull request with your changes
3. **Questions**: Open an issue on GitHub

### Documentation Guidelines
- Keep technical accuracy as top priority
- Include code examples where helpful
- Use diagrams for complex concepts
- Update the "Last Updated" date when making changes
- Cross-reference related sections

---

## Contact

For questions about the documentation:
- **Technical Issues**: Open a GitHub issue
- **Clinical Questions**: Consult with medical professionals
- **General Inquiries**: Contact the maintainers

---

## License

This documentation is part of the Epilepsy Diagnostic Assistant project.
See [../LICENSE](../LICENSE) for license information.
