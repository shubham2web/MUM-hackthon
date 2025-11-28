"""
HGB Diagnostic - Check if HGB soft bias is actually changing scores
"""

import sys
import os
from pathlib import Path

backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from memory.memory_manager import get_memory_manager
from tests.test_rag_benchmark import RAGBenchmark
from tests.rag_test_scenarios import load_all_test_scenarios

def diagnose_hgb():
    """Check HGB impact on scores"""
    
    print("\n" + "="*70)
    print("HGB SOFT BIAS DIAGNOSTIC")
    print("="*70 + "\n")
    
    # Initialize with HGB enabled
    memory = get_memory_manager(long_term_backend="faiss")
    benchmark = RAGBenchmark(memory)
    load_all_test_scenarios(benchmark)
    
    # Run first test case
    test_case = benchmark.test_cases[0]
    print(f"Test: {test_case.name}")
    print(f"Query: {test_case.query}\n")
    
    # Setup memories
    memory.clear()
    for role, content, metadata in test_case.setup_memories:
        memory.add_interaction(role=role, content=content, metadata=metadata, store_in_rag=True)
    
    # Search and inspect scores
    results = memory.search_memories(query=test_case.query, top_k=5)
    
    print(f"Retrieved {len(results)} results:\n")
    for i, result in enumerate(results, 1):
        print(f"{i}. Score: {result.get('score', 0):.4f}")
        print(f"   Text: {result.get('text', '')[:80]}...")
        
        # Check for HGB-specific fields
        if 'rerank_score' in result:
            print(f"   Rerank Score: {result['rerank_score']:.4f}")
        if 'hybrid_score_norm' in result:
            print(f"   Hybrid Norm: {result['hybrid_score_norm']:.4f}")
        if 'final_score' in result:
            print(f"   Final Score: {result['final_score']:.4f}")
        print()
    
    print("="*70)

if __name__ == "__main__":
    try:
        diagnose_hgb()
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
