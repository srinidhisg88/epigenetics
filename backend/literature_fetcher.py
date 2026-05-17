"""
Literature Fetcher module for Epilepsy Diagnostic Assistant.

Fetches recent publications from PubMed and optionally updates the RAG knowledge base.
"""

import os
import json
import hashlib
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from pathlib import Path

import requests
from Bio import Entrez
from dotenv import load_dotenv

from rag.retriever import get_retriever
from rag.generator import get_generator

# Load environment variables
load_dotenv()

# Configure Entrez with your email
Entrez.email = os.getenv("ENTREZ_EMAIL", "your_email@example.com")
Entrez.api_key = os.getenv("NCBI_API_KEY")  # Optional but recommended for higher rate limits

# Cache directory
CACHE_DIR = Path("cache/literature")
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# Cache TTL
CACHE_TTL_HOURS = 24


class LiteratureFetcher:
    """
    Fetches recent literature from PubMed and manages caching.
    """

    def __init__(self, update_rag: bool = True):
        """
        Initialize the Literature Fetcher.

        Args:
            update_rag: Whether to update RAG knowledge base with new papers
        """
        self.update_rag = update_rag
        self.generator = get_generator() if update_rag else None
        self.retriever = get_retriever() if update_rag else None

    def _get_cache_path(self, gene: str) -> Path:
        """Get cache file path for a gene."""
        cache_key = hashlib.md5(gene.encode()).hexdigest()
        return CACHE_DIR / f"{gene}_{cache_key}.json"

    def _is_cache_valid(self, cache_path: Path) -> bool:
        """Check if cache file exists and is still valid (within TTL)."""
        if not cache_path.exists():
            return False

        try:
            with open(cache_path, 'r') as f:
                cache_data = json.load(f)
                cache_time = datetime.fromisoformat(cache_data.get("cached_at", "2000-01-01"))
                return datetime.now() - cache_time < timedelta(hours=CACHE_TTL_HOURS)
        except Exception:
            return False

    def _load_from_cache(self, cache_path: Path) -> Optional[List[Dict]]:
        """Load papers from cache file."""
        try:
            with open(cache_path, 'r') as f:
                cache_data = json.load(f)
                return cache_data.get("papers", [])
        except Exception as e:
            print(f"Error loading cache: {e}")
            return None

    def _save_to_cache(self, cache_path: Path, papers: List[Dict]) -> None:
        """Save papers to cache file."""
        try:
            cache_data = {
                "cached_at": datetime.now().isoformat(),
                "papers": papers
            }
            with open(cache_path, 'w') as f:
                json.dump(cache_data, f, indent=2)
        except Exception as e:
            print(f"Error saving cache: {e}")

    def fetch_pubmed_papers(
        self,
        gene: str,
        max_results: int = 20,
        months_back: int = 6
    ) -> List[Dict]:
        """
        Fetch recent papers from PubMed for a specific gene.

        Args:
            gene: Gene symbol (e.g., 'SCN1A')
            max_results: Maximum number of papers to fetch
            months_back: How many months back to search

        Returns:
            List of paper dictionaries
        """
        # Check cache first
        cache_path = self._get_cache_path(gene)
        if self._is_cache_valid(cache_path):
            print(f"Loading papers for {gene} from cache...")
            cached_papers = self._load_from_cache(cache_path)
            if cached_papers:
                return cached_papers

        print(f"Fetching fresh papers for {gene} from PubMed...")

        # Calculate date range
        end_date = datetime.now()
        start_date = end_date - timedelta(days=months_back * 30)

        # Build PubMed query
        query = f"({gene}[Title/Abstract]) AND (epilepsy[Title/Abstract]) AND ({start_date.strftime('%Y/%m/%d')}:{end_date.strftime('%Y/%m/%d')}[Date - Publication])"

        try:
            # Search PubMed
            handle = Entrez.esearch(
                db="pubmed",
                term=query,
                retmax=max_results,
                sort="pub_date"
            )
            search_results = Entrez.read(handle)
            handle.close()

            pmids = search_results["IdList"]

            if not pmids:
                print(f"No papers found for {gene}")
                return []

            # Fetch paper details
            handle = Entrez.efetch(
                db="pubmed",
                id=pmids,
                rettype="abstract",
                retmode="xml"
            )
            papers_data = Entrez.read(handle)
            handle.close()

            papers = []
            for article_data in papers_data['PubmedArticle']:
                try:
                    article = article_data['MedlineCitation']['Article']
                    pmid = str(article_data['MedlineCitation']['PMID'])

                    # Extract title — strip HTML italic tags PubMed wraps gene names in
                    import re as _re
                    raw_title = article.get('ArticleTitle', 'No title')
                    title = _re.sub(r'<[^>]+>', '', str(raw_title)).strip()

                    # Extract abstract
                    abstract_parts = article.get('Abstract', {}).get('AbstractText', [])
                    if isinstance(abstract_parts, list):
                        abstract = ' '.join([str(part) for part in abstract_parts])
                    else:
                        abstract = str(abstract_parts)

                    # Extract authors
                    author_list = article.get('AuthorList', [])
                    authors = []
                    for author in author_list[:3]:  # First 3 authors
                        lastname = author.get('LastName', '')
                        initials = author.get('Initials', '')
                        if lastname:
                            authors.append(f"{lastname} {initials}")

                    if len(author_list) > 3:
                        authors.append("et al.")

                    # Extract journal and date
                    journal = article.get('Journal', {}).get('Title', 'Unknown Journal')
                    pub_date = article.get('Journal', {}).get('JournalIssue', {}).get('PubDate', {})
                    year = pub_date.get('Year', '')
                    month = pub_date.get('Month', '')
                    pub_date_str = f"{month} {year}" if month and year else year

                    # Determine publication type
                    pub_types = article.get('PublicationTypeList', [])
                    category = self._categorize_paper(pub_types)

                    # Generate AI summary
                    summary = self._generate_summary(title, abstract, gene)

                    paper = {
                        "pmid": pmid,
                        "title": title,
                        "authors": ", ".join(authors),
                        "journal": journal,
                        "pub_date": pub_date_str,
                        "abstract": abstract,
                        "summary": summary,
                        "category": category,
                        "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
                    }

                    papers.append(paper)

                except Exception as e:
                    print(f"Error processing article: {e}")
                    continue

            # Sort by category priority (Meta-analysis > RCT > Review > Case Study > Other)
            category_priority = {
                "Meta-analysis": 0,
                "Randomized Controlled Trial": 1,
                "Systematic Review": 2,
                "Review": 3,
                "Case Report": 4,
                "Other": 5
            }
            papers.sort(key=lambda p: category_priority.get(p['category'], 999))

            # Save to cache
            self._save_to_cache(cache_path, papers)

            # Update RAG knowledge base if enabled
            if self.update_rag and papers:
                self._update_knowledge_base(papers, gene)

            return papers

        except Exception as e:
            print(f"Error fetching papers from PubMed: {e}")
            return []

    def _categorize_paper(self, pub_types: List) -> str:
        """
        Categorize paper based on publication type.

        Args:
            pub_types: List of publication type strings

        Returns:
            Category string
        """
        pub_type_str = " ".join([str(pt) for pt in pub_types]).lower()

        if "meta-analysis" in pub_type_str:
            return "Meta-analysis"
        elif "randomized controlled trial" in pub_type_str or "rct" in pub_type_str:
            return "Randomized Controlled Trial"
        elif "systematic review" in pub_type_str:
            return "Systematic Review"
        elif "review" in pub_type_str:
            return "Review"
        elif "case report" in pub_type_str:
            return "Case Report"
        else:
            return "Other"

    def _generate_summary(self, title: str, abstract: str, gene: str) -> str:
        """
        Generate AI summary of paper using LLM.

        Args:
            title: Paper title
            abstract: Paper abstract
            gene: Gene symbol

        Returns:
            AI-generated summary string
        """
        if not self.generator or not abstract or len(abstract) < 50:
            return "No summary available"

        try:
            return self.generator.summarize_paper(title, abstract, gene, max_tokens=200)

        except Exception as e:
            print(f"Error generating summary: {e}")
            return "Summary generation failed"

    def _update_knowledge_base(self, papers: List[Dict], gene: str) -> None:
        """
        Update RAG knowledge base with new papers.

        Args:
            papers: List of paper dictionaries
            gene: Gene symbol
        """
        if not self.retriever:
            return

        print(f"\nUpdating RAG knowledge base with {len(papers)} papers for {gene}...")

        try:
            # Prepare documents for ingestion
            new_docs = []
            for paper in papers:
                # Create document text combining title and abstract
                doc_text = f"Title: {paper['title']}\n\n{paper['abstract']}\n\nSource: {paper['url']}"

                # Add metadata
                metadata = {
                    "source": paper['url'],
                    "title": paper['title'],
                    "pmid": paper['pmid'],
                    "gene": gene,
                    "pub_date": paper['pub_date'],
                    "category": paper['category'],
                    "type": "pubmed_article",
                    "authors": paper.get('authors', ''),
                    "journal": paper.get('journal', '')
                }

                new_docs.append({
                    "text": doc_text,
                    "metadata": metadata
                })

            # Add to FAISS index
            if hasattr(self.retriever, 'add_documents'):
                success = self.retriever.add_documents(new_docs)
                if success:
                    print(f"✓ Successfully added {len(new_docs)} documents to knowledge base\n")
                else:
                    print(f"✗ Failed to add documents to knowledge base\n")
            else:
                print("Warning: Retriever does not support add_documents method")

        except Exception as e:
            print(f"Error updating knowledge base: {e}")


# Singleton instance
_fetcher_instance: Optional[LiteratureFetcher] = None


def get_literature_fetcher(update_rag: bool = True) -> LiteratureFetcher:
    """
    Get or create singleton LiteratureFetcher instance.

    Args:
        update_rag: Whether to update RAG knowledge base

    Returns:
        LiteratureFetcher instance
    """
    global _fetcher_instance

    if _fetcher_instance is None:
        _fetcher_instance = LiteratureFetcher(update_rag=update_rag)

    return _fetcher_instance
