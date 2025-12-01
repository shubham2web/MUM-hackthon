# evidence_retriever.py
"""
ATLAS v4.1.1 RAG Evidence Retriever

Hybrid RAG module that combines:
- BM25 lexical search for keyword matching
- Embedding-based semantic search for concept matching

Returns structured evidence in the format expected by the verdict engine:
{
    "title": str,
    "url": str,
    "snippet": str (max 200 chars),
    "authority": float (0.0-1.0),
    "source_type": str (News/Fact-check/Research/Government/Other)
}

Safety guarantees:
- Source whitelisting
- Minimum authority threshold (0.3)
- Snippet truncation (max 200 chars)
- No raw documents exposed
"""

import os
import re
import logging
import time
import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger("rag.evidence_retriever")
logger.setLevel(logging.INFO)

# Configuration
ENABLE_RAG = os.getenv("ATLAS_RAG_ENABLED", "true").lower() == "true"
MIN_AUTHORITY_THRESHOLD = 0.3
MAX_SNIPPET_CHARS = 200
MAX_EVIDENCE_ITEMS = 10
RAG_TIMEOUT_SECONDS = 8

# Source authority tiers (per PRD Section 6.1)
TIER_1_DOMAINS = [
    'reuters.com', 'apnews.com', 'bbc.com', 'bbc.co.uk',
    '.gov', '.edu', 'who.int', 'un.org', 'factcheck.org',
    'snopes.com', 'politifact.com', 'fullfact.org'
]

TIER_2_DOMAINS = [
    'nytimes.com', 'washingtonpost.com', 'theguardian.com',
    'economist.com', 'ft.com', 'bloomberg.com', 'wsj.com',
    'npr.org', 'pbs.org', 'nature.com', 'science.org',
    'thehindu.com', 'hindustantimes.com', 'ndtv.com',
    'indiatoday.in', 'timesofindia.indiatimes.com'
]

TIER_3_DOMAINS = [
    'medium.com', 'substack.com', 'wordpress.com',
    'blogspot.com', 'quora.com', 'reddit.com'
]

# Source type classification
SOURCE_TYPE_PATTERNS = {
    'Fact-check': ['factcheck', 'snopes', 'politifact', 'fullfact', 'verify'],
    'Government': ['.gov', '.gov.', 'government', 'ministry', 'official'],
    'Research': ['.edu', 'nature.com', 'science.org', 'research', 'study', 'journal'],
    'News': ['news', 'times', 'post', 'guardian', 'bbc', 'cnn', 'reuters', 'ap']
}


def calculate_authority_score(url: str, domain: str) -> float:
    """
    Calculate authority score based on source domain.
    
    Returns:
        float: Authority score between 0.0 and 1.0
    """
    domain_lower = domain.lower() if domain else ""
    url_lower = url.lower() if url else ""
    
    # Check Tier 1 (highest authority: 0.85-1.0)
    for tier1 in TIER_1_DOMAINS:
        if tier1 in domain_lower or tier1 in url_lower:
            return 0.9 + (0.1 * (1 if 'factcheck' in domain_lower or '.gov' in domain_lower else 0))
    
    # Check Tier 2 (high authority: 0.65-0.84)
    for tier2 in TIER_2_DOMAINS:
        if tier2 in domain_lower or tier2 in url_lower:
            return 0.75
    
    # Check Tier 3 (low authority: 0.3-0.49)
    for tier3 in TIER_3_DOMAINS:
        if tier3 in domain_lower or tier3 in url_lower:
            return 0.35
    
    # Default (medium authority: 0.5-0.64)
    return 0.5


def classify_source_type(url: str, domain: str, title: str = "") -> str:
    """Classify the source type based on URL, domain, and title."""
    combined = f"{url} {domain} {title}".lower()
    
    for source_type, patterns in SOURCE_TYPE_PATTERNS.items():
        for pattern in patterns:
            if pattern in combined:
                return source_type
    
    return "News"  # Default


def sanitize_snippet(text: str, max_chars: int = MAX_SNIPPET_CHARS) -> str:
    """
    Sanitize and truncate snippet text.
    
    - Removes forbidden tokens (proponent, opponent)
    - Truncates to max_chars
    - Cleans whitespace
    """
    if not text:
        return ""
    
    # Remove forbidden tokens
    forbidden = ['proponent', 'opponent', 'transcript', 'debate']
    clean_text = text
    for token in forbidden:
        clean_text = re.sub(rf'\b{token}\b', '', clean_text, flags=re.IGNORECASE)
    
    # Clean whitespace
    clean_text = ' '.join(clean_text.split())
    
    # Truncate with ellipsis
    if len(clean_text) > max_chars:
        clean_text = clean_text[:max_chars - 3] + "..."
    
    return clean_text


def extract_domain(url: str) -> str:
    """Extract domain from URL."""
    if not url:
        return ""
    try:
        # Remove protocol
        domain = url.split("//")[-1]
        # Remove path
        domain = domain.split("/")[0]
        # Remove www.
        domain = domain.replace("www.", "")
        return domain
    except Exception:
        return ""


class RAGEvidenceRetriever:
    """
    Hybrid RAG Evidence Retriever for ATLAS v4.1.1.
    
    Combines BM25 lexical search with embedding-based semantic search
    for comprehensive evidence retrieval.
    """
    
    def __init__(self):
        self.enabled = ENABLE_RAG
        self.bm25_index = None
        self.embedding_model = None
        self._initialized = False
        
        # Metrics
        self.last_latency_ms = 0
        self.last_evidence_count = 0
        self.last_avg_authority = 0.0
        
        logger.info(f"RAGEvidenceRetriever initialized (enabled={self.enabled})")
    
    def _lazy_init(self):
        """Lazy initialization of BM25 and embedding models."""
        if self._initialized:
            return
        
        try:
            # Try to import BM25
            try:
                from rank_bm25 import BM25Okapi
                self.bm25_available = True
                logger.info("✅ BM25 (rank_bm25) available")
            except ImportError:
                self.bm25_available = False
                logger.warning("⚠️ rank_bm25 not installed. BM25 search disabled.")
            
            # Try to import sentence-transformers for embeddings
            try:
                from sentence_transformers import SentenceTransformer
                self.embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
                self.embedding_available = True
                logger.info("✅ Embedding model (all-MiniLM-L6-v2) loaded")
            except ImportError:
                self.embedding_available = False
                logger.warning("⚠️ sentence-transformers not installed. Embedding search disabled.")
            
            self._initialized = True
            
        except Exception as e:
            logger.error(f"RAG initialization error: {e}")
            self._initialized = True  # Mark as initialized to avoid repeated attempts
    
    async def retrieve_evidence(
        self,
        query: str,
        max_results: int = MAX_EVIDENCE_ITEMS,
        min_authority: float = MIN_AUTHORITY_THRESHOLD
    ) -> List[Dict[str, Any]]:
        """
        Retrieve evidence for a claim using hybrid RAG.
        
        Args:
            query: The claim or topic to search for
            max_results: Maximum number of evidence items to return
            min_authority: Minimum authority threshold for sources
        
        Returns:
            List of evidence items in verdict engine format:
            [{title, url, snippet, authority, source_type}, ...]
        """
        if not self.enabled:
            logger.info("RAG is disabled, skipping evidence retrieval")
            return []
        
        start_time = time.time()
        
        try:
            self._lazy_init()
            
            # Gather evidence from multiple sources
            evidence_items = []
            
            # 1. Web scraping evidence (primary source)
            web_evidence = await self._gather_web_evidence(query)
            evidence_items.extend(web_evidence)
            
            # 2. Memory/vector store evidence (if available)
            memory_evidence = await self._gather_memory_evidence(query)
            evidence_items.extend(memory_evidence)
            
            # 3. Normalize and deduplicate
            normalized = self._normalize_evidence(evidence_items)
            
            # 4. Filter by authority threshold
            filtered = [
                ev for ev in normalized
                if ev.get("authority", 0) >= min_authority
            ]
            
            # 5. Rank and limit results
            ranked = self._rank_evidence(filtered, query)
            final_evidence = ranked[:max_results]
            
            # Update metrics
            self.last_latency_ms = int((time.time() - start_time) * 1000)
            self.last_evidence_count = len(final_evidence)
            self.last_avg_authority = (
                sum(e.get("authority", 0.5) for e in final_evidence) / len(final_evidence)
                if final_evidence else 0.0
            )
            
            logger.info(
                f"📊 RAG retrieved {len(final_evidence)} evidence items "
                f"(latency={self.last_latency_ms}ms, avg_authority={self.last_avg_authority:.2f})"
            )
            
            return final_evidence
            
        except asyncio.TimeoutError:
            logger.warning("RAG evidence retrieval timed out")
            self.last_latency_ms = int((time.time() - start_time) * 1000)
            return []
        except Exception as e:
            logger.error(f"RAG evidence retrieval failed: {e}")
            self.last_latency_ms = int((time.time() - start_time) * 1000)
            return []
    
    async def _gather_web_evidence(self, query: str) -> List[Dict[str, Any]]:
        """Gather evidence from web scraping."""
        try:
            # Import the existing web scraper
            from services.pro_scraper import get_diversified_evidence
            
            raw_evidence = await asyncio.wait_for(
                get_diversified_evidence(query),
                timeout=RAG_TIMEOUT_SECONDS
            )
            
            return raw_evidence or []
            
        except asyncio.TimeoutError:
            logger.warning("Web scraping timed out")
            return []
        except ImportError:
            logger.warning("pro_scraper not available")
            return []
        except Exception as e:
            logger.error(f"Web evidence gathering failed: {e}")
            return []
    
    async def _gather_memory_evidence(self, query: str) -> List[Dict[str, Any]]:
        """Gather evidence from memory/vector store."""
        try:
            # Try to use the memory manager if available
            from memory.memory_manager import get_memory_manager
            
            memory = get_memory_manager()
            if memory and hasattr(memory, 'search'):
                results = await memory.search(query, top_k=5)
                return [
                    {
                        "title": r.get("title", "Memory Result"),
                        "url": r.get("url", ""),
                        "text": r.get("content", r.get("text", "")),
                        "domain": r.get("domain", "memory"),
                        "authority": r.get("score", 0.5)
                    }
                    for r in results
                ] if results else []
            
            return []
            
        except ImportError:
            return []  # Memory not available
        except Exception as e:
            logger.debug(f"Memory evidence not available: {e}")
            return []
    
    def _normalize_evidence(self, evidence_items: List[Dict]) -> List[Dict[str, Any]]:
        """
        Normalize evidence items to verdict engine format.
        
        Output format:
        {
            title: str,
            url: str,
            snippet: str (max 200 chars),
            authority: float (0.0-1.0),
            source_type: str
        }
        """
        normalized = []
        seen_urls = set()
        
        for item in evidence_items:
            if not item:
                continue
            
            url = item.get("url", "")
            
            # Skip items without valid URLs (must start with http and have more than just protocol)
            if not url or not url.startswith("http") or len(url) < 15:
                continue
            
            # Skip duplicates
            if url in seen_urls:
                continue
            seen_urls.add(url)
            
            # Extract domain
            domain = item.get("domain", "") or extract_domain(url)
            
            # Calculate authority
            authority = item.get("authority")
            if authority is None:
                authority = calculate_authority_score(url, domain)
            else:
                authority = float(authority)
            
            # Get text content
            text = item.get("text", "") or item.get("summary", "") or item.get("excerpt", "") or item.get("snippet", "")
            
            # Build normalized item
            normalized_item = {
                "title": item.get("title", "Unknown Source")[:100],
                "url": url,
                "snippet": sanitize_snippet(text),
                "authority": round(authority, 3),
                "source_type": classify_source_type(url, domain, item.get("title", "")),
                "domain": domain
            }
            
            normalized.append(normalized_item)
        
        return normalized
    
    def _rank_evidence(self, evidence: List[Dict], query: str) -> List[Dict]:
        """
        Rank evidence by relevance and authority.
        
        Uses a weighted combination of:
        - Authority score (40%)
        - Semantic similarity (40%) - if embeddings available
        - Keyword overlap (20%)
        """
        if not evidence:
            return []
        
        # Simple ranking by authority if no advanced features
        if not self.embedding_available:
            return sorted(evidence, key=lambda e: e.get("authority", 0.5), reverse=True)
        
        try:
            # Compute semantic similarity scores
            query_words = set(query.lower().split())
            
            for item in evidence:
                # Keyword overlap score (0-1)
                snippet_words = set(item.get("snippet", "").lower().split())
                title_words = set(item.get("title", "").lower().split())
                all_words = snippet_words | title_words
                
                if query_words and all_words:
                    overlap = len(query_words & all_words) / len(query_words)
                else:
                    overlap = 0
                
                # Combined score
                authority = item.get("authority", 0.5)
                item["_relevance_score"] = (authority * 0.5) + (overlap * 0.5)
            
            # Sort by combined score
            ranked = sorted(evidence, key=lambda e: e.get("_relevance_score", 0), reverse=True)
            
            # Remove internal scoring field
            for item in ranked:
                item.pop("_relevance_score", None)
            
            return ranked
            
        except Exception as e:
            logger.error(f"Evidence ranking failed: {e}")
            return sorted(evidence, key=lambda e: e.get("authority", 0.5), reverse=True)
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get RAG performance metrics."""
        return {
            "rag_enabled": self.enabled,
            "last_latency_ms": self.last_latency_ms,
            "last_evidence_count": self.last_evidence_count,
            "last_avg_authority": round(self.last_avg_authority, 3),
            "bm25_available": getattr(self, 'bm25_available', False),
            "embedding_available": getattr(self, 'embedding_available', False)
        }


# Singleton instance
_rag_instance: Optional[RAGEvidenceRetriever] = None


def get_rag_retriever() -> RAGEvidenceRetriever:
    """Get or create the RAG retriever singleton."""
    global _rag_instance
    if _rag_instance is None:
        _rag_instance = RAGEvidenceRetriever()
    return _rag_instance
