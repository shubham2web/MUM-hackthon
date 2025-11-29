# RAG Evidence Module for ATLAS v4.1.3
"""
Hybrid RAG (BM25 + Embedding Search) integration for evidence retrieval.

This module provides structured evidence retrieval that feeds directly
into the neutral verdict engine pipeline.

Key exports:
- RAGEvidenceRetriever: Main retriever class
- get_rag_retriever: Singleton accessor
- process_scraper_results: Central adapter for scraper → evidence bundle
- build_evidence_prompt: LLM system prompt builder
"""

from .evidence_retriever import RAGEvidenceRetriever, get_rag_retriever
from .adapter import (
    process_scraper_results,
    build_evidence_prompt,
    format_assistant_with_citations,
    normalize_url,
    compute_url_hash,
    sanitize_snippet
)

__all__ = [
    'RAGEvidenceRetriever', 
    'get_rag_retriever',
    'process_scraper_results',
    'build_evidence_prompt',
    'format_assistant_with_citations',
    'normalize_url',
    'compute_url_hash',
    'sanitize_snippet'
]
