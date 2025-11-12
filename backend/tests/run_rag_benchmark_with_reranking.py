"""
Run RAG benchmark WITH cross-encoder reranking enabled
"""
import sys
from pathlib import Path

backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

# Monkey patch to enable reranking
import memory.vector_store as vs_module
original_init = vs_module.VectorStore.__init__

def patched_init(self, *args, **kwargs):
    # Force enable reranking
    kwargs['enable_reranking'] = True
    kwargs['reranker_fusion_weight'] = 0.7
    original_init(self, *args, **kwargs)

vs_module.VectorStore.__init__ = patched_init

# Now run benchmark
from tests.run_rag_benchmark import main
main()
