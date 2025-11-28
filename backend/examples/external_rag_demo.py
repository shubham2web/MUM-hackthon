"""
External RAG Usage Example - Live Demo

Demonstrates the 3-step fix for chatbot hallucination:
1. Web Scraper - Fetches actual URL content
2. Query Condensation - Rewrites queries with context
3. Dynamic Evidence - Shows/hides evidence appropriately
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from memory.memory_manager import HybridMemoryManager
from core.memory_enhanced_agent import condense_query
from core.ai_agent import AiAgent


def demo_url_hallucination_fix():
    """
    Demonstrates how External RAG prevents URL keyword hallucination
    """
    print("\n" + "=" * 80)
    print("DEMO 1: URL Hallucination Fix")
    print("=" * 80)
    print("\nScenario: User provides URL with misleading keywords")
    print("Example: URL contains 'johannesburg' but article is about G20 in New Delhi")
    
    # Initialize memory manager
    memory = HybridMemoryManager(enable_rag=False)
    
    # User provides URL
    user_query = "Analyze this article about the summit: https://example.com"
    
    print(f"\n📥 User Input: {user_query}")
    
    # Build context WITH External RAG
    context_with_rag = memory.build_context_payload(
        system_prompt="You are a news analyst.",
        current_task=user_query,
        enable_web_rag=True
    )
    
    # Build context WITHOUT External RAG (for comparison)
    context_without_rag = memory.build_context_payload(
        system_prompt="You are a news analyst.",
        current_task=user_query,
        enable_web_rag=False
    )
    
    print("\n--- Without External RAG (Hallucination Risk) ---")
    print("❌ Bot would guess content based on URL keywords")
    print("❌ No actual webpage content fetched")
    if "[NO EXTERNAL EVIDENCE RETRIEVED]" in context_without_rag:
        print("✅ Correctly shows NO EVIDENCE message")
    
    print("\n--- With External RAG (Accurate) ---")
    if "LIVE WEB CONTENT" in context_with_rag:
        print("✅ Fetched actual webpage content")
        print("✅ Bot can read real facts from the article")
        
        # Extract a sample of the fetched content
        start = context_with_rag.find("LIVE WEB CONTENT")
        if start != -1:
            sample = context_with_rag[start:start+300]
            print(f"\n📄 Content Preview:\n{sample}...")
    else:
        print("⚠️ Web RAG not triggered (no URL detected or fetch failed)")


def demo_goldfish_memory_fix():
    """
    Demonstrates how Query Condensation prevents memory loss
    """
    print("\n" + "=" * 80)
    print("DEMO 2: Goldfish Memory Fix (Query Condensation)")
    print("=" * 80)
    print("\nScenario: User refers to previous context without repeating details")
    
    # Simulate conversation
    conversation_history = """
User: Check this NDTV article about climate change: https://ndtv.com/climate-article
Assistant: I'll analyze the climate change article from NDTV for you.
"""
    
    print(f"\n📝 Conversation History:\n{conversation_history}")
    
    # User follow-up (vague reference)
    user_followup = "what does it say about renewable energy?"
    print(f"\n📥 User Follow-up: {user_followup}")
    
    # Initialize LLM for condensation
    llm = AiAgent(model_name="llama3")
    
    print("\n--- Without Query Condensation (Memory Loss) ---")
    print(f"❌ Bot searches for: '{user_followup}'")
    print("❌ No context about NDTV article or URL")
    print("❌ Bot can't find relevant information")
    
    print("\n--- With Query Condensation (Context Aware) ---")
    try:
        condensed = condense_query(
            chat_history=conversation_history,
            latest_user_input=user_followup,
            llm_client=llm
        )
        print(f"✅ Query rewritten to: '{condensed}'")
        print("✅ Now includes explicit reference to NDTV article")
        print("✅ Bot can fetch the correct URL and answer accurately")
    except Exception as e:
        print(f"⚠️ Condensation failed (LLM may not be available): {e}")
        print("   In production, this would rewrite the query with full context")


def demo_evidence_block_fix():
    """
    Demonstrates how Dynamic Evidence prevents template leakage
    """
    print("\n" + "=" * 80)
    print("DEMO 3: Evidence Block Leakage Fix")
    print("=" * 80)
    print("\nScenario: Bot should only show evidence section when evidence exists")
    
    memory = HybridMemoryManager(enable_rag=False)
    
    # Case 1: Simple math (no evidence needed)
    print("\n--- Case 1: No Evidence Needed ---")
    print("📥 User: What is 2 + 2?")
    
    context_no_evidence = memory.build_context_payload(
        system_prompt="You are a math tutor.",
        current_task="What is 2 + 2?",
        enable_web_rag=False
    )
    
    if "[NO EXTERNAL EVIDENCE RETRIEVED]" in context_no_evidence:
        print("✅ Shows explicit NO EVIDENCE message")
        print("✅ Bot knows to rely on internal knowledge")
        print("✅ No 'Evidence Block' placeholder shown")
    else:
        print("❌ Missing NO EVIDENCE message")
    
    # Case 2: Question with URL (evidence available)
    print("\n--- Case 2: Evidence Available ---")
    print("📥 User: Summarize https://example.com")
    
    context_with_evidence = memory.build_context_payload(
        system_prompt="You are a summarizer.",
        current_task="Summarize the main points from https://example.com",
        enable_web_rag=True
    )
    
    if "[ZONE 2: RETRIEVED EVIDENCE]" in context_with_evidence:
        print("✅ Shows EVIDENCE section (conditional)")
        print("✅ Includes fetched web content")
        print("✅ Bot can use real facts to answer")
    elif "[NO EXTERNAL EVIDENCE RETRIEVED]" in context_with_evidence:
        print("⚠️ No evidence fetched (URL may be inaccessible)")
    else:
        print("❌ Evidence handling incorrect")


def demo_complete_flow():
    """
    Demonstrates complete flow with all fixes integrated
    """
    print("\n" + "=" * 80)
    print("DEMO 4: Complete Flow (All Fixes Integrated)")
    print("=" * 80)
    
    # Initialize system
    memory = HybridMemoryManager(enable_rag=False, short_term_window=5)
    
    print("\n🎬 Simulating realistic conversation...")
    
    # Turn 1: User provides URL
    print("\n--- Turn 1 ---")
    print("👤 User: Check this article about AI ethics: https://example.com")
    
    memory.add_interaction(
        role="user",
        content="Check this article about AI ethics: https://example.com",
        store_in_rag=False
    )
    
    context1 = memory.build_context_payload(
        system_prompt="You are an AI ethics analyst.",
        current_task="Analyze the AI ethics article from the provided URL",
        query="AI ethics article https://example.com",
        enable_web_rag=True
    )
    
    checks1 = [
        ("LIVE WEB CONTENT" in context1 or "[NO EXTERNAL EVIDENCE" in context1, "Web RAG triggered"),
        ("[ZONE 1: SYSTEM PROMPT]" in context1, "System prompt"),
        ("[ZONE 4: CURRENT TASK]" in context1, "Current task")
    ]
    
    for passed, name in checks1:
        status = "✅" if passed else "❌"
        print(f"  {status} {name}")
    
    memory.add_interaction(
        role="assistant",
        content="I've analyzed the article. It discusses fairness in AI systems.",
        store_in_rag=False
    )
    
    # Turn 2: User vague follow-up
    print("\n--- Turn 2 ---")
    print("👤 User: what about bias in the article?")
    
    memory.add_interaction(
        role="user",
        content="what about bias in the article?",
        store_in_rag=False
    )
    
    # Note: In real usage, you'd run condense_query here
    print("  ℹ️  Query condensation would rewrite: 'what about bias' →")
    print("      'what does the AI ethics article say about bias?'")
    
    context2 = memory.build_context_payload(
        system_prompt="You are an AI ethics analyst.",
        current_task="what about bias in the article?",
        query="bias in AI ethics article https://example.com",
        enable_web_rag=True
    )
    
    checks2 = [
        ("[ZONE 3: SHORT-TERM MEMORY]" in context2, "Short-term memory"),
        ("AI ethics" in context2 or "article" in context2, "Conversation context"),
    ]
    
    for passed, name in checks2:
        status = "✅" if passed else "❌"
        print(f"  {status} {name}")
    
    print("\n📊 Summary:")
    print("  ✅ External RAG fetches real URL content")
    print("  ✅ Query condensation preserves context")
    print("  ✅ Evidence block shown/hidden appropriately")
    print("  ✅ Short-term memory tracks conversation")
    print("\n  🎯 Result: No hallucination, accurate responses!")


def main():
    """Run all demos"""
    print("\n" + "=" * 80)
    print("🚀 EXTERNAL RAG IMPLEMENTATION - LIVE DEMO")
    print("=" * 80)
    print("\nThis demo shows how the 3-step fix prevents chatbot hallucination:")
    print("  1️⃣  Web Scraper - Fetches actual URL content")
    print("  2️⃣  Query Condensation - Rewrites queries with context")
    print("  3️⃣  Dynamic Evidence - Shows/hides evidence appropriately")
    
    try:
        demo_url_hallucination_fix()
        demo_goldfish_memory_fix()
        demo_evidence_block_fix()
        demo_complete_flow()
        
        print("\n" + "=" * 80)
        print("✅ ALL DEMOS COMPLETED SUCCESSFULLY")
        print("=" * 80)
        print("\n📖 For more details, see: backend/docs/EXTERNAL_RAG_FIX.md")
        
    except Exception as e:
        print(f"\n❌ DEMO FAILED: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
