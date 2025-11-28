"""
Populate test data with metadata for testing
Creates sample conversations with varying recency and authority scores
"""

import sys
import os
from pathlib import Path
from datetime import datetime, timedelta

# Add backend to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from memory.vector_store import VectorStore

def populate_test_data(vector_store=None):
    """Populate vector store with test conversations having metadata"""
    
    print("\n" + "="*70)
    print("POPULATING TEST DATA WITH METADATA")
    print("="*70)
    
    if vector_store is None:
        vector_store = VectorStore()
    
    # Sample conversations with varying metadata
    test_conversations = [
        {
            "text": "User asked about implementing authentication in FastAPI. I explained JWT tokens and OAuth2.",
            "role": "assistant",
            "timestamp": (datetime.now() - timedelta(days=1)).isoformat(),
            "source": "chat",
            "recency_score": 0.95,
            "authority_score": 0.85
        },
        {
            "text": "User requested help with React state management. I recommended Redux and Context API.",
            "role": "assistant",
            "timestamp": (datetime.now() - timedelta(days=7)).isoformat(),
            "source": "chat",
            "recency_score": 0.75,
            "authority_score": 0.90
        },
        {
            "text": "User had a Python pandas dataframe issue. I showed how to use groupby and pivot operations.",
            "role": "assistant",
            "timestamp": (datetime.now() - timedelta(days=30)).isoformat(),
            "source": "chat",
            "recency_score": 0.45,
            "authority_score": 0.80
        },
        {
            "text": "User needed SQL query optimization advice. I suggested indexing strategies and query refactoring.",
            "role": "assistant",
            "timestamp": (datetime.now() - timedelta(days=60)).isoformat(),
            "source": "documentation",
            "recency_score": 0.25,
            "authority_score": 0.95
        },
        {
            "text": "User asked about Docker container networking. I explained bridge networks and port mapping.",
            "role": "assistant",
            "timestamp": (datetime.now() - timedelta(hours=12)).isoformat(),
            "source": "chat",
            "recency_score": 0.98,
            "authority_score": 0.75
        },
        {
            "text": "User wanted to understand async/await in JavaScript. I demonstrated Promises and async functions.",
            "role": "assistant",
            "timestamp": (datetime.now() - timedelta(days=14)).isoformat(),
            "source": "tutorial",
            "recency_score": 0.65,
            "authority_score": 0.88
        },
        {
            "text": "User inquired about REST API best practices. I covered versioning, error handling, and HATEOAS.",
            "role": "assistant",
            "timestamp": (datetime.now() - timedelta(days=45)).isoformat(),
            "source": "documentation",
            "recency_score": 0.35,
            "authority_score": 0.92
        },
        {
            "text": "User needed help with Git merge conflicts. I explained conflict resolution and rebase strategies.",
            "role": "assistant",
            "timestamp": (datetime.now() - timedelta(days=3)).isoformat(),
            "source": "chat",
            "recency_score": 0.90,
            "authority_score": 0.70
        },
    ]
    
    print(f"\nAdding {len(test_conversations)} test conversations...")
    
    for i, conv in enumerate(test_conversations, 1):
        metadata = {
            "conversation_id": f"test_conv_{i}",
            "message_id": f"msg_{i}",
            "role": conv["role"],
            "timestamp": conv["timestamp"],
            "source": conv["source"],
            "recency_score": conv["recency_score"],
            "authority_score": conv["authority_score"]
        }
        
        memory_id = vector_store.add_memory(
            text=conv["text"],
            metadata=metadata
        )
        
        print(f"  {i}. Added memory {memory_id[:8]}... (recency={conv['recency_score']:.2f}, authority={conv['authority_score']:.2f})")
    
    print(f"\nSuccessfully populated {len(test_conversations)} test memories")
    print("="*70 + "\n")
    
    return vector_store

if __name__ == "__main__":
    try:
        populate_test_data()
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
