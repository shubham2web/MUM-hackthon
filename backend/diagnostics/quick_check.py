"""
Quick Diagnostic: Check candidate overlap & score differences
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Suppress all logging
import logging
logging.basicConfig(level=logging.CRITICAL)

from memory.vector_store import VectorStore

# Test query
query = "What did the proponent say about safety in turn 1?"

print("="*70)
print("QUICK DIAGNOSTIC: Candidate Pool Comparison")
print("="*70)

# Test 1: Fusion DISABLED
print("\n1) FUSION DISABLED (baseline):")
vs1 = VectorStore(backend="faiss", enable_hybrid_bm25=True)
vs1.hybrid_fusion = None  # Disable
# Add test memories
vs1.add_memory("Nuclear energy is the safest energy source with lowest death rate per TWh according to WHO statistics.", "test1", {"turn": 1, "role": "proponent"})
vs1.add_memory("Nuclear waste remains dangerous for thousands of years requiring costly long-term storage.", "test2", {"turn": 2, "role": "opponent"})
vs1.add_memory("Modern Generation IV reactors have passive safety systems that prevent meltdowns.", "test3", {"turn": 3, "role": "proponent"})

results1 = vs1.search(query, top_k=5)
print(f"  Retrieved: {len(results1)} candidates")
for i, r in enumerate(results1[:3], 1):
    print(f"    [{i}] score={r.score:.4f}, vector={r.vector_score:.4f}, text={r.text[:60]}...")

# Test 2: Fusion ENABLED
print("\n2) FUSION ENABLED (smart query analysis):")
vs2 = VectorStore(backend="faiss", enable_hybrid_bm25=True)
# Fusion is enabled by default
# Add same memories
vs2.add_memory("Nuclear energy is the safest energy source with lowest death rate per TWh according to WHO statistics.", "test1", {"turn": 1, "role": "proponent"})
vs2.add_memory("Nuclear waste remains dangerous for thousands of years requiring costly long-term storage.", "test2", {"turn": 2, "role": "opponent"})
vs2.add_memory("Modern Generation IV reactors have passive safety systems that prevent meltdowns.", "test3", {"turn": 3, "role": "proponent"})

results2 = vs2.search(query, top_k=5)
print(f"  Retrieved: {len(results2)} candidates")
for i, r in enumerate(results2[:3], 1):
    print(f"    [{i}] score={r.score:.4f}, vector={r.vector_score:.4f}, text={r.text[:60]}...")

# Comparison
print("\n3) COMPARISON:")
ids1 = [r.id for r in results1]
ids2 = [r in results2]
overlap = set(ids1).intersection(set(ids2))
print(f"  Overlap: {len(overlap)}/{len(ids1)} candidates ({len(overlap)/max(len(ids1),1)*100:.1f}%)")

scores1 = [r.score for r in results1]
scores2 = [r.score for r in results2]
print(f"  Score avg: disabled={sum(scores1)/len(scores1):.4f}, enabled={sum(scores2)/len(scores2):.4f}")
print(f"  Delta: {(sum(scores2)/len(scores2) - sum(scores1)/len(scores1)):.4f}")

print("\n" + "="*70)
print("DIAGNOSTIC COMPLETE")
print("="*70)
