"""
Deep dive RAG diagnostics - find out why we're getting 0.0% on everything.
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from memory.memory_manager import HybridMemoryManager
import numpy as np

if __name__ == "__main__":
    print("\n" + "="*70)
    print("🔬 RAG SYSTEM DIAGNOSTICS")
    print("="*70)
    
    # Initialize memory
    memory = HybridMemoryManager()
    
    # Test 1: Store a simple memory
    print("\n📝 TEST 1: Store and retrieve simple memory")
    print("-"*70)
    
    result = memory.add_interaction(
        role="user",
        content="Nuclear power is a clean energy source",
        metadata={"topic": "energy"},
        store_in_rag=True
    )
    
    print(f"Stored memory ID: {result.get('long_term', 'ERROR')}")
    
    # Test 2: Search for exact match
    print("\n🔍 TEST 2: Search for exact match")
    print("-"*70)
    query = "Nuclear power is a clean energy source"
    results = memory.search_memories(query=query, top_k=5)
    
    print(f"Query: {query}")
    print(f"Results found: {len(results)}")
    for i, r in enumerate(results, 1):
        if isinstance(r, dict):
            print(f"  {i}. Score: {r.get('score', 'N/A'):.4f} - {r.get('text', 'N/A')[:60]}...")
        else:
            print(f"  {i}. {r}")
    
    # Test 3: Search for semantic match
    print("\n🔍 TEST 3: Search for semantic match")
    print("-"*70)
    query2 = "What are the benefits of nuclear energy?"
    results2 = memory.search_memories(query=query2, top_k=5)
    
    print(f"Query: {query2}")
    print(f"Results found: {len(results2)}")
    for i, r in enumerate(results2, 1):
        if isinstance(r, dict):
            print(f"  {i}. Score: {r.get('score', 'N/A'):.4f} - {r.get('text', 'N/A')[:60]}...")
        else:
            print(f"  {i}. {r}")
    
    # Test 4: Check embedding dimensions
    print("\n🧮 TEST 4: Check embeddings")
    print("-"*70)
    
    from memory.embeddings import get_embedding_service
    emb_service = get_embedding_service()
    
    test_text = "This is a test"
    doc_embedding = emb_service.embed_text(test_text)
    query_embedding = emb_service.embed_query(test_text)
    
    print(f"Model: {emb_service.model_name}")
    print(f"Document embedding shape: {doc_embedding.shape}")
    print(f"Query embedding shape: {query_embedding.shape}")
    print(f"Document embedding norm: {np.linalg.norm(doc_embedding):.4f}")
    print(f"Query embedding norm: {np.linalg.norm(query_embedding):.4f}")
    
    # Check if embeddings are all zeros
    if np.allclose(doc_embedding, 0):
        print("⚠️  WARNING: Document embedding is all zeros!")
    if np.allclose(query_embedding, 0):
        print("⚠️  WARNING: Query embedding is all zeros!")
    
    # Test 5: Direct vector store test
    print("\n💾 TEST 5: Direct vector store test")
    print("-"*70)
    
    from memory.vector_store import VectorStore
    vs = VectorStore()
    
    # Store directly
    from memory.vector_store import MemoryEntry
    entry = MemoryEntry(
        id="test-1",
        text="Solar panels convert sunlight to electricity",
        metadata={"topic": "solar"}
    )
    vs.add_memory(entry)
    
    # Search directly
    search_results = vs.search("solar energy", top_k=5)
    print(f"Direct search results: {len(search_results)}")
    for i, r in enumerate(search_results, 1):
        print(f"  {i}. Score: {r.score:.4f} - {r.text[:60]}...")
    
    print("\n" + "="*70)
    print("DIAGNOSIS COMPLETE")
    print("="*70 + "\n")
