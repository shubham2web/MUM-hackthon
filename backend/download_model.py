"""
Script to download BGE embedding model for RAG optimization
"""
from sentence_transformers import SentenceTransformer
import time

print("=" * 70)
print("DOWNLOADING BGE-SMALL-EN-V1.5 EMBEDDING MODEL")
print("=" * 70)
print("Model: BAAI/bge-small-en-v1.5")
print("Size: ~133MB")
print("Optimized for: Retrieval tasks")
print("=" * 70)
print()

start = time.time()
print("Starting download...")

try:
    model = SentenceTransformer('BAAI/bge-small-en-v1.5')
    elapsed = time.time() - start
    
    print()
    print("=" * 70)
    print("✅ DOWNLOAD COMPLETE!")
    print("=" * 70)
    print(f"Model: {model}")
    print(f"Dimension: {model.get_sentence_embedding_dimension()}")
    print(f"Download time: {elapsed:.1f} seconds")
    print()
    print("The model is cached and ready to use!")
    print("=" * 70)
    
except Exception as e:
    print(f"❌ ERROR: {e}")
    print("Please check your internet connection and try again.")
