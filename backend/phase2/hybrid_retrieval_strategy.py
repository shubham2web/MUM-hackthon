"""
Hybrid Retrieval Strategy - Adaptive Precision/Recall Switching
================================================================

PRODUCTION IMPLEMENTATION: Combines baseline (high relevance) + 9c-5-combined (high precision)
Based on query classification to dynamically select optimal retrieval mode.

Performance Profile:
    Baseline: 74.78% relevance, 32.95% precision (broad context)
    9c-5: 70.25% relevance, 43.85% precision (focused filtering)
    
Expected Hybrid Performance (70% baseline / 30% precision):
    Weighted Relevance: ~73.4% (above 73% target)
    Weighted Precision: ~36.2% (above 34% target)
    Recall: 92.31% (maintains target)
    
Author: ATLAS Phase 2 Team
Date: November 11, 2025
"""

import re
from typing import List, Dict, Any, Literal
from dataclasses import dataclass
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


QueryMode = Literal["baseline", "precision"]


@dataclass
class QueryClassification:
    """Result of query classification."""
    mode: QueryMode
    confidence: float
    triggers: List[str]  # Which patterns triggered the classification
    

class QueryClassifier:
    """
    Lightweight query classifier to determine retrieval strategy.
    
    Uses rule-based heuristics to detect queries requiring high precision
    vs. broad recall.
    """
    
    def __init__(self):
        """Initialize classifier with detection patterns."""
        
        # Patterns that suggest need for high PRECISION (9c-5 mode)
        self.precision_patterns = {
            # Role-specific queries
            "role": [
                "opponent", "proponent", "moderator", "advocate", "adversary",
                "engineer", "manager", "scientist", "student", "developer",
                "expert", "analyst", "researcher", "author"
            ],
            
            # Topic-specific queries
            "topic": [
                "physics", "finance", "security", "policy", "ai", "health",
                "climate", "energy", "nuclear", "solar", "vaccine",
                "economics", "environment", "technology", "safety"
            ],
            
            # Document type queries
            "doc_type": [
                "report", "paper", "article", "document", "dataset",
                "study", "analysis", "evidence", "data", "claim",
                "argument", "statement", "position", "rebuttal"
            ],
            
            # Explicit filtering language
            "filter": [
                "specifically", "only", "exactly", "just", "particular",
                "which", "what specific", "filter by", "from the"
            ],
            
            # Temporal specificity
            "temporal": [
                "turn 1", "turn 2", "first", "second", "initial",
                "opening", "recent", "latest", "earlier", "previous"
            ]
        }
        
        # Patterns that suggest need for broad RECALL (baseline mode)
        self.recall_patterns = {
            # Exploratory queries
            "exploratory": [
                "tell me about", "explain", "describe", "overview",
                "general", "summary", "context", "background"
            ],
            
            # Multi-faceted queries
            "broad": [
                "everything", "all", "any", "various", "different",
                "multiple", "several", "related", "associated"
            ],
            
            # Open-ended questions
            "open_ended": [
                "how", "why", "when", "where", "discuss",
                "analyze", "compare", "contrast", "evaluate"
            ]
        }
    
    def classify(self, query: str) -> QueryClassification:
        """
        Classify query to determine optimal retrieval mode.
        
        Args:
            query: User query string
            
        Returns:
            QueryClassification with mode, confidence, and triggers
        """
        query_lower = query.lower()
        
        # Count matches for each pattern category
        precision_matches = []
        recall_matches = []
        
        # Check precision patterns
        for category, patterns in self.precision_patterns.items():
            for pattern in patterns:
                if pattern in query_lower:
                    precision_matches.append(f"{category}:{pattern}")
        
        # Check recall patterns
        for category, patterns in self.recall_patterns.items():
            for pattern in patterns:
                if pattern in query_lower:
                    recall_matches.append(f"{category}:{pattern}")
        
        # Decision logic - CONSERVATIVE: Favor baseline unless strong precision signal
        precision_score = len(precision_matches)
        recall_score = len(recall_matches)
        
        # PRECISION mode ONLY if strong signals:
        # 1. 3+ precision triggers (very focused query)
        # 2. OR 2 precision triggers from DIFFERENT categories
        # 3. OR explicit filter language present
        
        has_filter = any("filter" in t for t in precision_matches)
        has_temporal = any("temporal" in t for t in precision_matches)
        has_doc_type = any("doc_type" in t for t in precision_matches)
        
        # Count unique categories
        precision_categories = len(set(t.split(":")[0] for t in precision_matches))
        
        if precision_score >= 3:
            # Very specific query
            mode = "precision"
            confidence = min(0.75 + (precision_score * 0.05), 0.95)
            triggers = precision_matches
        
        elif precision_categories >= 2 and precision_score >= 2:
            # Multi-dimensional specificity
            mode = "precision"
            confidence = 0.80
            triggers = precision_matches
        
        elif has_filter or (has_temporal and has_doc_type):
            # Explicit filtering or temporal+document constraints
            mode = "precision"
            confidence = 0.85
            triggers = precision_matches
        
        # Otherwise use BASELINE (broad recall) - default for most queries
        else:
            mode = "baseline"
            confidence = 0.75 if recall_score > 0 else 0.70
            triggers = recall_matches if recall_matches else ["default:broad_query"]
        
        return QueryClassification(
            mode=mode,
            confidence=confidence,
            triggers=triggers
        )


class HybridRetriever:
    """
    Adaptive retrieval system that switches between baseline and precision modes.
    
    Automatically classifies queries and routes to optimal retrieval strategy.
    """
    
    def __init__(self, memory_manager, enable_logging: bool = True):
        """
        Initialize hybrid retriever.
        
        Args:
            memory_manager: HybridMemoryManager instance
            enable_logging: Whether to log mode decisions
        """
        self.memory_manager = memory_manager
        self.classifier = QueryClassifier()
        self.enable_logging = enable_logging
        
        # Statistics tracking
        self.stats = {
            "total_queries": 0,
            "baseline_queries": 0,
            "precision_queries": 0,
            "mode_history": []
        }
        
        # Lazy-load 9c-5 components
        self._metadata_strategy = None
        self._metadata_profiles = {}
    
    def _get_metadata_strategy(self):
        """Lazy-load Step 9c metadata filtering strategy."""
        if self._metadata_strategy is not None:
            return self._metadata_strategy
        
        # Import Step 9c components
        import sys
        from pathlib import Path
        backend_dir = Path(__file__).parent.parent
        sys.path.insert(0, str(backend_dir))
        
        from phase2.step9c_metadata_expansion_tests import CombinedFilterStrategy
        
        self._metadata_strategy = CombinedFilterStrategy()
        logger.info("📦 Loaded 9c-5-combined metadata strategy")
        
        return self._metadata_strategy
    
    def retrieve(
        self,
        query: str,
        top_k: int = 5,
        force_mode: QueryMode = None,
        **kwargs
    ) -> List[Dict[str, Any]]:
        """
        Retrieve documents using adaptive strategy selection.
        
        Args:
            query: User query
            top_k: Number of results to return
            force_mode: Override classification (for testing)
            **kwargs: Additional search parameters
            
        Returns:
            List of retrieved documents
        """
        # Update statistics
        self.stats["total_queries"] += 1
        
        # Classify query (unless overridden)
        if force_mode:
            classification = QueryClassification(
                mode=force_mode,
                confidence=1.0,
                triggers=["forced"]
            )
        else:
            classification = self.classifier.classify(query)
        
        # Log decision
        if self.enable_logging:
            logger.info(
                f"🎯 Query: '{query[:60]}...' → Mode: {classification.mode.upper()} "
                f"(confidence: {classification.confidence:.2f}, "
                f"triggers: {', '.join(classification.triggers[:3])})"
            )
        
        # Update mode statistics
        self.stats["mode_history"].append(classification.mode)
        if classification.mode == "baseline":
            self.stats["baseline_queries"] += 1
        else:
            self.stats["precision_queries"] += 1
        
        # Route to appropriate retrieval strategy
        if classification.mode == "baseline":
            return self._retrieve_baseline(query, top_k, **kwargs)
        else:
            return self._retrieve_precision(query, top_k, **kwargs)
    
    def _retrieve_baseline(
        self,
        query: str,
        top_k: int = 5,
        **kwargs
    ) -> List[Dict[str, Any]]:
        """
        Baseline retrieval (high relevance, broad recall).
        
        Uses standard hybrid search without filtering.
        """
        # Use original search method if available (to avoid recursion)
        search_method = getattr(self, '_original_search_memories', None) or self.memory_manager.search_memories
        results = search_method(query, top_k=top_k, **kwargs)
        
        if self.enable_logging:
            logger.info(f"   ✅ Baseline: Retrieved {len(results)} results")
        
        return results
    
    def _retrieve_precision(
        self,
        query: str,
        top_k: int = 5,
        **kwargs
    ) -> List[Dict[str, Any]]:
        """
        Precision retrieval (high precision, focused filtering).
        
        Uses Step 9c-5-combined metadata filtering strategy.
        """
        # Get metadata strategy
        strategy = self._get_metadata_strategy()
        
        # Retrieve more candidates for filtering
        retrieve_k = min(top_k * 3, 15)  # Get 3x for filtering
        
        # Use original search method if available (to avoid recursion)
        search_method = getattr(self, '_original_search_memories', None) or self.memory_manager.search_memories
        candidates = search_method(
            query,
            top_k=retrieve_k,
            **kwargs
        )
        
        # Extract metadata if needed
        vector_store = self.memory_manager.long_term
        if vector_store and hasattr(vector_store, 'id_to_metadata'):
            for doc_id, metadata in vector_store.id_to_metadata.items():
                if doc_id not in self._metadata_profiles:
                    text = metadata.get('text', '')
                    if text:
                        profile = strategy.extractor.extract_metadata(text, metadata)
                        self._metadata_profiles[doc_id] = profile
        
        # Convert to dict format for filtering
        candidates_dicts = []
        for r in candidates:
            candidates_dicts.append({
                'id': r['id'],
                'score': r.get('score', 1.0),
                'text': r['text'],
                'metadata': r.get('metadata', {})
            })
        
        # Apply metadata filtering
        filtered_dicts = strategy.filter_results(
            query,
            candidates_dicts,
            self._metadata_profiles
        )
        
        # Convert back to original format
        id_to_result = {r['id']: r for r in candidates}
        filtered = []
        for f_dict in filtered_dicts[:top_k]:
            if f_dict['id'] in id_to_result:
                filtered.append(id_to_result[f_dict['id']])
        
        # Fallback: if filtering removed too many, supplement with baseline
        if len(filtered) < max(2, top_k // 2):
            logger.warning(
                f"   ⚠️  Precision filtering too aggressive "
                f"({len(filtered)}/{top_k}), blending with baseline"
            )
            baseline_results = self._retrieve_baseline(query, top_k, **kwargs)
            
            # Merge: precision results first, then baseline
            seen_ids = {r['id'] for r in filtered}
            for baseline_r in baseline_results:
                if baseline_r['id'] not in seen_ids and len(filtered) < top_k:
                    filtered.append(baseline_r)
                    seen_ids.add(baseline_r['id'])
        
        if self.enable_logging:
            logger.info(
                f"   ✅ Precision: Filtered {len(candidates)} → {len(filtered)} results"
            )
        
        return filtered
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get retrieval statistics.
        
        Returns:
            Dict with mode distribution and performance metrics
        """
        total = self.stats["total_queries"]
        if total == 0:
            return {"error": "No queries processed yet"}
        
        baseline_pct = (self.stats["baseline_queries"] / total) * 100
        precision_pct = (self.stats["precision_queries"] / total) * 100
        
        return {
            "total_queries": total,
            "baseline_queries": self.stats["baseline_queries"],
            "precision_queries": self.stats["precision_queries"],
            "baseline_percentage": f"{baseline_pct:.1f}%",
            "precision_percentage": f"{precision_pct:.1f}%",
            "mode_history": self.stats["mode_history"][-20:]  # Last 20
        }
    
    def reset_statistics(self):
        """Reset statistics counters."""
        self.stats = {
            "total_queries": 0,
            "baseline_queries": 0,
            "precision_queries": 0,
            "mode_history": []
        }


# Convenience function for integration
def create_hybrid_retriever(memory_manager) -> HybridRetriever:
    """
    Create a configured hybrid retriever.
    
    Args:
        memory_manager: HybridMemoryManager instance
        
    Returns:
        HybridRetriever instance ready to use
    """
    retriever = HybridRetriever(memory_manager, enable_logging=True)
    logger.info("🚀 Hybrid retriever initialized (baseline + 9c-5-combined)")
    return retriever


if __name__ == "__main__":
    # Demo classifier
    classifier = QueryClassifier()
    
    test_queries = [
        "What did the opponent say about safety?",  # Precision (role + topic)
        "Tell me about the debate",  # Baseline (exploratory)
        "Arguments in turn 1",  # Precision (temporal + doc_type)
        "Explain the context",  # Baseline (exploratory)
        "What specific evidence did the proponent provide?",  # Precision (filter + role)
        "Previous discussion about AI",  # Baseline (open-ended)
    ]
    
    print("\n" + "="*70)
    print("QUERY CLASSIFIER DEMO")
    print("="*70 + "\n")
    
    for query in test_queries:
        classification = classifier.classify(query)
        print(f"Query: '{query}'")
        print(f"  → Mode: {classification.mode.upper()}")
        print(f"  → Confidence: {classification.confidence:.2f}")
        print(f"  → Triggers: {', '.join(classification.triggers)}")
        print()
