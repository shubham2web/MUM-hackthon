import sys
sys.path.insert(0, '.')

from tests.test_rag_benchmark import BenchmarkHarness

h = BenchmarkHarness()
h.setup()

# Run a test query
results = h.memory_manager.vector_store.search_memories('recent arguments about nuclear energy', top_k=5)

print('Sample metadata from retrieval:')
for i, r in enumerate(results[:3], 1):
    print(f'\n{i}. Score: {r.score:.3f}')
    print(f'   Authority: {r.metadata.get("authority_score", "MISSING")}')
    print(f'   Recency: {r.metadata.get("recency_score", "MISSING")}')
    print(f'   Role: {r.metadata.get("role", "MISSING")}')
    print(f'   Text preview: {r.text[:100]}...')
