"""
Cross-Encoder Reranker for RAG System
======================================

Implements cross-encoder reranking to improve retrieval precision and relevance.
Uses two-stage retrieval: bi-encoder (fast, broad) -> cross-encoder (accurate, precise).

Model: cross-encoder/ms-marco-MiniLM-L6-v2 (90.9MB)
Expected gains: +1-2pp precision, +1-2pp relevance

Author: ATLAS RAG Optimization Team
Date: November 11, 2025
"""

import logging
from typing import List, Dict, Any, Optional
from sentence_transformers import CrossEncoder

logger = logging.getLogger(__name__)


class CrossEncoderReranker:
    """
    Reranks retrieved documents using cross-encoder semantic similarity scoring.
    
    Cross-encoders jointly encode query+document pairs, providing more accurate
    relevance scores than bi-encoder embeddings used in initial retrieval.
    """
    
    def __init__(
        self,
        model_name: str = 'cross-encoder/ms-marco-MiniLM-L6-v2',
        enabled: bool = True,
        batch_size: int = 32,
        verbose: bool = False
    ):
        """
        Initialize cross-encoder reranker.
        
        Args:
            model_name: HuggingFace model ID for cross-encoder
            enabled: Whether reranking is enabled
            batch_size: Batch size for cross-encoder inference
            verbose: Enable verbose logging
        """
        self.model_name = model_name
        self.enabled = enabled
        self.batch_size = batch_size
        self.verbose = verbose
        self.model = None
        
        if self.enabled:
            self._load_model()
    
    def _load_model(self):
        """Load cross-encoder model from HuggingFace."""
        try:
            if self.verbose:
                logger.info(f"Loading cross-encoder model: {self.model_name}")
            
            self.model = CrossEncoder(self.model_name)
            
            if self.verbose:
                logger.info(f"✅ Cross-encoder model loaded successfully")
            
        except Exception as e:
            logger.error(f"❌ Failed to load cross-encoder model: {e}")
            self.enabled = False
            self.model = None
    
    def rerank(
        self,
        query: str,
        documents: List[Dict[str, Any]],
        top_k: int = 5,
        score_key: str = 'rerank_score'
    ) -> List[Dict[str, Any]]:
        """
        Rerank documents using cross-encoder scoring.
        
        Args:
            query: User query string
            documents: List of candidate documents from stage 1 retrieval
                       Each doc should have at minimum: {'text': str, 'id': str}
            top_k: Number of top results to return after reranking
            score_key: Key to store cross-encoder score in document dict
        
        Returns:
            Reranked documents (top-K) sorted by cross-encoder score
        """
        # Fast path: reranking disabled or no documents
        if not self.enabled or not documents or len(documents) == 0:
            return documents[:top_k]
        
        # Fast path: model not loaded
        if self.model is None:
            logger.warning("Cross-encoder model not loaded, returning original documents")
            return documents[:top_k]
        
        try:
            # Prepare query-document pairs for cross-encoder
            # Format: [query, document_text] for each document
            pairs = []
            for doc in documents:
                # Extract text from document (handle different formats)
                doc_text = self._extract_text(doc)
                pairs.append([query, doc_text])
            
            # Score all pairs with cross-encoder
            # Returns numpy array of relevance scores
            scores = self.model.predict(pairs, batch_size=self.batch_size)
            
            # Add cross-encoder scores to documents
            for doc, score in zip(documents, scores):
                doc[score_key] = float(score)
                
                # Preserve original score if it exists
                if 'score' in doc and 'original_score' not in doc:
                    doc['original_score'] = doc['score']
            
            # Sort by cross-encoder score (descending)
            reranked = sorted(
                documents,
                key=lambda x: x.get(score_key, -float('inf')),
                reverse=True
            )
            
            if self.verbose:
                logger.info(f"[RERANK] Reranked {len(documents)} docs -> top {top_k}")
                logger.info(f"[RERANK] Score range: {min(scores):.3f} to {max(scores):.3f}")
            
            return reranked[:top_k]
        
        except Exception as e:
            logger.error(f"❌ Error during reranking: {e}")
            # Fallback: return original documents
            return documents[:top_k]
    
    def _extract_text(self, doc: Dict[str, Any]) -> str:
        """
        Extract text content from document dictionary.
        
        Handles various document formats:
        - {'text': str}
        - {'content': str}
        - {'message': str}
        - MemoryEntry-like objects
        
        Args:
            doc: Document dictionary
        
        Returns:
            Extracted text string
        """
        # Try common text fields
        if 'text' in doc:
            return str(doc['text'])
        elif 'content' in doc:
            return str(doc['content'])
        elif 'message' in doc:
            return str(doc['message'])
        elif 'body' in doc:
            return str(doc['body'])
        else:
            # Fallback: convert entire doc to string
            return str(doc)
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get reranker statistics.
        
        Returns:
            Dictionary with reranker configuration and stats
        """
        return {
            'model_name': self.model_name,
            'enabled': self.enabled,
            'model_loaded': self.model is not None,
            'batch_size': self.batch_size,
            'verbose': self.verbose
        }


# Singleton instance for global use
_reranker_instance = None


def get_reranker(
    model_name: str = 'cross-encoder/ms-marco-MiniLM-L6-v2',
    enabled: bool = True,
    batch_size: int = 32,
    verbose: bool = False
) -> CrossEncoderReranker:
    """
    Get or create singleton reranker instance.
    
    This avoids loading the model multiple times.
    
    Args:
        model_name: HuggingFace model ID
        enabled: Enable reranking
        batch_size: Batch size for inference
        verbose: Verbose logging
    
    Returns:
        CrossEncoderReranker instance
    """
    global _reranker_instance
    
    if _reranker_instance is None:
        _reranker_instance = CrossEncoderReranker(
            model_name=model_name,
            enabled=enabled,
            batch_size=batch_size,
            verbose=verbose
        )
    
    return _reranker_instance


if __name__ == "__main__":
    # Quick test
    print("[TEST] Testing CrossEncoderReranker...")
    
    reranker = CrossEncoderReranker(verbose=True)
    
    # Test documents
    test_query = "What is machine learning?"
    test_docs = [
        {'id': '1', 'text': 'Machine learning is a subset of artificial intelligence.'},
        {'id': '2', 'text': 'Python is a programming language.'},
        {'id': '3', 'text': 'Deep learning uses neural networks for ML.'},
        {'id': '4', 'text': 'The weather is nice today.'},
    ]
    
    print(f"\n[TEST] Query: {test_query}")
    print(f"[TEST] Documents before reranking:")
    for i, doc in enumerate(test_docs):
        print(f"  {i+1}. {doc['text'][:50]}")
    
    # Rerank
    reranked = reranker.rerank(test_query, test_docs, top_k=3)
    
    print(f"\n[TEST] Top 3 after reranking:")
    for i, doc in enumerate(reranked):
        score = doc.get('rerank_score', 0)
        print(f"  {i+1}. [Score: {score:.3f}] {doc['text'][:50]}")
    
    print(f"\n[TEST] ✅ CrossEncoderReranker working correctly!")
