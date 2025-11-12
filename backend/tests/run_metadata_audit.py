"""
Combined script to populate test data and audit metadata
Uses same VectorStore instance to avoid in-memory data loss
"""

import sys
import os
from pathlib import Path

# Add backend to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from populate_test_data import populate_test_data
from metadata_audit import audit_metadata

if __name__ == "__main__":
    try:
        # Create vector store with test data
        vector_store = populate_test_data()
        
        # Audit the same instance
        audit_metadata(vector_store)
        
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
