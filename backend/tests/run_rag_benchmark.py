"""
RAG Benchmark Runner

Execute the complete RAG retrieval benchmark suite and generate reports.

Usage:
    python run_rag_benchmark.py [--verbose] [--export]

Options:
    --verbose    Show detailed output during benchmark execution
    --export     Export results to JSON file
"""

import sys
import os
import argparse
import json
from datetime import datetime
from dotenv import load_dotenv

# Load .env file for API keys
load_dotenv()

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from memory.memory_manager import get_memory_manager
from tests.test_rag_benchmark import RAGBenchmark
from tests.rag_test_scenarios import load_all_test_scenarios


def run_full_benchmark(verbose: bool = True, export: bool = True):
    """
    Execute complete RAG benchmark suite.
    
    Args:
        verbose: If True, print detailed output during execution
        export: If True, save results to JSON file
        
    Returns:
        Dictionary containing benchmark results
    """
    # Set UTF-8 encoding for Windows console
    import sys
    if sys.platform == 'win32':
        try:
            sys.stdout.reconfigure(encoding='utf-8')
        except:
            pass
    
    print("RAG RETRIEVAL BENCHMARK")
    print("=" * 70)
    print("Objective: Validate RAG retrieval quality with >85% relevance score")
    print("=" * 70 + "\n")
    
    # Initialize memory system
    try:
        memory = get_memory_manager(
            long_term_backend="faiss"  # Use FAISS to avoid Python 3.13 ChromaDB compatibility issues
        )
        print("✅ Memory manager initialized (re-ranking enabled by default)")
    except Exception as e:
        print(f"❌ Failed to initialize memory manager: {e}")
        return None
    
    # Create benchmark instance
    benchmark = RAGBenchmark(memory)
    print("✅ Benchmark harness created\n")
    
    # Load all test scenarios
    print("📋 Loading test scenarios...")
    load_all_test_scenarios(benchmark)
    print()
    
    # Run benchmark
    print("🚀 Executing benchmark suite...\n")
    start_time = datetime.now()
    
    results = benchmark.run_benchmark(verbose=verbose)
    
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()
    
    # Add execution metadata
    results["metadata"] = {
        "execution_time": duration,
        "start_time": start_time.isoformat(),
        "end_time": end_time.isoformat(),
        "memory_backend": memory.vector_store.backend if hasattr(memory, 'vector_store') else "unknown",
        "embedding_model": memory.embedding_service.model_name if hasattr(memory, 'embedding_service') else "unknown"
    }
    
    # Print formatted report
    benchmark.print_report(results)
    
    # Export results if requested
    if export:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"rag_benchmark_results_{timestamp}.json"
        benchmark.export_results(results, filename)
    
    # Print execution summary
    print(f"Execution time: {duration:.2f} seconds")
    print(f"Average time per test: {duration / results['summary']['total_tests']:.2f} seconds")
    
    # Provide recommendations based on results
    print_recommendations(results)
    
    return results


def print_recommendations(results: dict):
    """
    Print optimization recommendations based on benchmark results.
    
    Args:
        results: Benchmark results dictionary
    """
    summary = results["summary"]
    
    print("\n" + "=" * 70)
    print("RECOMMENDATIONS")
    print("=" * 70)
    
    if summary["target_met"]:
        print("[PASS] RAG system is performing well! (>=85% relevance)")
        print("\nNext steps:")
        print("  1. Deploy to production with monitoring")
        print("  2. Collect real-world usage data")
        print("  3. Move to Priority 3: Memory coherence & token optimization")
    else:
        print("[FAIL] RAG system needs optimization (target not met)")
        print(f"\nCurrent relevance: {summary['avg_relevance_score']:.1%}")
        print(f"Target relevance: 85%")
        print(f"Gap: {(0.85 - summary['avg_relevance_score']) * 100:.1f} percentage points")
        
        print("\nSuggested optimizations:")
        
        # Low precision = too many false positives
        if summary["avg_precision"] < 0.80:
            print("\n  1. LOW PRECISION (too many irrelevant results)")
            print("     - Increase similarity threshold (e.g., 0.75 instead of 0.5)")
            print("     - Enable stricter metadata filtering")
            print("     - Consider re-ranking retrieved results")
        
        # Low recall = missing relevant memories
        if summary["avg_recall"] < 0.90:
            print("\n  2. LOW RECALL (missing relevant memories)")
            print("     - Increase top_k (retrieve more results)")
            print("     - Try hybrid search (semantic + keyword)")
            print("     - Expand queries with synonyms")
        
        # Low relevance = embedding quality issue
        if summary["avg_relevance_score"] < 0.75:
            print("\n  3. LOW RELEVANCE SCORE (embedding quality)")
            print("     - Try better embedding model:")
            print("       * sentence-transformers/all-mpnet-base-v2 (768 dim)")
            print("       * BAAI/bge-small-en-v1.5 (optimized for retrieval)")
            print("     - Tune embedding generation (normalize, pooling)")
        
        # Check individual test failures
        failed_tests = [r for r in results["individual_results"] if not r.get("passed", False)]
        if failed_tests:
            print(f"\n  4. FAILING TEST PATTERNS")
            print(f"     {len(failed_tests)} tests failed. Review:")
            for test in failed_tests[:3]:  # Show first 3
                print(f"     - {test['test']}")
            if len(failed_tests) > 3:
                print(f"     ... and {len(failed_tests) - 3} more")
    
    print("=" * 70 + "\n")


def run_single_test(test_name: str, verbose: bool = True):
    """
    Run a single test case by name.
    
    Args:
        test_name: Name of test to run
        verbose: If True, print detailed output
    """
    memory = get_memory_manager()
    benchmark = RAGBenchmark(memory)
    load_all_test_scenarios(benchmark)
    
    # Find test by name
    matching_tests = [tc for tc in benchmark.test_cases if test_name.lower() in tc.name.lower()]
    
    if not matching_tests:
        print(f"No test found matching: {test_name}")
        print("\nAvailable tests:")
        for tc in benchmark.test_cases:
            print(f"  - {tc.name}")
        return
    
    if len(matching_tests) > 1:
        print(f"Multiple tests match '{test_name}':")
        for tc in matching_tests:
            print(f"  - {tc.name}")
        return
    
    # Run single test
    test = matching_tests[0]
    benchmark.test_cases = [test]
    
    print(f"Running single test: {test.name}\n")
    results = benchmark.run_benchmark(verbose=verbose)
    benchmark.print_report(results)


def main():
    """Main entry point for benchmark runner."""
    parser = argparse.ArgumentParser(
        description="Run RAG retrieval benchmark suite",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_rag_benchmark.py                    # Run all tests
  python run_rag_benchmark.py --verbose          # Show detailed output
  python run_rag_benchmark.py --no-export        # Don't save JSON results
  python run_rag_benchmark.py --test "Role Reversal"  # Run specific test
        """
    )
    
    parser.add_argument(
        '--verbose',
        action='store_true',
        default=True,
        help='Show detailed output during execution'
    )
    
    parser.add_argument(
        '--no-export',
        dest='export',
        action='store_false',
        default=True,
        help='Do not export results to JSON file'
    )
    
    parser.add_argument(
        '--test',
        type=str,
        help='Run a single test by name (partial match supported)'
    )
    
    args = parser.parse_args()
    
    # Run single test or full suite
    if args.test:
        run_single_test(args.test, verbose=args.verbose)
    else:
        results = run_full_benchmark(verbose=args.verbose, export=args.export)
        
        # Exit with error code if target not met
        if results and not results["summary"]["target_met"]:
            print("\nBenchmark target not met. Exiting with error code.")
            sys.exit(1)


if __name__ == "__main__":
    main()
