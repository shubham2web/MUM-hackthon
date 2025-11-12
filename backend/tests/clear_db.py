"""
Clear old vector database to allow dimension upgrade.

When upgrading embedding models (e.g., BGE 384-dim → Nomic 768-dim),
the old database must be cleared because dimensions are incompatible.
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import shutil

# Path to ChromaDB database
DB_PATH = "database/vector_store"

if __name__ == "__main__":
    print("\n" + "="*70)
    print("🗑️  CLEARING OLD VECTOR DATABASE")
    print("="*70)
    print(f"\nReason: Upgrading from BGE (384-dim) to Nomic (768-dim)")
    print(f"Path: {DB_PATH}")
    
    if os.path.exists(DB_PATH):
        print(f"\n⚠️  Deleting existing database...")
        shutil.rmtree(DB_PATH)
        print("✅ Database deleted")
    else:
        print("\n✅ No existing database found")
    
    print("\n" + "="*70)
    print("Ready for Nomic Embed upgrade!")
    print("="*70 + "\n")
