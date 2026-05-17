"""
RAG (Retrieval-Augmented Generation) module for Epilepsy Diagnostic Assistant.

This module provides:
- RAGRetriever: Retrieves relevant documents from FAISS index
- RAGGenerator: Generates responses using Groq LLM with retrieved context
"""

from .retriever import RAGRetriever
from .generator import RAGGenerator

__all__ = ["RAGRetriever", "RAGGenerator"]
