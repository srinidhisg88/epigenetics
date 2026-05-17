#!/usr/bin/env python3
"""
Build FAISS vector index from knowledge base documents.
Run this once after fetching PubMed abstracts.

Output:
- data/faiss_index/index.faiss
- data/faiss_index/chunks.json
"""

import os
import json
import re
from pathlib import Path
from typing import List, Dict, Tuple
import numpy as np

# Sentence transformers for embeddings
from sentence_transformers import SentenceTransformer

# FAISS for vector storage
import faiss


def load_documents(knowledge_base_dir: Path) -> List[Dict]:
    """
    Load all documents from the knowledge base directory.

    Args:
        knowledge_base_dir: Path to knowledge_base directory

    Returns:
        List of dictionaries with 'text', 'source', 'title' keys
    """
    documents = []

    # Load GeneReviews chapters (authoritative per-gene clinical summaries)
    genereview_dir = knowledge_base_dir / "genereview"
    if genereview_dir.exists():
        gr_files = sorted(genereview_dir.glob("genereview_*.txt"))
        for filepath in gr_files:
            print(f"Loading GeneReview: {filepath.name}")
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
            # Extract title from file content
            title_match = re.search(r'Title: (.+)', content)
            title = title_match.group(1).strip() if title_match else filepath.stem
            documents.append({
                "text": content,
                "source": filepath.name,
                "title": title,
                "type": "genereview"
            })

    # Load treatment guidelines (LLM-generated fallback, kept for backwards compat)
    guidelines_path = knowledge_base_dir / "treatment_guidelines.txt"
    if guidelines_path.exists():
        print(f"Loading: {guidelines_path}")
        with open(guidelines_path, 'r', encoding='utf-8') as f:
            content = f.read()
        documents.append({
            "text": content,
            "source": "treatment_guidelines.txt",
            "title": "Epilepsy Gene Treatment Guidelines",
            "type": "guidelines"
        })

    # Load PubMed abstracts
    pubmed_dir = knowledge_base_dir / "pubmed_abstracts"
    if pubmed_dir.exists():
        for filepath in pubmed_dir.glob("pmid_*.txt"):
            print(f"Loading: {filepath.name}")
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()

            # Extract title from content
            title_match = re.search(r'Title: (.+)', content)
            title = title_match.group(1) if title_match else filepath.stem

            documents.append({
                "text": content,
                "source": filepath.name,
                "title": title,
                "type": "pubmed"
            })

    # Load ClinVar epilepsy data if exists
    clinvar_path = knowledge_base_dir / "clinvar_epilepsy.txt"
    if clinvar_path.exists():
        print(f"Loading: {clinvar_path}")
        with open(clinvar_path, 'r', encoding='utf-8') as f:
            content = f.read()
        documents.append({
            "text": content,
            "source": "clinvar_epilepsy.txt",
            "title": "ClinVar Epilepsy Variants",
            "type": "clinvar"
        })

    # Load any other .txt files
    for filepath in knowledge_base_dir.glob("*.txt"):
        if filepath.name not in ["treatment_guidelines.txt", "clinvar_epilepsy.txt"]:
            print(f"Loading: {filepath.name}")
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
            documents.append({
                "text": content,
                "source": filepath.name,
                "title": filepath.stem,
                "type": "other"
            })

    print(f"\nTotal documents loaded: {len(documents)}")
    return documents


def chunk_text(text: str, chunk_size: int = 512, overlap: int = 50) -> List[str]:
    """
    Split text into overlapping chunks.

    Args:
        text: Input text
        chunk_size: Target chunk size in tokens (approximated as words * 1.3)
        overlap: Number of tokens to overlap between chunks

    Returns:
        List of text chunks
    """
    # Approximate tokens as words * 1.3
    words = text.split()
    target_words = int(chunk_size / 1.3)
    overlap_words = int(overlap / 1.3)

    if len(words) <= target_words:
        return [text]

    chunks = []
    start = 0

    while start < len(words):
        end = min(start + target_words, len(words))
        chunk = ' '.join(words[start:end])
        chunks.append(chunk)

        if end >= len(words):
            break

        start = end - overlap_words

    return chunks


def chunk_documents(documents: List[Dict]) -> List[Dict]:
    """
    Chunk all documents into smaller pieces.

    Args:
        documents: List of document dictionaries

    Returns:
        List of chunk dictionaries with 'text', 'source', 'chunk_id', 'title'
    """
    all_chunks = []

    for doc in documents:
        # For treatment guidelines, split by gene section
        if doc["type"] in ("guidelines", "genereview"):
            sections = re.split(r'={3,}', doc["text"])
            for i, section in enumerate(sections):
                section = section.strip()
                if len(section) > 100:
                    sub_chunks = chunk_text(section, chunk_size=512, overlap=50)
                    for j, chunk in enumerate(sub_chunks):
                        all_chunks.append({
                            "text": chunk,
                            "source": doc["source"],
                            "title": doc["title"],
                            "chunk_id": f"{doc['source']}_section{i}_chunk{j}"
                        })
        else:
            # Regular chunking for other documents
            chunks = chunk_text(doc["text"], chunk_size=512, overlap=50)
            for i, chunk in enumerate(chunks):
                all_chunks.append({
                    "text": chunk,
                    "source": doc["source"],
                    "title": doc["title"],
                    "chunk_id": f"{doc['source']}_chunk{i}"
                })

    print(f"Total chunks created: {len(all_chunks)}")
    return all_chunks


def build_faiss_index(chunks: List[Dict], model_name: str = "pritamdeka/S-PubMedBert-MS-MARCO") -> Tuple[faiss.Index, List[Dict]]:
    """
    Build FAISS index from document chunks.

    Args:
        chunks: List of chunk dictionaries
        model_name: Sentence transformer model name

    Returns:
        Tuple of (FAISS index, chunk metadata list)
    """
    print(f"\nLoading embedding model: {model_name}")
    model = SentenceTransformer(model_name)

    print("Generating embeddings...")
    texts = [chunk["text"] for chunk in chunks]

    # Generate embeddings in batches
    batch_size = 32
    all_embeddings = []

    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]
        embeddings = model.encode(batch, show_progress_bar=False, normalize_embeddings=True)
        all_embeddings.extend(embeddings)

        if (i + batch_size) % 100 == 0:
            print(f"  Processed {min(i + batch_size, len(texts))}/{len(texts)} chunks")

    embeddings_array = np.array(all_embeddings, dtype=np.float32)
    print(f"Embeddings shape: {embeddings_array.shape}")

    # Build FAISS index (Inner Product for cosine similarity with normalized vectors)
    dimension = embeddings_array.shape[1]
    index = faiss.IndexFlatIP(dimension)
    index.add(embeddings_array)

    print(f"FAISS index built with {index.ntotal} vectors")

    # Prepare chunk metadata (without the full text to save space in JSON)
    chunk_metadata = []
    for i, chunk in enumerate(chunks):
        chunk_metadata.append({
            "index": i,
            "text": chunk["text"],
            "source": chunk["source"],
            "title": chunk["title"],
            "chunk_id": chunk["chunk_id"]
        })

    return index, chunk_metadata


def main():
    """Main function to build the knowledge base index."""

    # Setup paths
    script_dir = Path(__file__).parent.parent
    knowledge_base_dir = script_dir / "data" / "knowledge_base"
    output_dir = script_dir / "data" / "faiss_index"
    output_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("Building FAISS Knowledge Base Index")
    print("=" * 60)
    print(f"\nKnowledge base directory: {knowledge_base_dir}")
    print(f"Output directory: {output_dir}")

    # Check if knowledge base exists
    if not knowledge_base_dir.exists():
        print(f"\nError: Knowledge base directory not found: {knowledge_base_dir}")
        print("Please run fetch_pubmed.py first to download PubMed abstracts.")
        return

    # Load documents
    print("\n[1/4] Loading documents...")
    documents = load_documents(knowledge_base_dir)

    if not documents:
        print("No documents found in knowledge base!")
        return

    # Chunk documents
    print("\n[2/4] Chunking documents...")
    chunks = chunk_documents(documents)

    # Build FAISS index
    print("\n[3/4] Building FAISS index...")
    index, chunk_metadata = build_faiss_index(chunks)

    # Save index and metadata
    print("\n[4/4] Saving index and metadata...")

    index_path = output_dir / "index.faiss"
    faiss.write_index(index, str(index_path))
    print(f"  Saved FAISS index: {index_path}")

    chunks_path = output_dir / "chunks.json"
    with open(chunks_path, 'w', encoding='utf-8') as f:
        json.dump(chunk_metadata, f, indent=2)
    print(f"  Saved chunk metadata: {chunks_path}")

    # Save build info
    info_path = output_dir / "build_info.json"
    build_info = {
        "total_documents": len(documents),
        "total_chunks": len(chunks),
        "embedding_model": "pritamdeka/S-PubMedBert-MS-MARCO",
        "embedding_dimension": index.d,
        "index_type": "IndexFlatIP (cosine similarity)",
        "build_date": __import__('datetime').datetime.now().isoformat()
    }
    with open(info_path, 'w', encoding='utf-8') as f:
        json.dump(build_info, f, indent=2)
    print(f"  Saved build info: {info_path}")

    print("\n" + "=" * 60)
    print("Knowledge base index built successfully!")
    print(f"  Total documents: {len(documents)}")
    print(f"  Total chunks: {len(chunks)}")
    print(f"  Index vectors: {index.ntotal}")
    print("=" * 60)


if __name__ == "__main__":
    main()
