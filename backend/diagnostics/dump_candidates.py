"""
Diagnostic A: Per-test candidate & score dump
Compare fusion-disabled vs smart-fusion modes
"""
import json
import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from memory.memory_manager import get_memory_manager
from tests.test_rag_benchmark import RAGBenchmark
from tests.rag_test_scenarios import load_all_test_scenarios


def dump_for_mode(mode_name: str, fusion_enabled: bool):
    """Dump candidates for a specific mode."""
    print(f"\n{'='*70}")
    print(f"DUMPING CANDIDATES FOR MODE: {mode_name}")
    print(f"{'='*70}\n")
    
    # Redirect print statements to suppress emoji encoding errors
    import io
    old_stdout = sys.stdout
    sys.stdout = io.StringIO()
    
    try:
        # Initialize memory with appropriate config
        memory = get_memory_manager(long_term_backend="faiss")
        
        # Override fusion setting
        if hasattr(memory, 'vector_store') and hasattr(memory.vector_store, 'hybrid_fusion'):
            if not fusion_enabled:
                # Disable fusion by setting to None
                memory.vector_store.hybrid_fusion = None
        
        # Create benchmark and load scenarios
        benchmark = RAGBenchmark(memory)
        load_all_test_scenarios(benchmark)
    finally:
        sys.stdout = old_stdout
    
    if fusion_enabled:
        print("Status: Fusion ENABLED (smart query analysis)")
    else:
        print("Status: Fusion DISABLED (fallback mode)")
    
    out = {}
    for idx, test in enumerate(benchmark.test_cases, 1):
        print(f"[{idx}/{len(benchmark.test_cases)}] {test['scenario_name'][:40]}...")
        query = test['query']
        
        # Search with top_k=20 for diagnostic purposes
        results = memory.search_long_term_memory(query=query, top_k=20)
        
        # Extract diagnostic info
        out[test['scenario_name']] = {
            'query': query,
            'expected_count': len(test['expected_memories']),
            'retrieved_count': len(results),
            'candidates': [{
                'rank': i + 1,
                'id': r.get('id', 'N/A'),
                'text_preview': r.get('text', '')[:80],
                'vector_score': r.get('vector_score', 0.0),
                'lexical_score': r.get('lexical_score', 0.0),
                'hybrid_score': r.get('hybrid_score', None),
                'final_score': r.get('score', 0.0),
                'metadata_boost_applied': r.get('metadata', {}).get('_metadata_boost_applied', False),
                'turn': r.get('metadata', {}).get('turn', None),
                'role': r.get('metadata', {}).get('role', None),
            } for i, r in enumerate(results)]
        }
    
    # Save to file
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"diagnostics_{mode_name}_{timestamp}.json"
    filepath = os.path.join(os.path.dirname(__file__), filename)
    
    with open(filepath, "w", encoding='utf-8') as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    
    print(f"\n✅ Wrote: {filepath}")
    return out, filepath


def compare_modes(dump_a, dump_b):
    """Compare two mode dumps."""
    print(f"\n{'='*70}")
    print("COMPARISON SUMMARY")
    print(f"{'='*70}\n")
    
    for test_name in dump_a.keys():
        if test_name not in dump_b:
            continue
        
        a_data = dump_a[test_name]
        b_data = dump_b[test_name]
        
        # Get candidate IDs
        ids_a = set(c['id'] for c in a_data['candidates'])
        ids_b = set(c['id'] for c in b_data['candidates'])
        
        overlap = ids_a.intersection(ids_b)
        overlap_pct = len(overlap) / max(len(ids_a), 1) * 100
        
        # Score statistics
        a_scores = [c['final_score'] for c in a_data['candidates']]
        b_scores = [c['final_score'] for c in b_data['candidates']]
        
        print(f"Test: {test_name}")
        print(f"  Candidates: A={len(ids_a)}, B={len(ids_b)}, Overlap={len(overlap)} ({overlap_pct:.1f}%)")
        print(f"  Score Avg:  A={sum(a_scores)/len(a_scores):.4f}, B={sum(b_scores)/len(b_scores):.4f}")
        
        # Check for missing IDs
        missing_in_b = ids_a - ids_b
        if missing_in_b:
            print(f"  ⚠️ {len(missing_in_b)} candidates in A but NOT in B!")
        
        new_in_b = ids_b - ids_a
        if new_in_b:
            print(f"  ⚠️ {len(new_in_b)} NEW candidates in B not in A!")
        
        print()


if __name__ == "__main__":
    # Set UTF-8 encoding for Windows console
    import sys
    if sys.platform == 'win32':
        try:
            sys.stdout.reconfigure(encoding='utf-8')
        except:
            pass
    
    print("RAG Diagnostic Tool: Candidate Dump & Comparison")
    print("=" * 70)
    
    # Dump both modes
    dump_a, file_a = dump_for_mode("fusion_disabled", fusion_enabled=False)
    dump_b, file_b = dump_for_mode("smart_fusion_vector_only", fusion_enabled=True)
    
    # Compare
    compare_modes(dump_a, dump_b)
    
    print(f"\n{'='*70}")
    print("DIAGNOSTIC COMPLETE")
    print(f"Files saved: {file_a}, {file_b}")
    print(f"{'='*70}\n")
