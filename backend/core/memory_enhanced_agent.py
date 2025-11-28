"""
Memory-Enhanced AI Agent

Wrapper around AiAgent that automatically uses Hybrid Memory System
to build context payloads with the 4-Zone architecture.
"""
from __future__ import annotations

import logging
from typing import Optional, Dict, Any, Iterator

from core.ai_agent import AiAgent, AiResponse
from memory.memory_manager import HybridMemoryManager


def condense_query(chat_history: str, latest_user_input: str, llm_client: AiAgent) -> str:
    """
    Uses LLM to rewrite the user query based on chat history.
    
    This solves "Goldfish Memory" - when user says "go to the sources",
    this function knows they meant "go to the NDTV source I just sent."
    
    Args:
        chat_history: Recent conversation history
        latest_user_input: Current user message
        llm_client: AiAgent instance for LLM calls
        
    Returns:
        Standalone query that includes context from history
        
    Examples:
        Input: "go to the sources"
        Context: [User sent NDTV link previously]
        Output: "Verify the facts in the NDTV link provided in the previous turn."
        
        Input: "what about that article?"
        Context: [Discussion about climate change article]
        Output: "What does the climate change article say about renewable energy?"
    """
    system_prompt = """Given the following conversation and a follow up question, 
rephrase the follow up question to be a standalone question. 
If the follow up question is referencing a link or context from the history, include it explicitly.

DO NOT answer the question - just rephrase it to be self-contained."""
    
    # Construct prompt with history
    prompt = f"""{system_prompt}

History:
{chat_history}

Follow Up Input: {latest_user_input}

Standalone Question:"""
    
    try:
        # Call LLM with fast model (Zone 3 from architecture)
        response = llm_client.call_blocking(
            user_message=prompt,
            system_prompt=None,
            max_tokens=256  # Short response needed
        )
        
        condensed = response.text.strip()
        logging.info(f"Query condensed: '{latest_user_input}' → '{condensed}'")
        return condensed
        
    except Exception as e:
        logging.error(f"Query condensation failed: {e}")
        # Fallback to original input
        return latest_user_input


class MemoryEnhancedAgent:
    """
    AI Agent with integrated Hybrid Memory System.
    
    Automatically builds 4-zone context payloads:
    - ZONE 1: System prompt (agent role/identity)
    - ZONE 2: RAG retrieval (relevant past context)
    - ZONE 3: Short-term memory (recent conversation)
    - ZONE 4: Current task (new instruction)
    
    Usage:
        agent = MemoryEnhancedAgent(role="proponent")
        
        # Agent automatically uses memory for context
        response = agent.generate(
            task="Argue in favor of renewable energy",
            system_prompt="You are a proponent debater..."
        )
        
        # Response is automatically stored in memory
    """
    
    def __init__(
        self,
        role: str,
        model_name: str = "llama3",
        memory_manager: Optional[HybridMemoryManager] = None,
        auto_store_responses: bool = True
    ):
        """
        Initialize memory-enhanced agent.
        
        Args:
            role: Agent role (proponent, opponent, moderator, etc.)
            model_name: LLM model to use
            memory_manager: Optional custom memory manager
            auto_store_responses: Automatically store responses in memory
        """
        self.logger = logging.getLogger(self.__class__.__name__)
        self.role = role
        self.auto_store_responses = auto_store_responses
        
        # Initialize base AI agent
        self.ai_agent = AiAgent(model_name=model_name)
        
        # Initialize or use provided memory manager
        if memory_manager is None:
            from memory.memory_manager import get_memory_manager
            self.memory = get_memory_manager()
        else:
            self.memory = memory_manager
        
        self.logger.info(f"Memory-enhanced agent initialized: {role}")
    
    def generate(
        self,
        task: str,
        system_prompt: Optional[str] = None,
        query_for_rag: Optional[str] = None,
        max_tokens: int = 1024,
        use_memory: bool = True,
        use_rag: bool = True,
        top_k_rag: int = 4,
        store_task: bool = False,
        task_metadata: Optional[Dict[str, Any]] = None
    ) -> AiResponse:
        """
        Generate response with memory-enhanced context.
        
        Args:
            task: Current task/instruction for the agent
            system_prompt: Optional system prompt (ZONE 1)
            query_for_rag: Optional custom query for RAG (defaults to task)
            max_tokens: Maximum tokens to generate
            use_memory: Whether to use memory system
            use_rag: Whether to use RAG retrieval (ZONE 2)
            top_k_rag: Number of relevant memories to retrieve
            store_task: Whether to store the task in memory
            task_metadata: Optional metadata for task
            
        Returns:
            AiResponse object
        """
        # Optionally store task in memory
        if store_task and use_memory:
            self.memory.add_interaction(
                role="user",
                content=task,
                metadata=task_metadata,
                store_in_rag=True
            )
        
        # Build context with memory if enabled
        if use_memory:
            context_payload = self.memory.build_context_payload(
                system_prompt=system_prompt or "",
                current_task=task,
                query=query_for_rag,
                top_k_rag=top_k_rag,
                use_short_term=True,
                use_long_term=use_rag
            )
            
            # Use the full context payload as user message
            user_message = context_payload
            system_msg = None  # System prompt is in ZONE 1
        else:
            # Without memory, use traditional approach
            user_message = task
            system_msg = system_prompt
        
        # Generate response
        response = self.ai_agent.call_blocking(
            user_message=user_message,
            system_prompt=system_msg,
            max_tokens=max_tokens
        )
        
        # Auto-store response in memory
        if self.auto_store_responses and use_memory:
            self.memory.add_interaction(
                role=self.role,
                content=response.text,
                metadata={
                    "provider": response.provider,
                    "latency": response.latency,
                    "model": self.ai_agent.model_name
                },
                store_in_rag=True
            )
        
        return response
    
    def generate_streaming(
        self,
        task: str,
        system_prompt: Optional[str] = None,
        query_for_rag: Optional[str] = None,
        max_tokens: int = 1024,
        use_memory: bool = True,
        use_rag: bool = True,
        top_k_rag: int = 4,
        store_task: bool = False
    ) -> Iterator[str]:
        """
        Generate streaming response with memory-enhanced context.
        
        Args:
            Same as generate() method
            
        Yields:
            Response chunks
        """
        # Store task if requested
        if store_task and use_memory:
            self.memory.add_interaction(
                role="user",
                content=task,
                store_in_rag=True
            )
        
        # Build context with memory
        if use_memory:
            context_payload = self.memory.build_context_payload(
                system_prompt=system_prompt or "",
                current_task=task,
                query=query_for_rag,
                top_k_rag=top_k_rag,
                use_short_term=True,
                use_long_term=use_rag
            )
            user_message = context_payload
            system_msg = None
        else:
            user_message = task
            system_msg = system_prompt
        
        # Stream response
        full_response = ""
        for chunk in self.ai_agent.stream(
            user_message=user_message,
            system_prompt=system_msg,
            max_tokens=max_tokens
        ):
            full_response += chunk
            yield chunk
        
        # Store complete response
        if self.auto_store_responses and use_memory:
            self.memory.add_interaction(
                role=self.role,
                content=full_response,
                store_in_rag=True
            )
    
    def add_to_memory(
        self,
        content: str,
        role: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Manually add content to memory.
        
        Args:
            content: Content to store
            role: Role (defaults to agent's role)
            metadata: Optional metadata
        """
        self.memory.add_interaction(
            role=role or self.role,
            content=content,
            metadata=metadata,
            store_in_rag=True
        )
    
    def search_memory(
        self,
        query: str,
        top_k: int = 10,
        filter_metadata: Optional[Dict[str, Any]] = None
    ):
        """Search agent's memory"""
        return self.memory.search_memories(
            query=query,
            top_k=top_k,
            filter_metadata=filter_metadata
        )
    
    def get_memory_summary(self) -> Dict[str, Any]:
        """Get memory system summary"""
        return self.memory.get_memory_summary()
    
    def __repr__(self) -> str:
        return f"MemoryEnhancedAgent(role={self.role}, memory={self.memory})"
