"""
Hybrid Memory System Demo

Demonstrates the 4-Zone Context Payload architecture with a sample debate.
Run this to see how memory enhances multi-agent conversations.
"""
import asyncio
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from memory.memory_manager import HybridMemoryManager
from core.memory_enhanced_agent import MemoryEnhancedAgent


def print_section(title: str):
    """Print a formatted section header"""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80 + "\n")


def print_zone_payload(payload: str):
    """Print context payload with syntax highlighting"""
    print("📦 CONTEXT PAYLOAD:")
    print("-" * 80)
    for line in payload.split('\n'):
        if line.startswith('[ZONE'):
            print(f"\033[94m{line}\033[0m")  # Blue for zone headers
        elif line.startswith('='):
            print(f"\033[90m{line}\033[0m")  # Gray for separators
        else:
            print(line)
    print("-" * 80)


def demo_basic_memory():
    """Demo 1: Basic memory operations"""
    print_section("DEMO 1: Basic Memory Operations")
    
    # Initialize memory
    memory = HybridMemoryManager(
        short_term_window=4,
        long_term_backend="faiss",  # Use FAISS for quick demo
        enable_rag=True
    )
    
    print("✅ Memory system initialized")
    print(f"   - Short-term window: 4 messages")
    print(f"   - Long-term backend: FAISS")
    print(f"   - RAG enabled: Yes")
    
    # Set debate context
    memory.set_debate_context("demo_debate_001")
    print("\n📋 Debate context set: demo_debate_001")
    
    # Add sample interactions
    print("\n💬 Adding interactions to memory...")
    
    interactions = [
        ("proponent", "Climate change is primarily caused by human activities like burning fossil fuels."),
        ("opponent", "Natural cycles like solar radiation also play a significant role."),
        ("moderator", "Both sides make valid points. Let's examine the evidence."),
        ("proponent", "The data shows a direct correlation between CO2 emissions and temperature rise."),
        ("opponent", "Correlation doesn't always imply causation. We need more analysis.")
    ]
    
    for role, content in interactions:
        result = memory.add_interaction(role=role, content=content)
        print(f"   ✓ Turn {result['turn']}: {role.upper()[:3]}... stored in memory")
    
    # Show memory summary
    print("\n📊 Memory Summary:")
    summary = memory.get_memory_summary()
    print(f"   - Total turns: {summary['turn_counter']}")
    print(f"   - Short-term messages: {summary['short_term']['current_count']}/{summary['short_term']['window_size']}")
    if summary['long_term']:
        print(f"   - Long-term memories: {summary['long_term']['total_memories']}")
    
    return memory


def demo_context_payload(memory: HybridMemoryManager):
    """Demo 2: Building 4-Zone Context Payload"""
    print_section("DEMO 2: Building 4-Zone Context Payload")
    
    print("🏗️  Building context for next agent turn...")
    print("   Query: 'What are the main arguments about climate change causes?'\n")
    
    # Build context payload
    context = memory.build_context_payload(
        system_prompt="""You are the Bias Auditor for ATLAS.
Your job: flag bias, logical fallacies, and missing citations.
Output format: Structured analysis.""",
        current_task="Audit the previous arguments for logical fallacies and bias.",
        query="main arguments about climate change causes",
        top_k_rag=3,
        use_short_term=True,
        use_long_term=True
    )
    
    print_zone_payload(context)
    
    # Show token estimate
    token_estimate = len(context) // 4
    print(f"\n📏 Estimated tokens: ~{token_estimate}")
    
    return context


def demo_semantic_search(memory: HybridMemoryManager):
    """Demo 3: Semantic search in long-term memory"""
    print_section("DEMO 3: Semantic Search in Long-Term Memory")
    
    queries = [
        "human impact on climate",
        "natural climate cycles",
        "evidence and data"
    ]
    
    for query in queries:
        print(f"\n🔍 Query: '{query}'")
        print("   Top 3 relevant memories:\n")
        
        results = memory.search_memories(query=query, top_k=3)
        
        if not results:
            print("   (No results found - memory may be using FAISS which needs more data)")
            continue
        
        for result in results:
            score_bar = "█" * int(result['score'] * 20)
            print(f"   [{score_bar:<20}] {result['score']:.3f}")
            print(f"   {result['text'][:80]}...")
            print(f"   Role: {result['metadata'].get('role', 'N/A')} | Turn: {result['metadata'].get('turn', 'N/A')}\n")


def demo_memory_enhanced_agent():
    """Demo 4: Memory-Enhanced Agent"""
    print_section("DEMO 4: Memory-Enhanced Agent")
    
    print("🤖 Creating memory-enhanced agent...")
    
    # Create agent (will use global memory manager)
    agent = MemoryEnhancedAgent(
        role="fact_checker",
        model_name="llama3",
        auto_store_responses=True
    )
    
    print("✅ Agent created: Fact Checker")
    print(f"   - Model: llama3")
    print(f"   - Auto-store responses: Yes")
    print(f"   - Memory: {agent.memory}")
    
    # Simulate agent task
    print("\n📝 Agent task: 'Verify the claim about CO2 correlation'")
    print("   (Note: Actual LLM call would happen here)")
    
    # Manually add response to demonstrate
    agent.add_to_memory(
        content="The claim about CO2 correlation is well-supported by multiple peer-reviewed studies. The IPCC reports show clear evidence.",
        metadata={"task": "fact_check", "verified": True}
    )
    
    print("   ✓ Agent response stored in memory")
    
    # Show memory state
    print("\n📊 Agent Memory State:")
    agent_summary = agent.get_memory_summary()
    print(f"   - Debate ID: {agent_summary['current_debate_id']}")
    print(f"   - Total turns: {agent_summary['turn_counter']}")


def demo_zone_comparison():
    """Demo 5: Context with/without memory zones"""
    print_section("DEMO 5: Context Comparison - With vs Without Memory")
    
    memory = HybridMemoryManager(short_term_window=4, enable_rag=True)
    memory.set_debate_context("comparison_demo")
    
    # Add some context
    memory.add_interaction("user", "Tell me about renewable energy benefits")
    memory.add_interaction("assistant", "Renewable energy reduces carbon emissions and provides sustainable power")
    
    task = "What are the economic benefits of renewable energy?"
    
    # WITHOUT memory
    print("❌ WITHOUT Memory (Traditional approach):")
    print("-" * 80)
    traditional_context = f"System: You are a helpful assistant.\nUser: {task}"
    print(traditional_context)
    print("-" * 80)
    print(f"Token estimate: ~{len(traditional_context) // 4}\n")
    
    # WITH memory
    print("✅ WITH Memory (4-Zone Hybrid System):")
    print("-" * 80)
    hybrid_context = memory.build_context_payload(
        system_prompt="You are a helpful assistant.",
        current_task=task,
        top_k_rag=2
    )
    # Print first 500 chars
    print(hybrid_context[:500] + "...\n[truncated for display]")
    print("-" * 80)
    print(f"Token estimate: ~{len(hybrid_context) // 4}")
    
    print("\n💡 Key Difference:")
    print("   - Traditional: No context, agent can't reference past conversation")
    print("   - Hybrid Memory: Agent has full context from ZONE 2 (RAG) and ZONE 3 (recent chat)")


def main():
    """Run all demos"""
    print("\n" + "=" * 80)
    print("  🧠 ATLAS HYBRID MEMORY SYSTEM - DEMONSTRATION")
    print("=" * 80)
    print("\n  This demo shows how the 4-Zone Context Payload architecture works.")
    print("  It combines RAG (long-term) with short-term memory for enhanced AI debates.\n")
    
    try:
        # Demo 1: Basic operations
        memory = demo_basic_memory()
        
        # Demo 2: Context payload
        demo_context_payload(memory)
        
        # Demo 3: Semantic search
        demo_semantic_search(memory)
        
        # Demo 4: Memory-enhanced agent
        demo_memory_enhanced_agent()
        
        # Demo 5: Comparison
        demo_zone_comparison()
        
        # Final summary
        print_section("DEMO COMPLETE")
        print("✅ All demos completed successfully!")
        print("\n📚 Next steps:")
        print("   1. Install dependencies: pip install -r backend/memory_requirements.txt")
        print("   2. Start server: python backend/server.py")
        print("   3. Try API endpoints: See MEMORY_SYSTEM_GUIDE.md")
        print("   4. Integrate with ATLAS v2.0 debates")
        print("\n💡 Tip: Run with real LLM by setting up API keys in backend/.env")
        
    except ImportError as e:
        print(f"\n❌ Import Error: {e}")
        print("\n📦 Missing dependencies. Install with:")
        print("   pip install sentence-transformers chromadb faiss-cpu numpy")
        print("\nOr:")
        print("   pip install -r backend/memory_requirements.txt")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
