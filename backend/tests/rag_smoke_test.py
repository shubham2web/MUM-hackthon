"""Quick smoke test for the hybrid RAG memory stack.

Run with:
    python -m backend.tests.rag_smoke_test

This script seeds a few synthetic debate turns, performs a hybrid
vector+lexical search, and prints the resulting context payload so you
can confirm the retrieval path end-to-end.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from textwrap import dedent

# Ensure the repository backend package is importable when the script
# is executed from the workspace root (python -m backend.tests.*)
BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from memory.memory_manager import get_memory_manager


def seed_sample_memories(memory_manager):
    """Populate the memory manager with a few representative turns."""
    sample_turns = [
        {
            "role": "user",
            "content": "How fast is misinformation spreading on TikTok about vaccines?",
            "metadata": {"topic": "vaccines", "channel": "tiktok"},
        },
        {
            "role": "assistant",
            "content": "Recent reports show a spike in short-form anti-vax content targeting teens.",
            "metadata": {"topic": "vaccines", "channel": "analysis"},
        },
        {
            "role": "researcher",
            "content": "CDC bulletin: 32% increase in vaccine misinformation across social media Q3 2025.",
            "metadata": {"topic": "vaccines", "source": "cdc", "quarter": "2025-Q3"},
        },
        {
            "role": "analyst",
            "content": "Facebook mitigation efforts reduced false shares by 12% after labeling campaigns.",
            "metadata": {"topic": "platform countermeasures", "channel": "facebook"},
        },
    ]

    for turn in sample_turns:
        memory_manager.add_interaction(
            role=turn["role"],
            content=turn["content"],
            metadata=turn.get("metadata"),
            store_in_rag=True,
        )


def run_search(memory_manager, query: str):
    """Execute a hybrid search and return structured results."""
    results = memory_manager.search_memories(
        query=query,
        top_k=5,
        similarity_threshold=0.35,
    )

    return [
        {
            "rank": item["rank"],
            "score": round(item["score"], 4),
            "snippet": item["text"],
            "metadata": item.get("metadata"),
        }
        for item in results
    ]


def main() -> None:
    # Force FAISS backend to avoid Python 3.13 Chroma issues in the smoke test.
    os.environ.setdefault("ATLAS_VECTOR_BACKEND", "faiss")

    memory_manager = get_memory_manager(
        reset=True,
        long_term_backend="faiss",
        enable_reranking=False,
    )

    seed_sample_memories(memory_manager)

    query = "latest vaccine misinformation stats"
    retrieved = run_search(memory_manager, query)

    print("\n[Hybrid Search Results]\n-----------------------")
    print(json.dumps(retrieved, indent=2))

    payload = memory_manager.build_context_payload(
        system_prompt="You are ATLAS, an analyst fighting misinformation.",
        current_task=f"Answer the query: {query}",
        query=query,
        top_k_rag=3,
    )

    print("\n[Context Payload Preview]\n-------------------------")
    print(dedent("\n".join(payload.splitlines()[:40])))
    print("\n... (truncated)\n")


if __name__ == "__main__":
    main()
