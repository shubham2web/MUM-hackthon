"""
Interactive RAG Demo - Test the optimized hybrid memory system

Run with: python -m backend.tests.interactive_rag_demo
"""
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from memory.memory_manager import get_memory_manager


def seed_misinformation_database(memory):
    """Seed with realistic misinformation examples"""
    print("📚 Seeding knowledge base with misinformation examples...")
    
    examples = [
        {
            "role": "researcher",
            "content": "Study shows 5G towers DO NOT cause COVID-19. No scientific evidence supports this claim.",
            "metadata": {"topic": "5G", "verdict": "FALSE", "source": "WHO"},
        },
        {
            "role": "analyst",
            "content": "Vaccine misinformation increased 340% on TikTok in Q3 2025, primarily targeting teens.",
            "metadata": {"topic": "vaccines", "platform": "tiktok", "trend": "rising"},
        },
        {
            "role": "fact_checker",
            "content": "Climate change denial posts surged after hurricane season, using manipulated weather data.",
            "metadata": {"topic": "climate", "verdict": "MISLEADING"},
        },
        {
            "role": "expert",
            "content": "Deepfake detection: Look for unnatural eye movements and inconsistent lighting.",
            "metadata": {"topic": "deepfakes", "type": "detection_tip"},
        },
        {
            "role": "researcher",
            "content": "Election fraud claims debunked by 62 courts, including Trump-appointed judges.",
            "metadata": {"topic": "elections", "verdict": "FALSE", "coverage": "widespread"},
        },
        {
            "role": "analyst",
            "content": "AI-generated fake news articles now account for 15% of political misinformation online.",
            "metadata": {"topic": "AI_misinfo", "trend": "emerging_threat"},
        },
    ]
    
    for ex in examples:
        memory.add_interaction(
            role=ex["role"],
            content=ex["content"],
            metadata=ex["metadata"],
            store_in_rag=True
        )
    
    print(f"✅ Added {len(examples)} examples to knowledge base\n")


def run_queries(memory):
    """Run sample queries to demonstrate RAG retrieval"""
    queries = [
        "What's the latest on vaccine misinformation?",
        "How can I detect deepfakes?",
        "Did 5G cause COVID-19?",
        "Tell me about election fraud claims",
    ]
    
    print("🔍 Running sample queries...\n")
    print("=" * 70)
    
    for i, query in enumerate(queries, 1):
        print(f"\n[QUERY {i}]: {query}")
        print("-" * 70)
        
        results = memory.search_memories(
            query=query,
            top_k=3,
            similarity_threshold=0.50
        )
        
        if results:
            for rank, result in enumerate(results, 1):
                print(f"\n  [{rank}] Score: {result['score']:.3f} | Role: {result['metadata'].get('role', 'N/A')}")
                print(f"      {result['text'][:150]}...")
                if 'verdict' in result['metadata']:
                    print(f"      Verdict: {result['metadata']['verdict']}")
        else:
            print("  ⚠ No relevant results found")
        
        print()
    
    print("=" * 70)


def interactive_mode(memory):
    """Let user ask custom questions"""
    print("\n💬 Interactive Mode (type 'quit' to exit)\n")
    
    while True:
        try:
            query = input("Your question: ").strip()
            
            if not query or query.lower() in ['quit', 'exit', 'q']:
                print("👋 Goodbye!")
                break
            
            results = memory.search_memories(query, top_k=3, similarity_threshold=0.50)
            
            if results:
                print(f"\n📋 Found {len(results)} relevant results:\n")
                for rank, result in enumerate(results, 1):
                    print(f"[{rank}] {result['text']}")
                    print(f"    Score: {result['score']:.3f} | {result['metadata']}\n")
            else:
                print("⚠ No relevant information found in knowledge base.\n")
        
        except KeyboardInterrupt:
            print("\n👋 Goodbye!")
            break
        except Exception as e:
            print(f"❌ Error: {e}\n")


def main():
    print("\n🚀 ATLAS RAG System - Interactive Demo")
    print("=" * 70)
    print("Testing optimized hybrid memory with:")
    print("  ✓ FastEmbed embeddings (BGE-small-en-v1.5)")
    print("  ✓ Hybrid vector + BM25 retrieval (75/25 split)")
    print("  ✓ Metadata boosting (recent + role-based)")
    print("  ✓ Adaptive thresholding")
    print("=" * 70 + "\n")
    
    # Initialize memory manager
    memory = get_memory_manager(
        reset=True,
        long_term_backend="faiss",
        enable_reranking=False,
    )
    
    # Seed knowledge base
    seed_misinformation_database(memory)
    
    # Run automated queries
    run_queries(memory)
    
    # Enter interactive mode
    interactive_mode(memory)


if __name__ == "__main__":
    main()
