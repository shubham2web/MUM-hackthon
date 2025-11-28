"""
Production Configuration for Alpha-v9 Hybrid Retrieval Strategy

This module provides a drop-in replacement for standard memory search
that uses the hybrid retrieval strategy for improved precision.

Usage:
    from phase2.alpha_v9_config import configure_hybrid_retrieval
    
    # Apply to existing memory manager
    memory_manager = get_memory_manager(long_term_backend="faiss")
    configure_hybrid_retrieval(memory_manager, enable_logging=True)
    
    # Now search_memories uses hybrid strategy
    results = memory_manager.search_memories("What did the opponent say?", top_k=5)
"""

from typing import Optional
import logging
from memory.memory_manager import HybridMemoryManager
from phase2.hybrid_retrieval_strategy import HybridRetriever

logger = logging.getLogger(__name__)


def configure_hybrid_retrieval(
    memory_manager: HybridMemoryManager,
    enable_logging: bool = True,
    log_level: str = "INFO"
) -> HybridRetriever:
    """
    Configure memory manager to use Alpha-v9 hybrid retrieval strategy.
    
    This function monkey-patches the memory manager's search_memories method
    to use the HybridRetriever, which provides adaptive precision/recall
    switching based on query patterns.
    
    Args:
        memory_manager: Memory manager instance to configure
        enable_logging: Enable query classification logging
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR)
        
    Returns:
        HybridRetriever instance (for statistics access)
        
    Example:
        >>> memory_manager = get_memory_manager(long_term_backend="faiss")
        >>> hybrid = configure_hybrid_retrieval(memory_manager)
        >>> 
        >>> # Use normally
        >>> results = memory_manager.search_memories("query", top_k=5)
        >>> 
        >>> # Access statistics
        >>> stats = hybrid.get_statistics()
        >>> print(f"Mode distribution: {stats['baseline_percentage']} baseline")
    """
    # Set logging level
    hybrid_logger = logging.getLogger("phase2.hybrid_retrieval_strategy")
    hybrid_logger.setLevel(getattr(logging, log_level.upper()))
    
    # Store original search method
    original_search = memory_manager.search_memories
    
    # Create hybrid retriever
    hybrid = HybridRetriever(memory_manager, enable_logging=enable_logging)
    
    # Store reference to original search (avoid recursion)
    hybrid._original_search_memories = original_search
    
    # Monkey-patch search_memories
    def hybrid_search(query: str, top_k: int = 5, **kwargs):
        """Wrapper that routes through hybrid retriever."""
        return hybrid.retrieve(query, top_k=top_k, **kwargs)
    
    memory_manager.search_memories = hybrid_search
    
    # Store hybrid instance reference for statistics access
    memory_manager._alpha_v9_hybrid = hybrid
    
    # Log configuration
    logger.info("✅ Alpha-v9 Hybrid Retrieval Strategy configured")
    logger.info(f"   Logging: {enable_logging}, Level: {log_level}")
    
    return hybrid


def get_hybrid_statistics(memory_manager: HybridMemoryManager) -> Optional[dict]:
    """
    Get statistics from hybrid retriever if configured.
    
    Args:
        memory_manager: Memory manager instance
        
    Returns:
        Statistics dict or None if hybrid not configured
        
    Example:
        >>> stats = get_hybrid_statistics(memory_manager)
        >>> if stats:
        >>>     print(f"Total queries: {stats['total_queries']}")
        >>>     print(f"Precision mode: {stats['precision_percentage']}")
    """
    # Check if hybrid instance is stored
    if hasattr(memory_manager, '_alpha_v9_hybrid'):
        hybrid = memory_manager._alpha_v9_hybrid
        if isinstance(hybrid, HybridRetriever):
            return hybrid.get_statistics()
    
    logger.warning("Hybrid retriever not configured on this memory manager")
    return None


# Production configuration presets
PRODUCTION_CONFIG = {
    "enable_logging": True,
    "log_level": "INFO"
}

DEVELOPMENT_CONFIG = {
    "enable_logging": True,
    "log_level": "DEBUG"
}

STAGING_CONFIG = {
    "enable_logging": True,
    "log_level": "INFO"
}


def configure_for_environment(
    memory_manager: HybridMemoryManager,
    environment: str = "production"
) -> HybridRetriever:
    """
    Configure hybrid retrieval for specific environment.
    
    Args:
        memory_manager: Memory manager instance
        environment: 'production', 'staging', or 'development'
        
    Returns:
        HybridRetriever instance
        
    Example:
        >>> hybrid = configure_for_environment(memory_manager, "production")
    """
    configs = {
        "production": PRODUCTION_CONFIG,
        "staging": STAGING_CONFIG,
        "development": DEVELOPMENT_CONFIG,
        "dev": DEVELOPMENT_CONFIG
    }
    
    config = configs.get(environment.lower(), PRODUCTION_CONFIG)
    logger.info(f"📦 Configuring hybrid retrieval for {environment} environment")
    
    return configure_hybrid_retrieval(memory_manager, **config)


# Quick start function
def enable_alpha_v9(memory_manager: HybridMemoryManager) -> HybridRetriever:
    """
    Quick enable Alpha-v9 with production defaults.
    
    Args:
        memory_manager: Memory manager instance
        
    Returns:
        HybridRetriever instance
        
    Example:
        >>> from phase2.alpha_v9_config import enable_alpha_v9
        >>> hybrid = enable_alpha_v9(memory_manager)
    """
    logger.info("🚀 Enabling Alpha-v9 Hybrid Retrieval Strategy")
    return configure_for_environment(memory_manager, "production")


if __name__ == "__main__":
    # Demo usage
    print("\n" + "="*70)
    print("Alpha-v9 Hybrid Retrieval - Configuration Demo")
    print("="*70 + "\n")
    
    from memory.memory_manager import get_memory_manager
    
    # Initialize memory manager
    print("[1] Initializing memory manager...")
    memory_manager = get_memory_manager(long_term_backend="faiss")
    
    # Enable Alpha-v9
    print("[2] Enabling Alpha-v9 hybrid strategy...")
    hybrid = enable_alpha_v9(memory_manager)
    
    # Show configuration
    print("\n[3] Configuration:")
    print(f"    - Baseline Mode: Broad recall (74.78% relevance)")
    print(f"    - Precision Mode: Metadata filtering (43.85% precision)")
    print(f"    - Expected Performance: 74.78% relevance, 40.00% precision")
    
    # Demo queries
    print("\n[4] Testing query classification:")
    test_queries = [
        "What did the opponent say about safety?",
        "Tell me about the debate",
        "What specific evidence was provided in turn 1?"
    ]
    
    for query in test_queries:
        classification = hybrid.classifier.classify(query)
        print(f"\n    Query: '{query}'")
        print(f"    → Mode: {classification.mode.upper()}")
        print(f"    → Confidence: {classification.confidence:.2f}")
        print(f"    → Triggers: {', '.join(classification.triggers[:3])}")
    
    # Show statistics
    print("\n[5] Initial statistics:")
    stats = hybrid.get_statistics()
    print(f"    - Total queries: {stats['total_queries']}")
    print(f"    - Baseline: {stats['baseline_queries']} ({stats['baseline_percentage']})")
    print(f"    - Precision: {stats['precision_queries']} ({stats['precision_percentage']})")
    
    print("\n" + "="*70)
    print("✅ Alpha-v9 Configuration Demo Complete")
    print("="*70 + "\n")
