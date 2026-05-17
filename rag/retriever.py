"""
RAG Retriever module for Epilepsy Diagnostic Assistant.

Handles loading the FAISS index and retrieving relevant document chunks
based on semantic similarity.
"""

import json
from pathlib import Path
from typing import List, Dict, Optional
import numpy as np

import faiss
from sentence_transformers import SentenceTransformer


class RAGRetriever:
    """
    Retrieves relevant document chunks from the FAISS knowledge base index.

    Attributes:
        index: FAISS index for vector similarity search
        chunks: List of chunk metadata with text content
        model: Sentence transformer model for encoding queries
    """

    def __init__(
        self,
        index_path: Optional[str] = None,
        chunks_path: Optional[str] = None,
        model_name: str = "pritamdeka/S-PubMedBert-MS-MARCO"
    ):
        """
        Initialize the RAG Retriever.

        Args:
            index_path: Path to FAISS index file. If None, uses default location.
            chunks_path: Path to chunks JSON file. If None, uses default location.
            model_name: Sentence transformer model name for query encoding.
        """
        # Determine paths
        base_dir = Path(__file__).parent.parent
        self.index_path = Path(index_path) if index_path else base_dir / "data" / "faiss_index" / "index.faiss"
        self.chunks_path = Path(chunks_path) if chunks_path else base_dir / "data" / "faiss_index" / "chunks.json"

        self.model_name = model_name
        self.index: Optional[faiss.Index] = None
        self.chunks: List[Dict] = []
        self.model: Optional[SentenceTransformer] = None
        self._loaded = False

    def load(self) -> bool:
        """
        Load the FAISS index, chunks, and embedding model.

        Returns:
            True if loaded successfully, False otherwise.
        """
        try:
            # Check if files exist
            if not self.index_path.exists():
                print(f"Error: FAISS index not found at {self.index_path}")
                print("Please run scripts/build_knowledge_base.py first.")
                return False

            if not self.chunks_path.exists():
                print(f"Error: Chunks file not found at {self.chunks_path}")
                return False

            # Load FAISS index
            print(f"Loading FAISS index from {self.index_path}...")
            self.index = faiss.read_index(str(self.index_path))
            print(f"  Index loaded: {self.index.ntotal} vectors")

            # Load chunks metadata
            print(f"Loading chunks from {self.chunks_path}...")
            with open(self.chunks_path, 'r', encoding='utf-8') as f:
                self.chunks = json.load(f)
            print(f"  Chunks loaded: {len(self.chunks)} chunks")

            # Load embedding model
            print(f"Loading embedding model: {self.model_name}...")
            self.model = SentenceTransformer(self.model_name)
            print("  Model loaded successfully")

            self._loaded = True
            return True

        except Exception as e:
            print(f"Error loading retriever: {e}")
            return False

    @property
    def is_loaded(self) -> bool:
        """Check if the retriever is loaded and ready."""
        return self._loaded

    def retrieve(self, query: str, top_k: int = 5) -> List[Dict]:
        """
        Retrieve top-k relevant document chunks for a query.

        Args:
            query: Search query string
            top_k: Number of results to return

        Returns:
            List of dictionaries with 'text', 'source', 'title', 'score' keys
        """
        if not self._loaded:
            raise RuntimeError("Retriever not loaded. Call load() first.")

        # Encode query
        query_embedding = self.model.encode(
            [query],
            normalize_embeddings=True,
            show_progress_bar=False
        )
        query_embedding = np.array(query_embedding, dtype=np.float32)

        # Search FAISS index
        scores, indices = self.index.search(query_embedding, top_k)

        # Build results
        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx < 0 or idx >= len(self.chunks):
                continue

            chunk = self.chunks[idx]
            results.append({
                "text": chunk["text"],
                "source": chunk["source"],
                "title": chunk.get("title", ""),
                "chunk_id": chunk.get("chunk_id", ""),
                "score": float(score)
            })

        return results

    def retrieve_for_variant(self, gene: str, variant_type: str, consequence: str, top_k: int = 5) -> List[Dict]:
        """
        Retrieve relevant chunks for a specific variant.

        Gene-specific chunks (GeneReview + gene-named PubMed files) are always
        included first. Remaining slots are filled with semantic search results
        so that increasing top_k adds broader context without diluting the
        gene-specific content with chunks from other genes.

        Args:
            gene: Gene symbol (e.g., 'SCN1A')
            variant_type: Type of variant (e.g., 'SNV', 'deletion')
            consequence: Molecular consequence (e.g., 'missense', 'nonsense')
            top_k: Number of results to return

        Returns:
            List of relevant document chunks
        """
        gene_upper = gene.upper()

        # Construct a rich query for the variant
        query = f"{gene_upper} epilepsy {consequence} variant pathogenicity treatment guidelines"

        # Add variant-type specific terms
        if "stop" in consequence.lower() or "nonsense" in consequence.lower():
            query += " loss of function truncating"
        elif "missense" in consequence.lower():
            query += " amino acid substitution protein function"
        elif "frameshift" in consequence.lower():
            query += " frameshift truncating loss of function"

        # ── Panel genes for contamination scoring ──────────────────────────────
        PANEL_GENES = {
            # Sodium channels
            "SCN1A","SCN2A","SCN3A","SCN8A","SCN9A",
            # Potassium channels
            "KCNQ2","KCNQ3",
            # GABA receptors
            "GABRA1","GABRG2",
            # mTOR pathway
            "TSC1","TSC2","DEPDC5","NPRL3",
            # Neurodevelopmental
            "CDKL5","MECP2","STXBP1","ARX","FOXG1",
            "PCDH19","SLC2A1","SLC6A1",
            "CHD2","PLCB1","PRRT2","TBC1D24","ALDH7A1",
        }

        # ── Step 1: pull gene-specific chunks directly from the index ──────────
        # Match on source filename (GeneReview files) OR gene symbol mentioned
        # in the first 300 chars of the chunk text (covers PubMed abstracts).
        # Sort by purity: GeneReview > single-gene papers > multi-gene papers.
        gene_chunks = []
        for c in self.chunks:
            in_filename = gene_upper in c["source"].upper()
            in_text = gene_upper in c["text"][:800].upper()
            if not (in_filename or in_text):
                continue

            # Count how many OTHER panel genes appear in the full text
            other_gene_count = sum(
                1 for g in PANEL_GENES
                if g != gene_upper and g in c["text"].upper()
            )
            # GeneReview files get priority 0; others ranked by contamination
            is_genereview = c["source"].startswith("genereview_")
            sort_key = (0 if is_genereview else 1, other_gene_count)

            gene_chunks.append({
                "text": c["text"],
                "source": c["source"],
                "title": c.get("title", ""),
                "chunk_id": c.get("chunk_id", ""),
                "score": 1.0,
                "_sort_key": sort_key,
            })

        # Sort: GeneReview first, then by ascending other-gene contamination
        gene_chunks.sort(key=lambda x: x.pop("_sort_key"))

        # ── Step 2: semantic search for broader context ─────────────────────────
        # Fetch extra candidates; we'll deduplicate and fill remaining slots.
        extra_k = max(top_k * 2, 20)
        semantic_results = self.retrieve(query, top_k=extra_k)

        # Exclude chunks already in gene_chunks AND GeneReview files for OTHER genes
        gene_sources = {c["source"] for c in gene_chunks}
        filtered_semantic = [
            r for r in semantic_results
            if r["source"] not in gene_sources
            and not (
                r["source"].startswith("genereview_")
                and gene_upper not in r["source"].upper()
            )
        ]

        # ── Step 3: merge — gene-specific first, then semantic fill ────────────
        combined = gene_chunks + filtered_semantic
        return combined[:top_k]

    def format_context(self, chunks: List[Dict], max_length: int = 4000) -> str:
        """
        Format retrieved chunks into a context string for the LLM.

        Args:
            chunks: List of chunk dictionaries from retrieve()
            max_length: Maximum character length of context

        Returns:
            Formatted context string with source citations
        """
        if not chunks:
            return "No relevant context found in the knowledge base."

        context_parts = []
        current_length = 0

        for i, chunk in enumerate(chunks, 1):
            # Format each chunk with citation
            chunk_text = f"[Source {i}: {chunk['source']}]\n{chunk['text']}\n"

            # Check length
            if current_length + len(chunk_text) > max_length:
                break

            context_parts.append(chunk_text)
            current_length += len(chunk_text)

        return "\n---\n".join(context_parts)

    def add_documents(self, documents: List[Dict]) -> bool:
        """
        Add new documents to the FAISS index and save.

        Args:
            documents: List of document dictionaries with 'text' and 'metadata' keys
                      Example: [{"text": "...", "metadata": {"source": "...", ...}}]

        Returns:
            True if documents were added successfully, False otherwise
        """
        if not self._loaded:
            raise RuntimeError("Retriever not loaded. Call load() first.")

        try:
            # Encode new documents
            texts = [doc["text"] for doc in documents]
            print(f"Encoding {len(texts)} new documents...")

            embeddings = self.model.encode(
                texts,
                normalize_embeddings=True,
                show_progress_bar=True,
                batch_size=32
            )
            embeddings = np.array(embeddings, dtype=np.float32)

            # Add to FAISS index
            print(f"Adding {len(embeddings)} vectors to FAISS index...")
            self.index.add(embeddings)

            # Create chunk metadata and add to chunks list
            starting_id = len(self.chunks)
            for i, doc in enumerate(documents):
                chunk_data = {
                    "text": doc["text"],
                    "source": doc["metadata"].get("source", "unknown"),
                    "title": doc["metadata"].get("title", ""),
                    "chunk_id": f"chunk_{starting_id + i}",
                }
                # Add any additional metadata
                chunk_data.update(doc["metadata"])
                self.chunks.append(chunk_data)

            # Save updated index and chunks
            print(f"Saving updated index to {self.index_path}...")
            faiss.write_index(self.index, str(self.index_path))

            print(f"Saving updated chunks to {self.chunks_path}...")
            with open(self.chunks_path, 'w', encoding='utf-8') as f:
                json.dump(self.chunks, f, indent=2, ensure_ascii=False)

            print(f"Successfully added {len(documents)} documents to knowledge base")
            print(f"Total vectors in index: {self.index.ntotal}")
            print(f"Total chunks: {len(self.chunks)}")

            return True

        except Exception as e:
            print(f"Error adding documents to knowledge base: {e}")
            return False

    def get_stats(self) -> Dict:
        """
        Get statistics about the loaded knowledge base.

        Returns:
            Dictionary with index statistics
        """
        if not self._loaded:
            return {"loaded": False}

        return {
            "loaded": True,
            "total_vectors": self.index.ntotal if self.index else 0,
            "total_chunks": len(self.chunks),
            "embedding_model": self.model_name,
            "index_path": str(self.index_path),
            "chunks_path": str(self.chunks_path)
        }


# Singleton instance for reuse
_retriever_instance: Optional[RAGRetriever] = None


def get_retriever() -> RAGRetriever:
    """
    Get or create the singleton RAGRetriever instance.

    Returns:
        Loaded RAGRetriever instance
    """
    global _retriever_instance

    if _retriever_instance is None:
        _retriever_instance = RAGRetriever()
        _retriever_instance.load()

    return _retriever_instance
