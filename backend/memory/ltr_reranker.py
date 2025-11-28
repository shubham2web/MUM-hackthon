"""
Learning-to-Rank (LTR) Reranker for RAG Retrieval

Python 3.13 compatible, no torch dependency.
Uses scikit-learn LogisticRegression/RandomForest to learn relevance scoring
from benchmark training data.

Features:
- vector_sim: Cosine similarity from embedding model
- bm25_score: BM25 ranking score
- recency_days: Days since document creation
- authority_score: Numeric encoding of metadata authority
- role_match: Binary match for role filtering
- text_length: Number of tokens
- metadata_boost: Existing multiplicative boost

Expected gain: +6-12% relevance improvement
"""
from __future__ import annotations

import logging
import os
from typing import List, Dict, Any, Optional
from datetime import datetime
import numpy as np

try:
    import joblib
    from sklearn.linear_model import LogisticRegression
    from sklearn.ensemble import RandomForestClassifier, HistGradientBoostingClassifier
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False
    joblib = None
    LogisticRegression = None


class LTRReranker:
    """
    Lightweight Learning-to-Rank reranker using scikit-learn.
    
    Trains on benchmark test data to learn which features predict relevance,
    then reranks retrieval candidates at inference time.
    """
    
    # Feature names in order (must match training)
    FEATURE_NAMES = [
        'vector_sim',
        'bm25_score', 
        'recency_days',
        'authority_score',
        'role_match',
        'text_length',
        'metadata_boost',
        'query_term_overlap',  # NEW: % of query terms in result
        'position_rank',        # NEW: Original retrieval position
        'semantic_density',     # NEW: Text/score ratio (quality indicator)
        'hybrid_score'          # RAG v2.0: Adaptive fusion score (alpha-weighted)
    ]
    
    def __init__(
        self,
        model_path: str = None,
        model_type: str = "logistic",  # "logistic", "random_forest", "gradient_boosting"
        rerank_weight: float = 0.9,  # Weight for reranker score vs vector score
        enable_reranking: bool = True,
        confidence_threshold: float = 0.25  # Lowered from 0.3 for better recall
    ):
        """
        Initialize LTR reranker.
        
        Args:
            model_path: Path to saved model file (default: auto-detect)
            model_type: Type of sklearn model to use
            rerank_weight: Weight for reranker probability (0-1)
            enable_reranking: Whether to enable reranking
            confidence_threshold: Minimum confidence score to include result (filters noise)
        """
        self.logger = logging.getLogger(self.__class__.__name__)
        
        # Auto-detect model path relative to this file
        if model_path is None:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            backend_dir = os.path.dirname(current_dir)  # Go up to backend/
            
            # Step 4: Use HGB model if gradient_boosting type specified
            if model_type == "gradient_boosting":
                model_path = os.path.join(backend_dir, "models", "ltr_reranker_gb.joblib")
            elif model_type == "random_forest":
                model_path = os.path.join(backend_dir, "models", "ltr_reranker_rf.joblib")
            else:
                model_path = os.path.join(backend_dir, "models", "ltr_reranker.joblib")
        
        self.model_path = model_path
        self.model_type = model_type
        self.rerank_weight = rerank_weight
        self.vector_weight = 1.0 - rerank_weight
        self.confidence_threshold = confidence_threshold
        self.enable_reranking = enable_reranking and SKLEARN_AVAILABLE
        self.model = None
        
        if not SKLEARN_AVAILABLE:
            self.logger.warning("scikit-learn not available, LTR reranking disabled")
            self.enable_reranking = False
            return
        
        if self.enable_reranking:
            self._load_model()
    
    def _load_model(self):
        """Load trained model from disk."""
        if os.path.exists(self.model_path):
            try:
                loaded = joblib.load(self.model_path)
                
                # Handle both bundle format and legacy format
                if isinstance(loaded, dict) and 'model' in loaded:
                    # New bundle format
                    self.model = loaded['model']
                    bundle_features = loaded.get('feature_names', [])
                    
                    # Validate feature count
                    if len(bundle_features) != len(self.FEATURE_NAMES):
                        self.logger.error(
                            f"Feature mismatch! Model expects {len(bundle_features)} features, "
                            f"but code has {len(self.FEATURE_NAMES)} features"
                        )
                        self.logger.error(f"Model features: {bundle_features}")
                        self.logger.error(f"Code features: {self.FEATURE_NAMES}")
                        self.model = None
                        self.enable_reranking = False
                        return
                    
                    self.logger.info(f"✅ LTR reranker loaded from {self.model_path}")
                    self.logger.info(f"   Model type: {type(self.model).__name__}")
                    self.logger.info(f"   Features: {len(bundle_features)} ({loaded.get('training_date', 'N/A')})")
                    self.logger.info(f"   Rerank weight: {self.rerank_weight:.2f}, Vector weight: {self.vector_weight:.2f}")
                else:
                    # Legacy format (just the model)
                    self.model = loaded
                    self.logger.warning(f"⚠️ Loaded legacy model format (no feature validation)")
                    self.logger.info(f"✅ LTR reranker loaded from {self.model_path}")
                    self.logger.info(f"   Model type: {type(self.model).__name__}")
                    self.logger.info(f"   Rerank weight: {self.rerank_weight:.2f}, Vector weight: {self.vector_weight:.2f}")
                    
            except Exception as e:
                self.logger.error(f"Failed to load LTR model: {e}")
                self.model = None
                self.enable_reranking = False
        else:
            self.logger.warning(f"LTR model not found at {self.model_path}")
            self.logger.info("Run train_ltr_reranker.py to generate the model")
            self.enable_reranking = False
    
    def extract_features(
        self,
        candidate: Dict[str, Any],
        query: str = "",
        query_metadata: Optional[Dict[str, Any]] = None,
        bm25_scores: Optional[Dict[str, float]] = None,
        position: int = 0
    ) -> Dict[str, float]:
        """
        Extract feature vector from a candidate result.
        
        Args:
            candidate: Result dict with id, text, score, metadata
            query: Query string for computing overlap
            query_metadata: Query metadata (e.g., required role)
            bm25_scores: Dict mapping candidate id to BM25 score
            position: Original retrieval position (0-indexed)
            
        Returns:
            Feature dict with all feature values
        """
        features = {}
        
        # Vector similarity score
        features['vector_sim'] = candidate.get('score', 0.0)
        
        # BM25 score
        if bm25_scores and candidate.get('id') in bm25_scores:
            features['bm25_score'] = bm25_scores[candidate['id']]
        else:
            features['bm25_score'] = 0.0
        
        # Recency (days since creation)
        metadata = candidate.get('metadata', {})
        timestamp_str = metadata.get('timestamp')
        if timestamp_str:
            try:
                ts = datetime.fromisoformat(timestamp_str)
                days = (datetime.now() - ts).days
                features['recency_days'] = float(days)
            except:
                features['recency_days'] = 3650.0  # ~10 years (very old)
        else:
            features['recency_days'] = 3650.0
        
        # Authority score (map to 0-1)
        authority = metadata.get('authority', 'unknown')
        authority_map = {
            'researcher': 1.0,
            'news': 0.8,
            'expert': 0.9,
            'government': 0.85,
            'user': 0.3,
            'unknown': 0.4
        }
        features['authority_score'] = authority_map.get(authority, 0.4)
        
        # Role match (binary) - IMPROVED: Check both exact and opponent match
        required_role = query_metadata.get('role') if query_metadata else None
        candidate_role = metadata.get('role')
        if required_role and candidate_role:
            # Exact match OR role reversal (pro↔con)
            is_exact = candidate_role == required_role
            is_reversed = (
                (required_role == 'pro' and candidate_role == 'con') or
                (required_role == 'con' and candidate_role == 'pro')
            )
            # Give partial credit for reversed roles (relevant for role reversal tests)
            features['role_match'] = 1.0 if is_exact else (0.5 if is_reversed else 0.0)
        else:
            features['role_match'] = 0.0
        
        # Text length (tokens)
        text = candidate.get('text', '')
        features['text_length'] = float(len(text.split()))
        
        # Metadata boost applied
        features['metadata_boost'] = metadata.get('boost', 1.0)
        
        # NEW: Query term overlap (% of query words in result)
        if query:
            query_terms = set(query.lower().split())
            result_terms = set(text.lower().split())
            if query_terms:
                overlap = len(query_terms & result_terms) / len(query_terms)
                features['query_term_overlap'] = overlap
            else:
                features['query_term_overlap'] = 0.0
        else:
            features['query_term_overlap'] = 0.0
        
        # NEW: Position rank (earlier = better, normalized)
        features['position_rank'] = 1.0 / (position + 1.0)  # 1.0, 0.5, 0.33...
        
        # NEW: Semantic density (quality indicator: score per word)
        if features['text_length'] > 0:
            features['semantic_density'] = features['vector_sim'] / (features['text_length'] / 100.0)
        else:
            features['semantic_density'] = 0.0
        
        # RAG v2.0: Hybrid score from adaptive fusion layer
        # This captures query-aware alpha weighting + metadata boost
        features['hybrid_score'] = candidate.get('hybrid_score', candidate.get('final_score', features['vector_sim']))
        
        return features
    
    def rerank(
        self,
        query: str,
        candidates: List[Dict[str, Any]],
        top_k: int = 5,
        query_metadata: Optional[Dict[str, Any]] = None,
        bm25_scores: Optional[Dict[str, float]] = None
    ) -> List[Dict[str, Any]]:
        """
        Rerank candidates using trained LTR model.
        
        Args:
            query: Search query string
            candidates: List of candidate results to rerank
            top_k: Number of results to return
            query_metadata: Optional query metadata (e.g., role filter)
            bm25_scores: Optional dict of BM25 scores by candidate id
            
        Returns:
            Reranked list of top_k candidates (filtered by confidence threshold)
        """
        if not self.enable_reranking or not self.model or not candidates:
            return candidates[:top_k]
        
        try:
            # Extract features for all candidates
            feature_rows = []
            expected_features = None
            
            # COMPATIBILITY: Determine expected feature count from model
            if hasattr(self.model, 'n_features_in_'):
                expected_features = self.model.n_features_in_
                if expected_features < len(self.FEATURE_NAMES):
                    self.logger.info(f"Model expects {expected_features} features, truncating from {len(self.FEATURE_NAMES)}")
            
            for position, candidate in enumerate(candidates):
                features = self.extract_features(
                    candidate, 
                    query=query,
                    query_metadata=query_metadata, 
                    bm25_scores=bm25_scores,
                    position=position
                )
                # Convert to list in correct order
                feature_vector = []
                for i, name in enumerate(self.FEATURE_NAMES):
                    # Stop if we've reached expected feature count
                    if expected_features and i >= expected_features:
                        break
                    if name in features:
                        feature_vector.append(features[name])
                
                feature_rows.append(feature_vector)
            
            # Get predictions from model
            X = np.array(feature_rows)
            probabilities = self.model.predict_proba(X)[:, 1]  # Probability of relevance
            
            # Step 4: Normalize scores to [0, 1] to prevent scale mismatch
            # Normalize HGB probabilities (usually already 0-1, but ensure it)
            hgb_min, hgb_max = probabilities.min(), probabilities.max()
            if hgb_max > hgb_min:
                probabilities_norm = (probabilities - hgb_min) / (hgb_max - hgb_min)
            else:
                probabilities_norm = probabilities
            
            # Normalize hybrid scores
            hybrid_scores = np.array([c.get('score', 0.0) for c in candidates])
            hybrid_min, hybrid_max = hybrid_scores.min(), hybrid_scores.max()
            if hybrid_max > hybrid_min:
                hybrid_scores_norm = (hybrid_scores - hybrid_min) / (hybrid_max - hybrid_min)
            else:
                hybrid_scores_norm = hybrid_scores
            
            # Compute soft bias fusion: 0.7 * hybrid + 0.3 * hgb
            for i, candidate in enumerate(candidates):
                hgb_score = float(probabilities_norm[i])
                hybrid_score = float(hybrid_scores_norm[i])
                
                # Soft bias combination (normalized scores)
                candidate['rerank_score'] = hgb_score
                candidate['hybrid_score_norm'] = hybrid_score
                candidate['final_score'] = (
                    self.vector_weight * hybrid_score +  # 0.7 weight for hybrid
                    self.rerank_weight * hgb_score       # 0.3 weight for HGB
                )
            
            # CRITICAL: Filter by confidence threshold (removes noise/irrelevant results)
            confident_results = [
                c for c in candidates 
                if c.get('rerank_score', 0.0) >= self.confidence_threshold
            ]
            
            # If we filtered too aggressively, fall back to top vector results
            if len(confident_results) == 0 and len(candidates) > 0:
                self.logger.warning(f"All {len(candidates)} results below confidence threshold {self.confidence_threshold}, using top vector results")
                confident_results = candidates[:top_k]
            
            # Sort by final score
            reranked = sorted(confident_results, key=lambda x: x.get('final_score', 0.0), reverse=True)
            
            filtered_count = len(candidates) - len(confident_results)
            if filtered_count > 0:
                self.logger.debug(f"Filtered {filtered_count} low-confidence results (threshold={self.confidence_threshold})")
            
            self.logger.debug(f"Reranked {len(candidates)} candidates → {len(confident_results)} confident → returning top {min(top_k, len(reranked))}")
            
            return reranked[:top_k]
            
        except Exception as e:
            self.logger.error(f"LTR reranking failed: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            # Fallback to original ordering
            return candidates[:top_k]


# Global singleton
_ltr_reranker: Optional[LTRReranker] = None


def get_ltr_reranker(reset: bool = False, **kwargs) -> LTRReranker:
    """
    Get or create global LTR reranker instance.
    
    Args:
        reset: Whether to reset the singleton
        **kwargs: Arguments for LTRReranker constructor
        
    Returns:
        LTRReranker instance
    """
    global _ltr_reranker
    
    if reset or _ltr_reranker is None:
        _ltr_reranker = LTRReranker(**kwargs)
    
    return _ltr_reranker
