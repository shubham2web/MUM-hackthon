"""
Demo Cache Warmer - Pre-load queries to avoid 37-second waits on stage

Run this BEFORE your demo to:
1. Scrape all demo URLs and cache them
2. Store summaries in memory (ChromaDB)
3. Ensure instant responses (<1s) during live presentation

Usage:
    python warm_cache_for_demo.py

Expected output:
    ✅ Query 1 cached in 35.2s
    ✅ Query 2 cached in 28.7s
    ✅ All queries cached! Demo ready.

On stage: Your queries will now hit CACHE (⚡ 0.5s) instead of LIVE FETCH (🌐 37s)
"""
import asyncio
import json
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from ai_agent import analyze_topic_with_groq


# ============================================================================
# DEMO QUERIES - CUSTOMIZE THESE FOR YOUR PRESENTATION
# ============================================================================

DEMO_QUERIES = [
    # Query 1: Jamiat Chief example (from your log)
    "Tell me about Jamiat Chief backs Al Falah proposal",
    
    # Query 2: Renewable Energy (common demo topic)
    "What are the latest developments in renewable energy? https://techcrunch.com/2024/renewable-energy",
    
    # Query 3: AI Safety
    "Summarize recent news on AI safety regulations",
    
    # Query 4: Climate Change
    "What are experts saying about climate change solutions?",
    
    # Query 5: Tech Industry
    "Latest updates on tech industry layoffs and hiring trends",
]


# ============================================================================
# CACHE WARMING LOGIC
# ============================================================================

async def warm_single_query(query: str, index: int, total: int) -> dict:
    """
    Warm cache for a single query
    
    Returns:
        dict with status, query, latency, sources_count
    """
    print(f"\n{'='*70}")
    print(f"[{index}/{total}] Warming query: {query[:60]}...")
    print(f"{'='*70}")
    
    try:
        import time
        start = time.time()
        
        # Call the actual AI agent (this will scrape, cache, and store in memory)
        result = await analyze_topic_with_groq(query)
        
        latency = time.time() - start
        
        # Parse result
        if isinstance(result, str):
            # Plain text response
            sources = 0
        elif isinstance(result, dict):
            sources = len(result.get('sources', []))
        else:
            sources = 0
        
        print(f"✅ CACHED in {latency:.1f}s | Sources: {sources}")
        
        return {
            'status': 'success',
            'query': query,
            'latency': latency,
            'sources_count': sources
        }
        
    except Exception as e:
        print(f"❌ FAILED: {e}")
        return {
            'status': 'error',
            'query': query,
            'error': str(e)
        }


async def warm_all_queries():
    """
    Warm cache for all demo queries sequentially
    """
    print("\n" + "="*70)
    print("🔥 CACHE WARMER FOR DEMO - Starting...")
    print("="*70)
    print(f"Total queries to warm: {len(DEMO_QUERIES)}")
    print("This will take ~2-5 minutes depending on URLs...\n")
    
    results = []
    
    for i, query in enumerate(DEMO_QUERIES, start=1):
        result = await warm_single_query(query, i, len(DEMO_QUERIES))
        results.append(result)
        
        # Brief pause between queries to avoid rate limiting
        if i < len(DEMO_QUERIES):
            print("\n⏳ Waiting 3 seconds before next query...")
            await asyncio.sleep(3)
    
    # Summary report
    print("\n" + "="*70)
    print("📊 CACHE WARMING COMPLETE - SUMMARY")
    print("="*70)
    
    success_count = sum(1 for r in results if r['status'] == 'success')
    total_latency = sum(r.get('latency', 0) for r in results if 'latency' in r)
    
    print(f"✅ Successful: {success_count}/{len(DEMO_QUERIES)}")
    print(f"❌ Failed: {len(DEMO_QUERIES) - success_count}/{len(DEMO_QUERIES)}")
    print(f"⏱️  Total time: {total_latency:.1f}s")
    
    if success_count == len(DEMO_QUERIES):
        print("\n🎉 ALL QUERIES CACHED! Your demo is ready.")
        print("💡 On stage, these queries will now respond in <1 second (CACHE hit)")
    else:
        print("\n⚠️  Some queries failed. Check errors above.")
        print("💡 You can re-run this script to retry failed queries.")
    
    # Save report
    report_path = Path(__file__).parent / "data" / "cache_warm_report.json"
    report_path.parent.mkdir(exist_ok=True)
    
    with open(report_path, 'w') as f:
        json.dump({
            'timestamp': asyncio.get_event_loop().time(),
            'total_queries': len(DEMO_QUERIES),
            'successful': success_count,
            'failed': len(DEMO_QUERIES) - success_count,
            'total_latency': total_latency,
            'results': results
        }, f, indent=2)
    
    print(f"\n📄 Report saved to: {report_path}")
    
    return results


# ============================================================================
# CACHE VERIFICATION
# ============================================================================

def verify_cache_files():
    """
    Check if cache files exist and show their status
    """
    print("\n" + "="*70)
    print("🔍 VERIFYING CACHE FILES")
    print("="*70)
    
    data_dir = Path(__file__).parent / "data"
    
    files_to_check = [
        ("web_cache.json", "Web scraper cache"),
        ("chroma_db", "Vector memory store (ChromaDB)"),
        ("rag_cache.json", "RAG response cache"),
    ]
    
    for filename, description in files_to_check:
        path = data_dir / filename
        if path.exists():
            if path.is_file():
                size = path.stat().st_size / 1024  # KB
                print(f"✅ {description}: {size:.1f} KB")
            else:
                # Directory (e.g., chroma_db)
                print(f"✅ {description}: exists")
        else:
            print(f"❌ {description}: not found")
    
    print("="*70)


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    print("""
╔══════════════════════════════════════════════════════════════════════╗
║                     DEMO CACHE WARMER 🔥                             ║
║                                                                      ║
║  This script pre-loads your demo queries to avoid long waits         ║
║  during your live presentation.                                      ║
║                                                                      ║
║  What it does:                                                       ║
║  1. Runs each demo query through the full RAG pipeline              ║
║  2. Scrapes URLs and saves to web_cache.json                        ║
║  3. Stores summaries in ChromaDB memory                             ║
║  4. Caches final responses                                          ║
║                                                                      ║
║  Result: <1 second responses during demo instead of 37 seconds! 🚀  ║
╚══════════════════════════════════════════════════════════════════════╝
    """)
    
    # Verify existing cache
    verify_cache_files()
    
    # Confirm before starting
    print("\n⚠️  This will make HTTP requests to scrape URLs in your queries.")
    print("⚠️  Expected time: 2-5 minutes for all queries.")
    response = input("\n▶ Start cache warming? [Y/n]: ").strip().lower()
    
    if response in ['', 'y', 'yes']:
        # Run the warming process
        asyncio.run(warm_all_queries())
        
        # Re-verify after warming
        verify_cache_files()
        
        print("\n✅ Cache warming complete! You're ready for the demo.")
        print("💡 TIP: Run this script again before your presentation to refresh the cache.")
    else:
        print("\n❌ Cache warming cancelled.")
        sys.exit(0)
