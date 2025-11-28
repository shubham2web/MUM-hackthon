"""
Benchmark Metadata Audit - Check metadata availability in actual benchmark test data
Runs real benchmark queries and analyzes metadata coverage in retrieved results
"""

import sys
import os
from pathlib import Path

# Add backend to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from memory.vector_store import VectorStore
from tests.test_rag_benchmark import RAGBenchmark
from tests.rag_test_scenarios import load_all_test_scenarios
import statistics
from collections import defaultdict

def audit_benchmark_metadata():
    """Audit metadata in actual benchmark retrieved results"""
    
    print("\n" + "="*70)
    print("BENCHMARK METADATA AUDIT")
    print("="*70)
    print("Checking metadata availability in ACTUAL benchmark test queries")
    print("="*70 + "\n")
    
    # Initialize vector store
    print("Initializing vector store...")
    vector_store = VectorStore()
    
    # Initialize benchmark to get test cases
    print("Loading benchmark test cases...")
    from memory.memory_manager import get_memory_manager
    memory = get_memory_manager(long_term_backend="faiss")
    benchmark = RAGBenchmark(memory)
    load_all_test_scenarios(benchmark)
    
    test_cases = benchmark.test_cases
    print(f"Total test cases: {len(test_cases)}\n")
    
    # Track metadata across all queries
    all_metadata = []
    metadata_fields = {
        'recency_score': [],
        'authority_score': [],
        'source': [],
        'timestamp': [],
        'conversation_id': [],
        'message_id': [],
        'role': []
    }
    missing_counts = {field: 0 for field in metadata_fields.keys()}
    
    print("Running queries and collecting metadata...")
    print("-" * 70)
    
    for i, test_case in enumerate(test_cases, 1):
        query = test_case.query
        print(f"\n{i}. Query: {query[:60]}{'...' if len(query) > 60 else ''}")
        
        try:
            # Run query with top_k=5 (typical retrieval size)
            results = vector_store.query(query, top_k=5)
            
            if not results or len(results) == 0:
                print(f"   No results returned")
                continue
            
            print(f"   Retrieved: {len(results)} documents")
            
            # Collect metadata from results
            for result in results:
                metadata = result.get('metadata', {})
                all_metadata.append(metadata)
                
                # Track each field
                for field in metadata_fields.keys():
                    if field in metadata and metadata[field] is not None:
                        value = metadata[field]
                        # Skip empty strings
                        if isinstance(value, str) and value.strip() == '':
                            missing_counts[field] += 1
                        else:
                            metadata_fields[field].append(value)
                    else:
                        missing_counts[field] += 1
            
        except Exception as e:
            print(f"   Error: {e}")
            continue
    
    # Analysis
    total_retrieved = len(all_metadata)
    
    print("\n" + "="*70)
    print("BENCHMARK METADATA COVERAGE SUMMARY")
    print("="*70)
    print(f"Total documents retrieved: {total_retrieved}")
    print(f"From {len(test_cases)} benchmark queries\n")
    
    if total_retrieved == 0:
        print("NO DOCUMENTS RETRIEVED - Cannot audit metadata")
        print("\nRECOMMENDATION:")
        print("  SKIP Step 3 (Metadata Boost) - No data to retrieve")
        print("  PROCEED to Step 4 (HGB Soft Bias) - Model-based approach")
        return
    
    print("-"*70)
    print(f"{'Field':<20} {'Present':<10} {'Missing':<10} {'Coverage':<10}")
    print("-"*70)
    
    for field in metadata_fields.keys():
        present = len(metadata_fields[field])
        missing = missing_counts[field]
        coverage = (present / total_retrieved * 100) if total_retrieved > 0 else 0
        print(f"{field:<20} {present:<10} {missing:<10} {coverage:>6.1f}%")
    
    # Detailed analysis for recency and authority
    print("\n" + "-"*70)
    print("RECENCY SCORE ANALYSIS")
    print("-"*70)
    
    if metadata_fields['recency_score']:
        try:
            recency_scores = [float(s) for s in metadata_fields['recency_score'] if s is not None]
            print(f"Count:     {len(recency_scores)}")
            print(f"Min:       {min(recency_scores):.4f}")
            print(f"Max:       {max(recency_scores):.4f}")
            print(f"Mean:      {statistics.mean(recency_scores):.4f}")
            print(f"Median:    {statistics.median(recency_scores):.4f}")
            print(f"Std Dev:   {statistics.stdev(recency_scores) if len(recency_scores) > 1 else 0:.4f}")
            
            # Check if normalized
            if min(recency_scores) >= 0 and max(recency_scores) <= 1:
                print("Status:    ✅ NORMALIZED (0-1 range)")
            else:
                print("Status:    ⚠️ NOT NORMALIZED - needs normalization!")
        except Exception as e:
            print(f"Error analyzing recency scores: {e}")
    else:
        print("❌ NO RECENCY SCORES FOUND IN BENCHMARK DATA")
    
    print("\n" + "-"*70)
    print("AUTHORITY SCORE ANALYSIS")
    print("-"*70)
    
    if metadata_fields['authority_score']:
        try:
            authority_scores = [float(s) for s in metadata_fields['authority_score'] if s is not None]
            print(f"Count:     {len(authority_scores)}")
            print(f"Min:       {min(authority_scores):.4f}")
            print(f"Max:       {max(authority_scores):.4f}")
            print(f"Mean:      {statistics.mean(authority_scores):.4f}")
            print(f"Median:    {statistics.median(authority_scores):.4f}")
            print(f"Std Dev:   {statistics.stdev(authority_scores) if len(authority_scores) > 1 else 0:.4f}")
            
            # Check if normalized
            if min(authority_scores) >= 0 and max(authority_scores) <= 1:
                print("Status:    ✅ NORMALIZED (0-1 range)")
            else:
                print("Status:    ⚠️ NOT NORMALIZED - needs normalization!")
        except Exception as e:
            print(f"Error analyzing authority scores: {e}")
    else:
        print("❌ NO AUTHORITY SCORES FOUND IN BENCHMARK DATA")
    
    # RECOMMENDATION
    print("\n" + "="*70)
    print("RECOMMENDATION")
    print("="*70)
    
    recency_coverage = (len(metadata_fields['recency_score']) / total_retrieved * 100) if total_retrieved > 0 else 0
    authority_coverage = (len(metadata_fields['authority_score']) / total_retrieved * 100) if total_retrieved > 0 else 0
    
    print(f"\nMetadata Coverage in Benchmark Results:")
    print(f"  Recency Score:   {recency_coverage:.1f}%")
    print(f"  Authority Score: {authority_coverage:.1f}%")
    
    if recency_coverage < 30 or authority_coverage < 30:
        print(f"\n❌ SKIP Step 3 (Metadata Boost) - Insufficient metadata coverage")
        print(f"   Threshold: Need >30% coverage for both metrics")
        print(f"   Recency:   {recency_coverage:.1f}% {'✅' if recency_coverage >= 30 else '❌'}")
        print(f"   Authority: {authority_coverage:.1f}% {'✅' if authority_coverage >= 30 else '❌'}")
        print(f"\n✅ PROCEED to Step 4 (HGB Soft Bias)")
        print(f"   Reason: Model-based approach, independent of metadata")
        print(f"   Expected: +2-3% improvement with conservative weight (w=0.3)")
    elif recency_coverage < 70 or authority_coverage < 70:
        print(f"\n⚠️ PROCEED with Step 3 (Metadata Boost) WITH CAUTION")
        print(f"   Coverage: {min(recency_coverage, authority_coverage):.1f}% (moderate)")
        print(f"   Strategy: Use NULL-SAFE multiplicative boost")
        print(f"   Formula:  final = hybrid * (1 + w*score) where score defaults to 0.5 if missing")
        print(f"   Weights:  Start conservative - recency=0.1, authority=0.2")
        print(f"   Expected: +1-2% if metadata helps, rollback if regression")
    else:
        print(f"\n✅ PROCEED with Step 3 (Metadata Boost) - Good coverage")
        print(f"   Coverage: {min(recency_coverage, authority_coverage):.1f}% (excellent)")
        print(f"   Strategy: Full multiplicative boost with grid search")
        print(f"   Formula:  final = hybrid * (1 + recency_w*recency + authority_w*authority)")
        print(f"   Grid:     recency ∈ [0.2, 0.4], authority ∈ [0.4, 0.7]")
        print(f"   Expected: +2-4% improvement")
    
    print("="*70 + "\n")

if __name__ == "__main__":
    try:
        audit_benchmark_metadata()
    except Exception as e:
        print(f"\nError during audit: {e}")
        import traceback
        traceback.print_exc()
