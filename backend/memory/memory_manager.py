"""
Hybrid Memory Manager - Core Orchestrator

Combines RAG (long-term memory) with short-term conversational memory.
Implements the 4-Zone Context Payload architecture from the PRD.
"""
from __future__ import annotations

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

from memory.vector_store import VectorStore
from memory.short_term_memory import ShortTermMemory
from memory.embeddings import get_embedding_service


class HybridMemoryManager:
    """
    Main orchestrator for the Hybrid Memory System.
    
    Implements the 4-Zone Context Payload:
    - ZONE 1: SYSTEM PROMPT (agent identity, role, rules)
    - ZONE 2: LONG-TERM MEMORY (RAG retrieval from vector DB)
    - ZONE 3: SHORT-TERM MEMORY (recent conversational window)
    - ZONE 4: NEW TASK (current instruction/action)
    
    Usage:
        memory_manager = HybridMemoryManager()
        
        # Add interactions to memory
        memory_manager.add_interaction(role="proponent", content="...")
        
        # Build context payload for LLM
        payload = memory_manager.build_context_payload(
            system_prompt="You are...",
            current_task="Analyze...",
            query="What was discussed about X?"
        )
        
        # Use payload with LLM
        response = llm.generate(payload)
    """
    
    def __init__(
        self,
        short_term_window: int = 4,
        long_term_backend: str = "chromadb",
        collection_name: str = "atlas_memory",
        enable_rag: bool = True,
        enable_reranking: bool = False,  # STEP 4 FAILED: HGB hurt performance -2.66% - DISABLED
    ):
        """
        Initialize Hybrid Memory Manager.
        
        Args:
            short_term_window: Number of recent messages to keep
            long_term_backend: "chromadb" or "faiss"
            collection_name: Name for vector store collection
            enable_rag: Whether to enable RAG retrieval (can disable for testing)
            enable_reranking: Whether to enable cross-encoder re-ranking
        """
        self.logger = logging.getLogger(self.__class__.__name__)
        
        # Initialize short-term memory (ZONE 3)
        self.short_term = ShortTermMemory(window_size=short_term_window)
        
        # Initialize long-term memory (ZONE 2)
        self.enable_rag = enable_rag
        if self.enable_rag:
            try:
                self.long_term = VectorStore(
                    collection_name=collection_name,
                    backend=long_term_backend,
                    enable_reranking=enable_reranking  # CRITICAL FIX: Pass reranking flag through
                )
                self.logger.info("✅ Hybrid Memory System initialized with RAG enabled")
            except Exception as e:
                self.logger.error(f"Failed to initialize RAG: {e}")
                self.logger.warning("Disabling RAG - only short-term memory will be used")
                self.enable_rag = False
                self.long_term = None
        else:
            self.long_term = None
            self.logger.info("Hybrid Memory System initialized (RAG disabled)")
        
        # Metadata for tracking
        self.current_debate_id = None
        self.turn_counter = 0
    
    def set_debate_context(self, debate_id: str):
        """
        Set the current debate context for metadata tracking.
        
        Args:
            debate_id: Unique identifier for the debate session
        """
        self.current_debate_id = debate_id
        self.turn_counter = 0
        self.logger.info(f"Debate context set: {debate_id}")
    
    def add_interaction(
        self,
        role: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
        store_in_rag: bool = True
    ) -> Dict[str, str]:
        """
        Add an interaction to both short-term and long-term memory.
        
        Args:
            role: Speaker role (user, assistant, proponent, opponent, moderator, etc.)
            content: Message content
            metadata: Optional metadata
            store_in_rag: Whether to also store in long-term RAG
            
        Returns:
            Dict with memory IDs
        """
        if not content or not content.strip():
            self.logger.warning("Attempted to add empty interaction")
            return {}
        
        self.turn_counter += 1
        
        # Prepare metadata
        full_metadata = metadata or {}
        full_metadata.update({
            'role': role,
            'turn': self.turn_counter,
            'timestamp': datetime.now().isoformat()
        })
        
        if self.current_debate_id:
            full_metadata['debate_id'] = self.current_debate_id
        
        # Add to short-term memory (ZONE 3)
        short_term_msg = self.short_term.add_message(
            role=role,
            content=content,
            metadata=full_metadata
        )
        
        # Add to long-term memory (ZONE 2)
        long_term_id = None
        if store_in_rag and self.enable_rag and self.long_term:
            # Format for RAG: include role context
            rag_text = f"[{role.upper()}]: {content}"
            long_term_id = self.long_term.add_memory(
                text=rag_text,
                metadata=full_metadata
            )
        
        result = {
            'role': role,
            'turn': self.turn_counter,
            'short_term': 'added',
            'long_term': long_term_id if long_term_id else 'not_stored'
        }
        
        self.logger.debug(f"Added interaction: {role} (turn {self.turn_counter})")
        return result
    
    def build_context_payload(
        self,
        system_prompt: str,
        current_task: str,
        query: Optional[str] = None,
        top_k_rag: int = 4,
        use_short_term: bool = True,
        use_long_term: bool = True,
        format_style: str = "structured"
    ) -> str:
        """
        Build the complete 4-Zone Context Payload for LLM.
        
        Args:
            system_prompt: ZONE 1 - Agent identity and rules
            current_task: ZONE 4 - Current instruction
            query: Optional query for RAG retrieval (if None, uses current_task)
            top_k_rag: Number of relevant memories to retrieve from RAG
            use_short_term: Include ZONE 3 (recent conversation)
            use_long_term: Include ZONE 2 (RAG retrieval)
            format_style: "structured" or "conversational"
            
        Returns:
            Complete formatted context string
        """
        zones = []
        
        # ZONE 1: SYSTEM PROMPT (always included)
        zones.append("=" * 80)
        zones.append("[ZONE 1: SYSTEM PROMPT]")
        zones.append("=" * 80)
        zones.append(system_prompt)
        zones.append("")
        
        # ZONE 2: LONG-TERM MEMORY (RAG)
        if use_long_term and self.enable_rag and self.long_term:
            rag_query = query if query else current_task
            rag_context = self.long_term.get_relevant_context(
                query=rag_query,
                top_k=top_k_rag,
                format_style=format_style
            )
            
            if rag_context:
                zones.append("=" * 80)
                zones.append("[ZONE 2: LONG-TERM MEMORY (RAG)]")
                zones.append("=" * 80)
                zones.append(rag_context)
                zones.append("")
        
        # ZONE 3: SHORT-TERM MEMORY (recent conversation)
        if use_short_term and len(self.short_term) > 0:
            short_term_context = self.short_term.get_context_string(
                format_style=format_style
            )
            
            if short_term_context:
                zones.append("=" * 80)
                zones.append("[ZONE 3: SHORT-TERM MEMORY]")
                zones.append("=" * 80)
                zones.append(short_term_context)
                zones.append("")
        
        # ZONE 4: NEW TASK (current instruction)
        zones.append("=" * 80)
        zones.append("[ZONE 4: CURRENT TASK]")
        zones.append("=" * 80)
        zones.append(current_task)
        zones.append("=" * 80)
        
        return "\n".join(zones)
    
    def get_zone2_context(self, query: str, top_k: int = 4) -> str:
        """Get only ZONE 2 (RAG) context"""
        if not self.enable_rag or not self.long_term:
            return ""
        return self.long_term.get_relevant_context(query, top_k=top_k)
    
    def get_zone3_context(self, count: Optional[int] = None) -> str:
        """Get only ZONE 3 (short-term) context"""
        return self.short_term.get_context_string(count=count)
    
    def clear_short_term(self):
        """Clear short-term memory only"""
        self.short_term.clear()
        self.logger.info("Short-term memory cleared")
    
    def clear_long_term(self):
        """Clear long-term memory only (use with caution!)"""
        if self.enable_rag and self.long_term:
            self.long_term.clear_all()
            self.logger.warning("Long-term memory cleared!")
    
    def clear_all_memory(self):
        """Clear both short-term and long-term memory"""
        self.clear_short_term()
        self.clear_long_term()
        self.logger.warning("All memory cleared!")
    
    def clear(self):
        """
        Clear all memory (alias for clear_all_memory).
        
        This method is provided for convenience and compatibility with
        test frameworks that expect a simple clear() method.
        """
        self.clear_all_memory()
    
    def get_memory_summary(self) -> Dict[str, Any]:
        """Get comprehensive memory system statistics"""
        summary = {
            'current_debate_id': self.current_debate_id,
            'turn_counter': self.turn_counter,
            'short_term': self.short_term.get_summary(),
            'long_term': None,
            'rag_enabled': self.enable_rag
        }
        
        if self.enable_rag and self.long_term:
            summary['long_term'] = self.long_term.get_stats()
        
        return summary
    
    def export_memory_state(self) -> Dict[str, Any]:
        """Export complete memory state for persistence"""
        state = {
            'debate_id': self.current_debate_id,
            'turn_counter': self.turn_counter,
            'short_term': self.short_term.export_to_dict(),
            'timestamp': datetime.now().isoformat()
        }
        return state
    
    def search_memories(
        self,
        query: str,
        top_k: int = 10,
        filter_metadata: Optional[Dict[str, Any]] = None,
        similarity_threshold: float = 0.50  # OPTIMAL: Balanced at 0.50 for best precision/recall tradeoff
    ) -> List[Dict[str, Any]]:
        """
        Search long-term memories with optional filters and similarity threshold.
        
        Args:
            query: Search query
            top_k: Number of results
            filter_metadata: Optional metadata filters (e.g., {"role": "proponent"})
            similarity_threshold: Minimum similarity score (0-1) for results
            
        Returns:
            List of search results with scores (filtered by threshold)
        """
        if not self.enable_rag or not self.long_term:
            return []
        
        # OPTIMIZATION 1 & 2: Pass threshold and metadata filters to vector store
        results = self.long_term.search(
            query, 
            top_k=top_k, 
            filter_metadata=filter_metadata,
            similarity_threshold=similarity_threshold
        )
        return [
            {
                'id': r.id,
                'text': r.text,
                'score': r.score,
                'rank': r.rank,
                'metadata': r.metadata
            }
            for r in results
        ]
    
    def __repr__(self) -> str:
        return (
            f"HybridMemoryManager("
            f"debate={self.current_debate_id}, "
            f"turns={self.turn_counter}, "
            f"short_term={len(self.short_term)}, "
            f"rag={'enabled' if self.enable_rag else 'disabled'})"
        )


# Global singleton instance (optional)
_memory_manager: Optional[HybridMemoryManager] = None


def get_memory_manager(
    reset: bool = False,
    enable_alpha_v9: bool = True,  # NEW: Enable Alpha-v9 by default
    **kwargs
) -> HybridMemoryManager:
    """
    Get or create global memory manager instance.
    
    Args:
        reset: Whether to create a new instance
        enable_alpha_v9: Enable Alpha-v9 Hybrid Retrieval Strategy (recommended)
        **kwargs: Arguments for HybridMemoryManager constructor
        
    Returns:
        HybridMemoryManager instance
    """
    global _memory_manager
    
    if reset or _memory_manager is None:
        _memory_manager = HybridMemoryManager(**kwargs)
        
        # Enable Alpha-v9 Hybrid Retrieval if requested
        if enable_alpha_v9:
            try:
                from phase2.alpha_v9_config import configure_hybrid_retrieval
                hybrid = configure_hybrid_retrieval(
                    _memory_manager, 
                    enable_logging=False,  # Disable verbose logging in production
                    log_level="WARNING"
                )
                logging.info("✅ Alpha-v9 Hybrid Retrieval Strategy enabled (+7pp precision)")
            except ImportError as e:
                logging.warning(f"⚠️ Alpha-v9 not available: {e}. Using baseline retrieval.")
            except Exception as e:
                logging.error(f"❌ Failed to enable Alpha-v9: {e}. Using baseline retrieval.")
    
    return _memory_manager
