"""
Cross-Encoder Reranker for RAG Precision Enhancement (Step 8)
=============================================================

Lightweight semantic reranking using a cross-encoder model to rescore
top-k retrieval results for improved precision without hurting recall.

Model: cross-encoder/ms-marco-MiniLM-L-6-v2
- Size: ~80MB
- Speed: ~10ms per query (10 results)
- Trained on MS MARCO passage ranking dataset
"""

import logging
from typing import List, Dict, Any, Optional
import numpy as np


class CrossEncoderReranker:
    """
    Lightweight cross-encoder reranker for improving retrieval precision.
    
    Unlike bi-encoders (used for initial retrieval), cross-encoders score
    query-document pairs jointly, capturing fine-grained semantic interactions.
    """
    
    def __init__(
        self,
        model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2",
        max_length: int = 512,
        device: str = "cpu"
    ):
        """
        Initialize cross-encoder reranker.
        
        Args:
            model_name: HuggingFace cross-encoder model
            max_length: Maximum sequence length for query+document
            device: "cpu" or "cuda"
        """
        self.logger = logging.getLogger(self.__class__.__name__)
        self.model_name = model_name
        self.max_length = max_length
        self.device = device
        self.model = None
        
        # Lazy initialization - only load when needed
        self._initialize_model()
    
    def _initialize_model(self):
        """Lazy load the cross-encoder model"""
        try:
            from sentence_transformers import CrossEncoder
            
            self.logger.info(f"Loading cross-encoder: {self.model_name}")
            self.model = CrossEncoder(
                self.model_name,
                max_length=self.max_length,
                device=self.device
            )
            self.logger.info(f"✅ Cross-encoder loaded: {self.model_name}")
            
        except ImportError:
            self.logger.error(
                "sentence-transformers not installed. "
                "Install: pip install sentence-transformers"
            )
            raise
        except Exception as e:
            self.logger.error(f"Failed to load cross-encoder: {e}")
            raise
    
    def rerank(
        self,
        query: str,
        documents: List[str],
        top_k: Optional[int] = None,
        return_scores: bool = False
    ) -> List[int] | List[tuple[int, float]]:
        """
        Rerank documents using cross-encoder scoring.
        
        Args:
            query: Search query
            documents: List of document texts to rerank
            top_k: Number of top results to return (default: all)
            return_scores: If True, return (index, score) tuples
            
        Returns:
            List of document indices in descending relevance order,
            or list of (index, score) tuples if return_scores=True
        """
        if not documents:
            return []
        
        if not query or not query.strip():
            # No query - return original order
            indices = list(range(len(documents)))
            return [(i, 0.0) for i in indices] if return_scores else indices
        
        # Prepare query-document pairs
        pairs = [[query, doc] for doc in documents]
        
        # Score all pairs (cross-encoder is slower but more accurate)
        scores = self.model.predict(pairs)
        
        # Sort by score (descending)
        scored_indices = [
            (idx, float(score)) 
            for idx, score in enumerate(scores)
        ]
        scored_indices.sort(key=lambda x: x[1], reverse=True)
        
        # Apply top_k limit
        if top_k is not None and top_k > 0:
            scored_indices = scored_indices[:top_k]
        
        if return_scores:
            return scored_indices
        else:
            return [idx for idx, _ in scored_indices]
    
    def rerank_with_hybrid_fusion(
        self,
        query: str,
        documents: List[str],
        vector_scores: List[float],
        fusion_weight: float = 0.7,
        top_k: Optional[int] = None
    ) -> List[tuple[int, float]]:
        """
        Hybrid reranking: combine vector scores with cross-encoder scores.
        
        Args:
            query: Search query
            documents: List of document texts
            vector_scores: Original vector similarity scores
            fusion_weight: Weight for vector scores (0-1), 
                          1-fusion_weight is cross-encoder weight
            top_k: Number of top results to return
            
        Returns:
            List of (index, hybrid_score) tuples sorted by relevance
        """
        if not documents:
            return []
        
        # Get cross-encoder scores
        ce_scored = self.rerank(query, documents, return_scores=True)
        ce_scores = {idx: score for idx, score in ce_scored}
        
        # Normalize both score sets to [0, 1]
        vector_scores_array = np.array(vector_scores)
        ce_scores_array = np.array([ce_scores[i] for i in range(len(documents))])
        
        # Min-max normalization
        def normalize(scores):
            if len(scores) == 0:
                return scores
            min_score = scores.min()
            max_score = scores.max()
            if max_score - min_score < 1e-9:
                return np.ones_like(scores) * 0.5
            return (scores - min_score) / (max_score - min_score)
        
        vector_norm = normalize(vector_scores_array)
        ce_norm = normalize(ce_scores_array)
        
        # Hybrid fusion
        hybrid_scores = (
            fusion_weight * vector_norm + 
            (1 - fusion_weight) * ce_norm
        )
        
        # Sort by hybrid score
        scored_indices = [
            (idx, float(score)) 
            for idx, score in enumerate(hybrid_scores)
        ]
        scored_indices.sort(key=lambda x: x[1], reverse=True)
        
        # Apply top_k
        if top_k is not None and top_k > 0:
            scored_indices = scored_indices[:top_k]
        
        return scored_indices


class LightweightReranker:
    """
    Simplified reranker wrapper for easy integration into VectorStore.
    """
    
    def __init__(
        self,
        model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2",
        fusion_weight: float = 0.7,  # 70% vector, 30% cross-encoder
        enabled: bool = True
    ):
        """
        Initialize lightweight reranker.
        
        Args:
            model_name: Cross-encoder model name
            fusion_weight: Weight for vector scores in hybrid fusion
            enabled: Enable/disable reranking
        """
        self.logger = logging.getLogger(self.__class__.__name__)
        self.enabled = enabled
        self.fusion_weight = fusion_weight
        
        if enabled:
            try:
                self.cross_encoder = CrossEncoderReranker(model_name=model_name)
                self.logger.info("✅ Lightweight reranker initialized")
            except Exception as e:
                self.logger.warning(f"Failed to initialize reranker: {e}")
                self.enabled = False
                self.cross_encoder = None
        else:
            self.cross_encoder = None
    
    def rerank_results(
        self,
        query: str,
        results: List[Dict[str, Any]],
        top_k: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Rerank retrieval results using cross-encoder.
        
        Args:
            query: Search query
            results: List of retrieval results with 'text' and 'score' keys
            top_k: Number of top results to return
            
        Returns:
            Reranked results with updated scores
        """
        if not self.enabled or not results or self.cross_encoder is None:
            return results[:top_k] if top_k else results
        
        # Extract documents and vector scores
        documents = [r.get("text", "") for r in results]
        vector_scores = [r.get("score", 0.0) for r in results]
        
        # Hybrid reranking
        reranked_indices = self.cross_encoder.rerank_with_hybrid_fusion(
            query=query,
            documents=documents,
            vector_scores=vector_scores,
            fusion_weight=self.fusion_weight,
            top_k=top_k
        )
        
        # Reconstruct results in new order with updated scores
        reranked_results = []
        for new_rank, (original_idx, hybrid_score) in enumerate(reranked_indices, 1):
            result = results[original_idx].copy()
            result["score"] = hybrid_score
            result["rank"] = new_rank
            result["original_rank"] = original_idx + 1
            result["reranked"] = True
            reranked_results.append(result)
        
        return reranked_results
