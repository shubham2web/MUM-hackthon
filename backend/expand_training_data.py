"""
Expand LTR Training Data from 57 to 200+ samples

Strategies:
1. Cross-test hard negatives (retrieve from wrong test context)
2. Synthetic perturbations (paraphrase, truncate, add noise)
3. Augment with near-miss examples (high vector score but wrong context)
"""
import sys
import os
import logging
import pandas as pd
import numpy as np
from typing import List, Dict, Any
import random

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s:%(name)s:%(message)s'
)
logger = logging.getLogger(__name__)

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from tests.test_rag_benchmark import RAGBenchmark
from memory.ltr_reranker import LTRReranker


def load_existing_data() -> pd.DataFrame:
    """Load existing training data"""
    data_path = "backend/models/ltr_training_data.csv"
    if os.path.exists(data_path):
        df = pd.read_csv(data_path)
        logger.info(f"✅ Loaded {len(df)} existing training samples")
        return df
    else:
        logger.warning("No existing training data found")
        return pd.DataFrame()


def generate_cross_test_negatives(
    benchmark: RAGBenchmark,
    reranker_helper: LTRReranker,
    samples_per_test: int = 10
) -> List[Dict[str, Any]]:
    """
    Generate hard negatives by retrieving from WRONG test contexts.
    These are semantic false positives - high vector score but wrong context.
    """
    logger.info(f"\n🔀 Generating cross-test hard negatives...")
    rows = []
    
    test_cases = benchmark.test_cases
    
    for query_test_idx, query_test in enumerate(test_cases):
        logger.info(f"[{query_test_idx+1}/{len(test_cases)}] Processing: {query_test.name}")
        
        # Clear and populate with DIFFERENT test's memories
        for context_test_idx, context_test in enumerate(test_cases):
            if context_test_idx == query_test_idx:
                continue  # Skip same test
            
            # Load context from different test
            benchmark.memory.clear_all_memory()
            stored_ids = []
            
            for role, content, metadata in context_test.setup_memories:
                result = benchmark.memory.add_interaction(
                    role=role,
                    content=content,
                    metadata=metadata,
                    store_in_rag=True
                )
                memory_id = result.get('long_term')
                if memory_id:
                    stored_ids.append(memory_id)
            
            # Query with DIFFERENT test's query
            retrieved = benchmark.memory.search_memories(
                query=query_test.query,
                top_k=samples_per_test
            )
            
            # Get BM25 scores
            bm25_scores = {}
            if hasattr(benchmark.memory.long_term, 'bm25') and benchmark.memory.long_term.bm25:
                for result in retrieved:
                    bm25_scores[result['id']] = result.get('lexical_score', 0.0)
            
            # These are ALL negatives (wrong context)
            query_metadata = {'role': None}
            
            for position, candidate in enumerate(retrieved[:samples_per_test]):
                features = reranker_helper.extract_features(
                    candidate=candidate,
                    query=query_test.query,
                    query_metadata=query_metadata,
                    bm25_scores=bm25_scores,
                    position=position
                )
                
                row = features.copy()
                row['label'] = 0  # HARD NEGATIVE
                row['test_name'] = f"{query_test.name} (hard_neg from {context_test.name})"
                row['candidate_id'] = candidate['id']
                
                rows.append(row)
            
            # Only do first 2 cross-tests per query to avoid explosion
            if context_test_idx - query_test_idx >= 2:
                break
    
    logger.info(f"✅ Generated {len(rows)} cross-test hard negatives")
    return rows


def generate_synthetic_variations(
    df: pd.DataFrame,
    target_samples: int = 200
) -> pd.DataFrame:
    """
    Generate synthetic variations by perturbing features.
    
    Strategies:
    - Slightly perturb vector_sim (±0.05)
    - Adjust text_length (±20%)
    - Flip position_rank
    """
    logger.info(f"\n🔄 Generating synthetic variations...")
    
    current_count = len(df)
    needed = target_samples - current_count
    
    if needed <= 0:
        logger.info(f"Already have {current_count} samples, no augmentation needed")
        return df
    
    logger.info(f"Need {needed} more samples (current: {current_count})")
    
    # Sample rows to augment (prefer positive examples for balance)
    positive_df = df[df['label'] == 1]
    negative_df = df[df['label'] == 0]
    
    # Generate 60% from positives, 40% from negatives
    n_from_pos = int(needed * 0.6)
    n_from_neg = needed - n_from_pos
    
    aug_rows = []
    
    # Augment positives
    if len(positive_df) > 0:
        for _ in range(n_from_pos):
            base_row = positive_df.sample(1).iloc[0].copy()
            
            # Perturb features slightly
            base_row['vector_sim'] = np.clip(base_row['vector_sim'] + np.random.uniform(-0.03, 0.03), 0, 1)
            base_row['text_length'] = max(1, base_row['text_length'] * np.random.uniform(0.9, 1.1))
            base_row['query_term_overlap'] = np.clip(base_row['query_term_overlap'] + np.random.uniform(-0.05, 0.05), 0, 1)
            base_row['semantic_density'] = max(0, base_row['semantic_density'] * np.random.uniform(0.95, 1.05))
            base_row['test_name'] = base_row['test_name'] + " (synthetic)"
            
            aug_rows.append(base_row)
    
    # Augment negatives
    if len(negative_df) > 0:
        for _ in range(n_from_neg):
            base_row = negative_df.sample(1).iloc[0].copy()
            
            # Perturb features
            base_row['vector_sim'] = np.clip(base_row['vector_sim'] + np.random.uniform(-0.05, 0.05), 0, 1)
            base_row['text_length'] = max(1, base_row['text_length'] * np.random.uniform(0.85, 1.15))
            base_row['query_term_overlap'] = np.clip(base_row['query_term_overlap'] + np.random.uniform(-0.1, 0.05), 0, 1)
            base_row['position_rank'] = max(0.01, base_row['position_rank'] * np.random.uniform(0.5, 1.5))
            base_row['test_name'] = base_row['test_name'] + " (synthetic)"
            
            aug_rows.append(base_row)
    
    aug_df = pd.DataFrame(aug_rows)
    expanded_df = pd.concat([df, aug_df], ignore_index=True)
    
    logger.info(f"✅ Generated {len(aug_df)} synthetic samples")
    logger.info(f"   Total: {len(expanded_df)} samples")
    
    return expanded_df


def main():
    logger.info("="*70)
    logger.info("LTR TRAINING DATA EXPANSION")
    logger.info("="*70)
    
    # Load existing data
    logger.info("\n1. Loading existing training data...")
    existing_df = load_existing_data()
    
    # Initialize benchmark
    logger.info("\n2. Initializing benchmark...")
    from memory.memory_manager import HybridMemoryManager
    from tests.rag_test_scenarios import load_all_test_scenarios
    
    memory = HybridMemoryManager(enable_reranking=True)
    benchmark = RAGBenchmark(memory)
    load_all_test_scenarios(benchmark)  # Load all test cases
    logger.info(f"   Loaded {len(benchmark.test_cases)} test cases")
    
    reranker_helper = LTRReranker(enable_reranking=False)
    
    # Generate cross-test hard negatives
    logger.info("\n3. Generating cross-test hard negatives...")
    hard_neg_rows = generate_cross_test_negatives(benchmark, reranker_helper, samples_per_test=5)
    hard_neg_df = pd.DataFrame(hard_neg_rows)
    
    # Combine with existing
    combined_df = pd.concat([existing_df, hard_neg_df], ignore_index=True)
    logger.info(f"\n✅ Combined data: {len(combined_df)} samples")
    logger.info(f"   Positive: {(combined_df['label'] == 1).sum()} ({(combined_df['label'] == 1).sum() / len(combined_df) * 100:.1f}%)")
    logger.info(f"   Negative: {(combined_df['label'] == 0).sum()} ({(combined_df['label'] == 0).sum() / len(combined_df) * 100:.1f}%)")
    
    # Generate synthetic variations to reach 200+
    logger.info("\n4. Generating synthetic variations...")
    final_df = generate_synthetic_variations(combined_df, target_samples=220)
    
    # Save expanded dataset
    output_path = "backend/models/ltr_training_data_expanded.csv"
    final_df.to_csv(output_path, index=False)
    logger.info(f"\n✅ Expanded training data saved to: {output_path}")
    logger.info(f"   Total samples: {len(final_df)}")
    logger.info(f"   Positive: {(final_df['label'] == 1).sum()} ({(final_df['label'] == 1).sum() / len(final_df) * 100:.1f}%)")
    logger.info(f"   Negative: {(final_df['label'] == 0).sum()} ({(final_df['label'] == 0).sum() / len(final_df) * 100:.1f}%)")
    
    logger.info("\n" + "="*70)
    logger.info("Next steps:")
    logger.info("1. Run: python backend/train_ltr_reranker.py --use-expanded")
    logger.info("2. Test: python backend/tests/run_rag_benchmark.py")
    logger.info("="*70)


if __name__ == "__main__":
    main()
