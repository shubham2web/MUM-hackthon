"""
LLM-as-Judge Relevance Scorer

Advanced relevance evaluation using LLM to judge retrieval quality.
Provides both scores and detailed rationales for debugging.
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import json
from typing import Dict, Any, List

# Import AiAgent from parent directory
try:
    from ai_agent import AiAgent
except ImportError:
    # Fallback if import fails
    print("Warning: Could not import AiAgent. LLM-as-Judge will not function.")
    AiAgent = None


class LLMRelevanceJudge:
    """
    Uses an LLM to judge the relevance of retrieved memories.
    
    This provides a more nuanced evaluation than pure semantic similarity,
    as it can understand context, partial matches, and reasoning.
    """
    
    def __init__(self):
        self.ai_agent = AiAgent()
        self.system_prompt = """You are an expert evaluator of information retrieval systems.
Your task is to judge whether a retrieved memory is relevant to a query.

Be objective and precise. Consider:
- Does the memory answer the query?
- Is it on the correct topic?
- Does it contain the requested information?
- Is it from the right source/role if specified?

Provide both a numerical score and clear reasoning."""
    
    def judge_relevance(
        self,
        query: str,
        retrieved_memory: str,
        context: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Judge the relevance of a retrieved memory to a query.
        
        Args:
            query: The search query
            retrieved_memory: The retrieved memory content
            context: Optional context (role, turn, metadata)
            
        Returns:
            Dictionary with 'score' (0-10) and 'rationale' (explanation)
        """
        # Build context string if provided
        context_str = ""
        if context:
            context_parts = []
            if 'role' in context:
                context_parts.append(f"Role: {context['role']}")
            if 'turn' in context:
                context_parts.append(f"Turn: {context['turn']}")
            if 'metadata' in context:
                context_parts.append(f"Metadata: {context['metadata']}")
            
            if context_parts:
                context_str = f"\n\nContext:\n{', '.join(context_parts)}"
        
        # Build prompt with JSON response format
        user_prompt = f"""Query: {query}

Retrieved Memory: {retrieved_memory}{context_str}

Is this memory relevant to answering the query?

Respond in JSON format with exactly two keys:
1. "score": A number from 0 (completely irrelevant) to 10 (perfectly relevant)
2. "rationale": A brief explanation (1-2 sentences) for your score

Scoring guide:
- 0-3: Irrelevant (wrong topic, no useful information)
- 4-6: Partially relevant (correct topic but missing key information)
- 7-10: Highly relevant (contains answer or directly addresses query)

Your response (JSON only):"""
        
        try:
            # Generate LLM judgment
            full_response = ""
            for chunk in self.ai_agent.stream(
                user_message=user_prompt,
                system_prompt=self.system_prompt,
                max_tokens=200
            ):
                full_response += chunk
            
            # Parse JSON response
            # Try to extract JSON from response (LLM might add text around it)
            json_start = full_response.find('{')
            json_end = full_response.rfind('}') + 1
            
            if json_start >= 0 and json_end > json_start:
                json_str = full_response[json_start:json_end]
                result = json.loads(json_str)
                
                # Validate response format
                if 'score' in result and 'rationale' in result:
                    # Normalize score to 0-1 range
                    normalized_score = result['score'] / 10.0
                    return {
                        'score': normalized_score,
                        'raw_score': result['score'],
                        'rationale': result['rationale'],
                        'success': True
                    }
            
            # Fallback if JSON parsing fails
            return {
                'score': 0.5,
                'raw_score': 5,
                'rationale': 'Failed to parse LLM response',
                'success': False,
                'raw_response': full_response
            }
            
        except Exception as e:
            return {
                'score': 0.5,
                'raw_score': 5,
                'rationale': f'Error during judgment: {str(e)}',
                'success': False
            }
    
    def judge_batch(
        self,
        query: str,
        retrieved_memories: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Judge multiple retrieved memories for a single query.
        
        Args:
            query: The search query
            retrieved_memories: List of dicts with 'content' and optional 'context'
            
        Returns:
            List of judgment results with scores and rationales
        """
        results = []
        
        for i, memory in enumerate(retrieved_memories):
            content = memory.get('content', '')
            context = memory.get('context', {})
            
            judgment = self.judge_relevance(query, content, context)
            judgment['memory_index'] = i
            results.append(judgment)
        
        return results
    
    def evaluate_test_case(
        self,
        query: str,
        retrieved_memories: List[str],
        expected_indices: List[int]
    ) -> Dict[str, Any]:
        """
        Evaluate a test case using LLM judgments.
        
        Args:
            query: Search query
            retrieved_memories: List of retrieved memory contents
            expected_indices: Indices of expected/correct memories
            
        Returns:
            Evaluation metrics with LLM-based scoring
        """
        judgments = []
        
        for i, memory in enumerate(retrieved_memories):
            judgment = self.judge_relevance(query, memory)
            judgment['memory_index'] = i
            judgment['is_expected'] = i in expected_indices
            judgments.append(judgment)
        
        # Calculate metrics
        avg_score_expected = sum(
            j['score'] for j in judgments if j['is_expected']
        ) / len(expected_indices) if expected_indices else 0.0
        
        avg_score_unexpected = sum(
            j['score'] for j in judgments if not j['is_expected']
        ) / max(1, len(judgments) - len(expected_indices))
        
        return {
            'query': query,
            'judgments': judgments,
            'avg_score_expected': avg_score_expected,
            'avg_score_unexpected': avg_score_unexpected,
            'score_gap': avg_score_expected - avg_score_unexpected,
            'total_memories': len(retrieved_memories),
            'expected_count': len(expected_indices)
        }


def demo_llm_judge():
    """Demonstrate LLM-as-Judge functionality."""
    judge = LLMRelevanceJudge()
    
    # Example test case
    query = "What did the proponent say about nuclear safety?"
    
    memories = [
        "Nuclear energy is the safest energy source with lowest death rate per TWh.",  # Highly relevant
        "Solar panel costs have dropped 90% in the last decade.",  # Irrelevant
        "Modern reactors have passive safety systems that prevent meltdowns.",  # Relevant
        "France gets 70% of electricity from nuclear power.",  # Partially relevant
    ]
    
    print("🎯 LLM-as-Judge Demo")
    print("=" * 70)
    print(f"Query: {query}\n")
    
    for i, memory in enumerate(memories):
        print(f"Memory {i + 1}: {memory}")
        result = judge.judge_relevance(query, memory)
        
        if result['success']:
            print(f"  Score: {result['raw_score']}/10 ({result['score']:.2f})")
            print(f"  Rationale: {result['rationale']}")
        else:
            print(f"  ❌ Error: {result['rationale']}")
        
        print()
    
    print("=" * 70)


if __name__ == "__main__":
    # Run demo
    demo_llm_judge()
