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

# Import web scraper for External RAG
try:
    from tools.web_scraper import fetch_url_content, extract_url
    WEB_SCRAPER_AVAILABLE = True
except ImportError:
    WEB_SCRAPER_AVAILABLE = False
    logging.warning("Web scraper not available - External RAG disabled")


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
    
    def get_role_history(self, role: str, debate_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Retrieve all memories from a specific role in the debate.
        
        This is used for role reversal to recall the agent's original stance.
        
        Args:
            role: Role to retrieve memories for (e.g., "proponent", "opponent")
            debate_id: Optional debate ID to filter by (uses current if None)
            
        Returns:
            List of memory entries from that role
        """
        if not self.enable_rag or not self.long_term:
            return []
        
        debate_id = debate_id or self.current_debate_id
        filter_metadata = {"role": role}
        if debate_id:
            filter_metadata["debate_id"] = debate_id
        
        try:
            results = self.search_memories(
                query=f"all arguments and statements by {role}",
                top_k=20,  # Get more results for role history
                filter_metadata=filter_metadata,
                similarity_threshold=0.0  # Get all results, regardless of similarity
            )
            self.logger.info(f"📜 Retrieved {len(results)} historical memories for role '{role}'")
            return results
        except Exception as e:
            self.logger.error(f"Failed to retrieve role history: {e}")
            return []
    
    def build_role_reversal_context(
        self,
        current_role: str,
        previous_role: str,
        system_prompt: str,
        current_task: str,
        debate_id: Optional[str] = None
    ) -> str:
        """
        Build specialized context for role reversal scenarios.
        
        When agents switch roles mid-debate, this ensures they can recall their
        previous arguments and maintain coherent reasoning.
        
        Args:
            current_role: The role the agent is NOW playing
            previous_role: The role the agent PREVIOUSLY played
            system_prompt: System prompt for the current role
            current_task: Current task instruction
            debate_id: Optional debate ID (uses current if None)
            
        Returns:
            Enhanced context payload with role history
        """
        # Get the agent's previous arguments when they were in the other role
        previous_arguments = self.get_role_history(previous_role, debate_id)
        
        # Build special RAG query to retrieve relevant context about role switch
        rag_query = (
            f"Previous arguments made by {previous_role} that are relevant to "
            f"the current {current_role} position"
        )
        
        zones = []
        
        # ZONE 1: SYSTEM PROMPT (with role reversal awareness)
        zones.append("=" * 80)
        zones.append("[ZONE 1: SYSTEM PROMPT - ROLE REVERSAL MODE]")
        zones.append("=" * 80)
        zones.append(system_prompt)
        zones.append("")
        zones.append(f"⚠️  ROLE REVERSAL CONTEXT:")
        zones.append(f"   - You previously argued as: {previous_role}")
        zones.append(f"   - You are now arguing as: {current_role}")
        zones.append(f"   - Maintain awareness of your previous stance to avoid contradictions")
        zones.append("")
        
        # ZONE 2A: PREVIOUS ROLE HISTORY (what I said before)
        if previous_arguments:
            zones.append("=" * 80)
            zones.append(f"[ZONE 2A: YOUR PREVIOUS ARGUMENTS AS {previous_role.upper()}]")
            zones.append("=" * 80)
            zones.append(f"Review of your previous stance (first {min(5, len(previous_arguments))} key points):\n")
            
            for i, arg in enumerate(previous_arguments[:5], 1):
                content = arg.get('content', '')
                turn = arg.get('metadata', {}).get('turn', 'unknown')
                zones.append(f"{i}. [Turn {turn}] {content[:200]}...")
                zones.append("")
        
        # ZONE 2B: LONG-TERM MEMORY (RAG - broader context)
        if self.enable_rag and self.long_term:
            rag_context = self.long_term.get_relevant_context(
                query=rag_query,
                top_k=3,
                format_style="structured"
            )
            
            if rag_context:
                zones.append("=" * 80)
                zones.append("[ZONE 2B: RELEVANT DEBATE CONTEXT]")
                zones.append("=" * 80)
                zones.append(rag_context)
                zones.append("")
        
        # ZONE 3: SHORT-TERM MEMORY (recent conversation)
        if len(self.short_term) > 0:
            short_term_context = self.short_term.get_context_string(format_style="structured")
            
            if short_term_context:
                zones.append("=" * 80)
                zones.append("[ZONE 3: RECENT CONVERSATION]")
                zones.append("=" * 80)
                zones.append(short_term_context)
                zones.append("")
        
        # ZONE 4: NEW TASK (current instruction)
        zones.append("=" * 80)
        zones.append("[ZONE 4: CURRENT TASK]")
        zones.append("=" * 80)
        zones.append(current_task)
        zones.append("=" * 80)
        
        context = "\n".join(zones)
        self.logger.info(
            f"🔄 Role reversal context built: {previous_role} → {current_role} "
            f"({len(previous_arguments)} historical args recalled)"
        )
        
        return context
    
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
        format_style: str = "structured",
        enable_web_rag: bool = True
    ) -> str:
        """
        Build the complete 4-Zone Context Payload for LLM with External RAG support.
        
        CRITICAL FIX: This now conditionally inserts evidence to prevent "Evidence Block" leakage.
        When no evidence exists, it explicitly tells the LLM instead of leaving a template.
        
        Args:
            system_prompt: ZONE 1 - Agent identity and rules
            current_task: ZONE 4 - Current instruction
            query: Optional query for RAG retrieval (if None, uses current_task)
            top_k_rag: Number of relevant memories to retrieve from RAG
            use_short_term: Include ZONE 3 (recent conversation)
            use_long_term: Include ZONE 2 (RAG retrieval)
            format_style: "structured" or "conversational"
            enable_web_rag: Enable External Web RAG for URL content
            
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
        
        # Prepare to collect evidence from multiple sources
        rag_context = ""
        web_context = ""
        has_evidence = False
        
        # ZONE 2A: LONG-TERM MEMORY (Internal RAG from vector DB)
        if use_long_term and self.enable_rag and self.long_term:
            rag_query = query if query else current_task
            rag_context = self.long_term.get_relevant_context(
                query=rag_query,
                top_k=top_k_rag,
                format_style=format_style
            )
            
            if rag_context and rag_context.strip():
                has_evidence = True
        
        # ZONE 2B: EXTERNAL WEB RAG (Live URL fetching) + PERMANENT LEARNING
        if enable_web_rag and WEB_SCRAPER_AVAILABLE:
            # Check if query or current_task contains a URL
            search_text = query if query else current_task
            url = extract_url(search_text)
            
            if url:
                self.logger.info(f"🌐 External RAG: Fetching URL {url}")
                web_content = fetch_url_content(url, max_length=8000)
                
                # Clean the tag "[LIVE FETCH]" or "[CACHED SUMMARY]" for storage
                clean_content = web_content.replace("[LIVE FETCH]", "").replace("[CACHED SUMMARY]", "").strip()
                
                # Only add if fetch was successful
                if clean_content and not clean_content.startswith("Error"):
                    web_context = f"\n### LIVE WEB CONTENT FROM {url}:\n{clean_content}\n"
                    has_evidence = True
                    
                    # --- THE UPGRADE: PERMANENT LEARNING LOOP ---
                    # Inject web summary into Vector DB for cross-conversation recall
                    if self.enable_rag and self.long_term:
                        try:
                            self.logger.info(f"🧠 LEARNING: Injecting web summary into Long-Term Memory (Vector DB)")
                            
                            # Add to vector store with rich metadata
                            memory_id = self.long_term.add_memory(
                                text=clean_content,
                                metadata={
                                    "source": url,
                                    "type": "web_memory",
                                    "timestamp": datetime.now().isoformat(),
                                    "ingestion_method": "auto_web_rag"
                                }
                            )
                            
                            self.logger.info(f"✅ Successfully stored web content in Vector DB (ID: {memory_id})")
                        except Exception as e:
                            self.logger.error(f"Failed to store web content in Vector DB: {e}")
                    # ---------------------------------------
                else:
                    self.logger.warning(f"Failed to fetch URL: {web_content}")
        
        # ZONE 2: EVIDENCE BLOCK (Conditionally inserted)
        if has_evidence:
            zones.append("=" * 80)
            zones.append("[ZONE 2: RETRIEVED EVIDENCE]")
            zones.append("=" * 80)
            zones.append("### IMPORTANT: Use this evidence to answer accurately ###")
            zones.append("")
            
            if rag_context:
                zones.append("--- Internal Memory (Past Debates) ---")
                zones.append(rag_context)
                zones.append("")
            
            if web_context:
                zones.append("--- External Web Source (Live Data) ---")
                zones.append(web_context)
                zones.append("")
            
            zones.append("### END OF EVIDENCE ###")
            zones.append("")
        else:
            # CRITICAL: Explicitly tell LLM there's no external evidence
            zones.append("=" * 80)
            zones.append("[ZONE 2: EVIDENCE STATUS]")
            zones.append("=" * 80)
            zones.append("[NO EXTERNAL EVIDENCE RETRIEVED]")
            zones.append("Rely on your internal knowledge, but admit if you don't know.")
            zones.append("Do NOT hallucinate facts - if uncertain, say so explicitly.")
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
    
    def detect_memory_inconsistencies(
        self,
        role: str,
        new_statement: str,
        debate_id: Optional[str] = None,
        threshold: float = 0.3
    ) -> Dict[str, Any]:
        """
        Detect potential contradictions or inconsistencies in a role's statements.
        
        This is critical for role reversal to maintain coherence - agents should
        be aware when they're contradicting their previous stance.
        
        Args:
            role: Role to check for inconsistencies
            new_statement: New statement to check against history
            debate_id: Optional debate ID (uses current if None)
            threshold: Similarity threshold for detecting related statements
            
        Returns:
            Dictionary with inconsistency analysis:
            {
                'has_inconsistencies': bool,
                'related_statements': List[Dict],
                'consistency_score': float,
                'warnings': List[str]
            }
        """
        if not self.enable_rag or not self.long_term:
            return {
                'has_inconsistencies': False,
                'related_statements': [],
                'consistency_score': 1.0,
                'warnings': ['RAG disabled - cannot check consistency']
            }
        
        # Get role history
        role_history = self.get_role_history(role, debate_id)
        
        if not role_history:
            return {
                'has_inconsistencies': False,
                'related_statements': [],
                'consistency_score': 1.0,
                'warnings': ['No historical statements found']
            }
        
        # Search for semantically similar statements from the same role
        debate_id = debate_id or self.current_debate_id
        filter_metadata = {"role": role}
        if debate_id:
            filter_metadata["debate_id"] = debate_id
        
        try:
            similar_statements = self.search_memories(
                query=new_statement,
                top_k=5,
                filter_metadata=filter_metadata,
                similarity_threshold=threshold
            )
            
            warnings = []
            consistency_score = 1.0
            
            # Analyze for potential contradictions
            # (In a production system, you'd use NLI models here)
            if similar_statements:
                # Simple heuristic: check for negation keywords
                negation_keywords = ['not', 'never', 'no', 'false', 'wrong', 'incorrect', 
                                    'disagree', 'opposite', 'contrary', 'reject']
                
                new_lower = new_statement.lower()
                has_negation_new = any(word in new_lower for word in negation_keywords)
                
                for stmt in similar_statements:
                    old_content = stmt.get('content', '').lower()
                    has_negation_old = any(word in old_content for word in negation_keywords)
                    
                    # If one has negation and the other doesn't, potential contradiction
                    if has_negation_new != has_negation_old:
                        similarity = stmt.get('similarity_score', 0)
                        warnings.append(
                            f"Potential contradiction with Turn {stmt.get('metadata', {}).get('turn', '?')}: "
                            f"'{stmt.get('content', '')[:100]}...'"
                        )
                        consistency_score -= (similarity * 0.2)
                
                consistency_score = max(0.0, consistency_score)
            
            result = {
                'has_inconsistencies': len(warnings) > 0,
                'related_statements': similar_statements,
                'consistency_score': consistency_score,
                'warnings': warnings
            }
            
            if warnings:
                self.logger.warning(
                    f"⚠️  Detected {len(warnings)} potential inconsistencies for role '{role}'"
                )
            
            return result
            
        except Exception as e:
            self.logger.error(f"Failed to detect inconsistencies: {e}")
            return {
                'has_inconsistencies': False,
                'related_statements': [],
                'consistency_score': 1.0,
                'warnings': [f'Error during consistency check: {str(e)}']
            }
    
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
    
    # =========================================================================
    # PHASE 4: TOKEN OPTIMIZATION
    # =========================================================================
    
    def calculate_memory_value_score(
        self,
        memory_id: str,
        current_context: str = ""
    ) -> float:
        """
        Calculate value score for a memory to determine if it should be kept.
        
        Scoring factors:
        - Recency: More recent memories score higher
        - Relevance: Semantic similarity to current context
        - Interaction count: How often this memory is retrieved
        - Role importance: Moderator/critical turns score higher
        
        Returns:
            Score from 0.0 (low value) to 1.0 (high value)
        """
        if not self.enable_rag or not self.long_term:
            return 0.0
        
        try:
            # Get memory data
            results = self.long_term.search(memory_id, top_k=1)
            if not results:
                return 0.0
            
            memory = results[0]
            score = 0.0
            
            # Factor 1: Recency (40% weight)
            # Newer memories are more valuable
            turn = memory.metadata.get('turn', 0)
            max_turn = self.turn_counter or 1
            recency_score = turn / max_turn
            score += recency_score * 0.4
            
            # Factor 2: Relevance (40% weight)
            # If current_context provided, calculate semantic similarity
            if current_context and self.embedding_service:
                relevance_score = memory.score if hasattr(memory, 'score') else 0.5
                score += relevance_score * 0.4
            else:
                score += 0.2  # Default mid-range
            
            # Factor 3: Role importance (20% weight)
            # Moderator and critical roles are more valuable
            role = memory.metadata.get('role', '')
            if role == 'moderator':
                score += 0.2
            elif role in ['proponent', 'opponent']:
                score += 0.15
            else:
                score += 0.1
            
            return min(score, 1.0)
            
        except Exception as e:
            logging.error(f"Error calculating memory value score: {e}")
            return 0.5  # Default mid-range on error
    
    def truncate_low_value_memories(
        self,
        threshold: float = 0.3,
        current_context: str = ""
    ) -> Dict[str, Any]:
        """
        Remove memories with value scores below threshold to save tokens.
        
        Args:
            threshold: Minimum value score to keep (0.0-1.0)
            current_context: Current debate context for relevance scoring
            
        Returns:
            {
                "removed_count": int,
                "removed_ids": List[str],
                "tokens_saved_estimate": int
            }
        """
        if not self.enable_rag or not self.long_term:
            return {
                "removed_count": 0,
                "removed_ids": [],
                "tokens_saved_estimate": 0
            }
        
        try:
            # Get all memories
            all_memories = self.long_term.search("", top_k=1000)
            
            removed_ids = []
            total_text_length = 0
            
            for memory in all_memories:
                # Calculate value score
                score = self.calculate_memory_value_score(
                    memory.id, 
                    current_context
                )
                
                # Remove if below threshold
                if score < threshold:
                    removed_ids.append(memory.id)
                    total_text_length += len(memory.text)
                    # Delete from vector store
                    self.long_term.delete(memory.id)
            
            # Estimate tokens saved (~4 chars per token)
            tokens_saved = total_text_length // 4
            
            logging.info(f"🗑️ Truncated {len(removed_ids)} low-value memories (threshold: {threshold})")
            
            return {
                "removed_count": len(removed_ids),
                "removed_ids": removed_ids,
                "tokens_saved_estimate": tokens_saved
            }
            
        except Exception as e:
            logging.error(f"Error truncating low-value memories: {e}")
            return {
                "removed_count": 0,
                "removed_ids": [],
                "tokens_saved_estimate": 0,
                "error": str(e)
            }
    
    def deduplicate_memories(
        self,
        similarity_threshold: float = 0.95
    ) -> Dict[str, Any]:
        """
        Remove duplicate or near-duplicate memories to save tokens.
        
        Args:
            similarity_threshold: Cosine similarity above which memories are considered duplicates
            
        Returns:
            {
                "removed_count": int,
                "duplicate_pairs": List[tuple],
                "tokens_saved_estimate": int
            }
        """
        if not self.enable_rag or not self.long_term:
            return {
                "removed_count": 0,
                "duplicate_pairs": [],
                "tokens_saved_estimate": 0
            }
        
        try:
            # Get all memories
            all_memories = self.long_term.search("", top_k=1000)
            
            removed_ids = set()
            duplicate_pairs = []
            total_text_length = 0
            
            # Compare each memory with others
            for i, mem1 in enumerate(all_memories):
                if mem1.id in removed_ids:
                    continue
                
                for mem2 in all_memories[i+1:]:
                    if mem2.id in removed_ids:
                        continue
                    
                    # Check if embeddings are very similar
                    if hasattr(mem1, 'score') and hasattr(mem2, 'score'):
                        # Use cosine similarity between texts
                        similarity = self._calculate_similarity(mem1.text, mem2.text)
                        
                        if similarity >= similarity_threshold:
                            # Keep the more recent one (higher turn number)
                            turn1 = mem1.metadata.get('turn', 0)
                            turn2 = mem2.metadata.get('turn', 0)
                            
                            to_remove = mem1 if turn1 < turn2 else mem2
                            to_keep = mem2 if turn1 < turn2 else mem1
                            
                            removed_ids.add(to_remove.id)
                            duplicate_pairs.append((to_keep.id, to_remove.id))
                            total_text_length += len(to_remove.text)
                            
                            # Delete from vector store
                            self.long_term.delete(to_remove.id)
            
            # Estimate tokens saved
            tokens_saved = total_text_length // 4
            
            logging.info(f"🔗 Deduplicated {len(removed_ids)} near-duplicate memories")
            
            return {
                "removed_count": len(removed_ids),
                "duplicate_pairs": duplicate_pairs,
                "tokens_saved_estimate": tokens_saved
            }
            
        except Exception as e:
            logging.error(f"Error deduplicating memories: {e}")
            return {
                "removed_count": 0,
                "duplicate_pairs": [],
                "tokens_saved_estimate": 0,
                "error": str(e)
            }
    
    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """Calculate semantic similarity between two texts"""
        if not self.embedding_service:
            # Fallback: Simple overlap ratio
            words1 = set(text1.lower().split())
            words2 = set(text2.lower().split())
            if not words1 or not words2:
                return 0.0
            overlap = len(words1 & words2)
            return overlap / max(len(words1), len(words2))
        
        try:
            # Use embeddings for semantic similarity
            emb1 = self.embedding_service.embed_text(text1)
            emb2 = self.embedding_service.embed_text(text2)
            
            # Cosine similarity
            import numpy as np
            similarity = np.dot(emb1, emb2) / (np.linalg.norm(emb1) * np.linalg.norm(emb2))
            return float(similarity)
            
        except Exception as e:
            logging.warning(f"Similarity calculation failed: {e}")
            return 0.0
    
    def compress_old_memories(
        self,
        age_threshold: int = 20,
        compression_ratio: float = 0.5
    ) -> Dict[str, Any]:
        """
        Summarize old memories to reduce token usage while preserving key information.
        
        Args:
            age_threshold: Turns older than this are candidates for compression
            compression_ratio: Target length as fraction of original (0.0-1.0)
            
        Returns:
            {
                "compressed_count": int,
                "original_tokens": int,
                "compressed_tokens": int,
                "tokens_saved": int
            }
        """
        if not self.enable_rag or not self.long_term:
            return {
                "compressed_count": 0,
                "original_tokens": 0,
                "compressed_tokens": 0,
                "tokens_saved": 0
            }
        
        try:
            # Get all memories
            all_memories = self.long_term.search("", top_k=1000)
            current_turn = self.turn_counter or 1
            
            compressed_count = 0
            original_length = 0
            compressed_length = 0
            
            for memory in all_memories:
                turn = memory.metadata.get('turn', 0)
                age = current_turn - turn
                
                # Only compress old memories
                if age < age_threshold:
                    continue
                
                original_text = memory.text
                original_length += len(original_text)
                
                # Simple compression: keep first and last sentences + key phrases
                sentences = original_text.split('. ')
                target_sentences = max(1, int(len(sentences) * compression_ratio))
                
                if len(sentences) <= target_sentences:
                    continue  # Already short enough
                
                # Keep first sentence, last sentence, and sample middle
                if target_sentences == 1:
                    compressed_text = sentences[0] + '.'
                else:
                    first = sentences[0]
                    last = sentences[-1]
                    middle_count = target_sentences - 2
                    step = max(1, len(sentences[1:-1]) // middle_count) if middle_count > 0 else 1
                    middle = [sentences[i] for i in range(1, len(sentences)-1, step)][:middle_count]
                    
                    compressed_text = '. '.join([first] + middle + [last]) + '.'
                
                compressed_length += len(compressed_text)
                compressed_count += 1
                
                # Update memory in vector store with compressed version
                memory.metadata['compressed'] = True
                memory.metadata['original_length'] = len(original_text)
                self.long_term.delete(memory.id)
                self.long_term.add_text(
                    compressed_text,
                    metadata=memory.metadata
                )
            
            original_tokens = original_length // 4
            compressed_tokens = compressed_length // 4
            tokens_saved = original_tokens - compressed_tokens
            
            logging.info(f"📦 Compressed {compressed_count} old memories, saved ~{tokens_saved} tokens")
            
            return {
                "compressed_count": compressed_count,
                "original_tokens": original_tokens,
                "compressed_tokens": compressed_tokens,
                "tokens_saved": tokens_saved
            }
            
        except Exception as e:
            logging.error(f"Error compressing memories: {e}")
            return {
                "compressed_count": 0,
                "original_tokens": 0,
                "compressed_tokens": 0,
                "tokens_saved": 0,
                "error": str(e)
            }


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
