"""
Mini RAG Benchmark - Demonstration Version

Runs a subset of 3 tests to demonstrate LLM re-ranking impact
while staying within Groq free tier rate limits.
"""

import sys
import os
from datetime import datetime
from dotenv import load_dotenv

# Load .env file for API keys
load_dotenv()

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from memory.memory_manager import get_memory_manager
from tests.test_rag_benchmark import RAGBenchmark, TestCase


def create_mini_test_suite():
    """Create 3 representative test cases"""
    
    test_cases = []
    
    # Test 1: Long-Term Memory Retention (best performer, 81% baseline)
    test_cases.append(TestCase(
        name="Long-Term Memory Retention",
        description="Tests retrieval of early content after many subsequent memories",
        memories=[
            {"text": "User asked about Python basics", "metadata": {"role": "user", "turn": 1, "topic": "programming"}},
            {"text": "I explained Python syntax fundamentals", "metadata": {"role": "assistant", "turn": 2, "topic": "programming"}},
            *[{"text": f"Filler conversation turn {i}", "metadata": {"role": "user" if i%2==0 else "assistant", "turn": i+3, "topic": "other"}} 
              for i in range(10)],  # 10 filler messages
            {"text": "User mentioned JavaScript frameworks", "metadata": {"role": "user", "turn": 13, "topic": "webdev"}},
        ],
        query="What did we discuss about Python earlier?",
        expected_ids=["long_term_0", "long_term_1"],  # Should recall early Python discussion
        judge_criteria="Must retrieve the Python discussion from turns 1-2, not the recent JavaScript mention or filler content"
    ))
    
    # Test 2: Similar Content Disambiguation (71% baseline, tests precision)
    test_cases.append(TestCase(
        name="Similar Content Disambiguation",
        description="Tests ability to distinguish between very similar statements",
        memories=[
            {"text": "The capital of France is Paris", "metadata": {"role": "assistant", "turn": 1, "topic": "geography"}},
            {"text": "The capital of Italy is Rome", "metadata": {"role": "assistant", "turn": 2, "topic": "geography"}},
            {"text": "Paris is known for the Eiffel Tower", "metadata": {"role": "assistant", "turn": 3, "topic": "landmarks"}},
        ],
        query="What is the capital of Italy?",
        expected_ids=["similar_1"],  # ONLY the Rome fact
        judge_criteria="Must return ONLY the Italy-Rome fact. Paris mentions are semantically similar but incorrect."
    ))
    
    # Test 3: Multi-Turn Chat Context (67% baseline)
    test_cases.append(TestCase(
        name="Multi-Turn Chat Context",
        description="Tests retrieval of previous explanations in multi-turn conversation",
        memories=[
            {"text": "User: How does photosynthesis work?", "metadata": {"role": "user", "turn": 1, "topic": "biology"}},
            {"text": "Assistant: Photosynthesis converts sunlight into chemical energy using chlorophyll", "metadata": {"role": "assistant", "turn": 2, "topic": "biology"}},
            {"text": "User: Can you explain the light-dependent reactions?", "metadata": {"role": "user", "turn": 3, "topic": "biology"}},
            {"text": "Assistant: Light-dependent reactions occur in the thylakoid membranes", "metadata": {"role": "assistant", "turn": 4, "topic": "biology"}},
        ],
        query="What did you say about photosynthesis?",
        expected_ids=["chat_1"],  # The photosynthesis explanation
        judge_criteria="Should recall the general photosynthesis explanation, not the specific light-dependent detail"
    ))
    
    return test_cases


def run_mini_benchmark():
    """Execute mini benchmark"""
    
    # Set UTF-8 encoding
    if sys.platform == 'win32':
        try:
            sys.stdout.reconfigure(encoding='utf-8')
        except:
            pass
    
    print("\n" + "="*70)
    print("MINI RAG BENCHMARK - RE-RANKING DEMONSTRATION")
    print("="*70)
    print("Running 3 tests to demonstrate LLM re-ranking impact")
    print("(Mini version stays within Groq free tier rate limits)")
    print("="*70 + "\n")
    
    # Initialize memory
    try:
        print("Initializing memory manager...")
        memory = get_memory_manager(
            long_term_backend="faiss",
            reset=True  # Fresh instance
        )
        print("✅ Memory initialized with LLM re-ranking enabled\n")
    except Exception as e:
        print(f"❌ Failed: {e}")
        return
    
    # Create benchmark
    benchmark = RAGBenchmark(memory)
    
    # Load mini test suite
    test_cases = create_mini_test_suite()
    for test in test_cases:
        benchmark.add_test(test)
    
    print(f"📋 Loaded {len(test_cases)} test cases\n")
    
    # Run benchmark
    print("🚀 Running mini benchmark...\n")
    start_time = datetime.now()
    
    results = benchmark.run_benchmark(verbose=True)
    
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()
    
    # Print results
    print("\n" + "="*70)
    print("MINI BENCHMARK RESULTS")
    print("="*70)
    print(f"Tests Run:          {len(results['test_results'])}")
    print(f"Tests Passed:       {results['summary']['passed']}")
    print(f"Pass Rate:          {results['summary']['pass_rate']:.1f}%\n")
    
    print(f"Average Precision:  {results['summary']['avg_precision']:.1f}%")
    print(f"Average Recall:     {results['summary']['avg_recall']:.1f}%")
    print(f"Average F1 Score:   {results['summary']['avg_f1']:.1f}%")
    print(f"Average Relevance:  {results['summary']['avg_relevance']:.1f}%")
    
    target_met = results['summary']['avg_relevance'] >= 85.0
    status_icon = "✅" if target_met else "❌"
    print(f"\n🎯 Target (>85% relevance): {status_icon} {'MET' if target_met else 'NOT MET'}")
    print("="*70)
    
    print(f"\nExecution time: {duration:.2f} seconds")
    print(f"Average time per test: {duration/len(test_cases):.2f} seconds\n")
    
    # Individual results
    print("="*70)
    print("INDIVIDUAL TEST RESULTS")
    print("="*70 + "\n")
    
    for test_result in results['test_results']:
        status_icon = "✅ PASS" if test_result['passed'] else "❌ FAIL"
        print(f"{status_icon} {test_result['name']}")
        print(f"   Precision:  {test_result['precision']:.2f}%")
        print(f"   Recall:     {test_result['recall']:.2f}%")
        print(f"   F1 Score:   {test_result['f1']:.2f}%")
        print(f"   Relevance:  {test_result['relevance']:.2f}%\n")
    
    # Comparison note
    print("="*70)
    print("EXPECTED IMPROVEMENT WITH RE-RANKING")
    print("="*70)
    print("\nBaseline (BGE only, no re-ranking):")
    print("  • Long-Term Memory:   81.3% relevance")
    print("  • Similar Content:    71.0% relevance")
    print("  • Multi-Turn Chat:    67.4% relevance")
    print("  • Average:            73.2% relevance")
    print("\nWith LLM Re-ranking (current run):")
    print(f"  • Average:            {results['summary']['avg_relevance']:.1f}% relevance")
    print(f"  • Improvement:        {results['summary']['avg_relevance']-73.2:+.1f} percentage points")
    print("\n" + "="*70 + "\n")
    
    return results


if __name__ == "__main__":
    try:
        run_mini_benchmark()
    except KeyboardInterrupt:
        print("\n\n❌ Benchmark interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Benchmark failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
