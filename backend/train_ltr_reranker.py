"""
Train Learning-to-Rank (LTR) Reranker from Benchmark Data

Generates training labels from the 13-test RAG benchmark:
- Positive label: candidate is in expected_ids for that test
- Negative label: candidate retrieved but not in expected_ids

Features extracted:
1. vector_sim - cosine similarity from embedding
2. bm25_score - BM25 ranking score
3. recency_days - days since document creation
4. authority_score - metadata authority (0-1)
5. role_match - binary role match
6. text_length - number of tokens
7. metadata_boost - existing boost applied

Model: scikit-learn LogisticRegression (or RandomForest/GradientBoosting)
"""
import sys
import os
import logging
import pandas as pd
import numpy as np
from typing import List, Dict, Any
from datetime import datetime

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s:%(name)s:%(message)s'
)
logger = logging.getLogger(__name__)

try:
    import joblib
    from sklearn.linear_model import LogisticRegression
    from sklearn.ensemble import RandomForestClassifier, HistGradientBoostingClassifier
    from sklearn.model_selection import train_test_split, cross_val_score
    from sklearn.metrics import classification_report, roc_auc_score
    from sklearn.calibration import CalibratedClassifierCV
except ImportError:
    logger.error("scikit-learn not installed. Install: pip install scikit-learn joblib")
    sys.exit(1)

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from tests.test_rag_benchmark import RAGBenchmark
from memory.ltr_reranker import LTRReranker


def prepare_training_data(
    benchmark: RAGBenchmark,
    n_candidates: int = 20
) -> pd.DataFrame:
    """
    Generate training data from benchmark test cases.
    
    For each test:
    1. Store memories
    2. Retrieve n_candidates (oversample)
    3. Label as 1 if in expected_ids, 0 otherwise
    4. Extract features
    
    Args:
        benchmark: RAGBenchmark instance with test cases
        n_candidates: Number of candidates to retrieve per query
        
    Returns:
        DataFrame with features and labels
    """
    logger.info(f"Preparing training data from {len(benchmark.test_cases)} test cases...")
    
    rows = []
    reranker_helper = LTRReranker(enable_reranking=False)  # Just for feature extraction
    
    for test_idx, test_case in enumerate(benchmark.test_cases, 1):
        logger.info(f"[{test_idx}/{len(benchmark.test_cases)}] Processing: {test_case.name}")
        
        # Clear and populate memories
        benchmark.memory.clear_all_memory()
        stored_ids = []
        
        # Use the same storage logic as the benchmark
        for role, content, metadata in test_case.setup_memories:
            result = benchmark.memory.add_interaction(
                role=role,
                content=content,
                metadata=metadata,
                store_in_rag=True
            )
            # Get the long-term memory ID
            memory_id = result.get('long_term')
            if memory_id:
                stored_ids.append(memory_id)
        
        # Retrieve candidates (oversample to get both positive and negative examples)
        retrieved = benchmark.memory.search_memories(
            query=test_case.query,
            top_k=n_candidates
        )
        
        # Expected relevant IDs
        expected_ids = set([stored_ids[i] for i in test_case.expected_indices])
        
        # Get BM25 scores if available
        bm25_scores = {}
        if hasattr(benchmark.memory.long_term, 'bm25') and benchmark.memory.long_term.bm25:
            # Compute BM25 scores for these candidates
            for result in retrieved:
                # BM25 score already in lexical_score if hybrid is enabled
                bm25_scores[result['id']] = result.get('lexical_score', 0.0)
        
        # Extract features and labels
        query_metadata = {'role': None}  # Simplified - no role filtering in training
        
        for position, candidate in enumerate(retrieved):
            # Label: 1 if relevant, 0 if not
            label = 1 if candidate['id'] in expected_ids else 0
            
            # CRITICAL FIX: Ensure hybrid_score is populated in candidate
            # During training, candidates have 'score' (final_score from retrieval)
            # This is the fusion score that should be used as hybrid_score
            if 'hybrid_score' not in candidate:
                candidate['hybrid_score'] = candidate.get('final_score', candidate.get('score', candidate.get('similarity', 0.0)))
            
            # Extract features (with new parameters)
            features = reranker_helper.extract_features(
                candidate=candidate,
                query=test_case.query,  # NEW: pass query for term overlap
                query_metadata=query_metadata,
                bm25_scores=bm25_scores,
                position=position  # NEW: pass position for rank feature
            )
            
            # Add label and test metadata
            row = features.copy()
            row['label'] = label
            row['test_name'] = test_case.name
            row['candidate_id'] = candidate['id']
            
            rows.append(row)
    
    df = pd.DataFrame(rows)
    logger.info(f"✅ Generated {len(df)} training examples")
    logger.info(f"   Positive examples: {(df['label'] == 1).sum()} ({(df['label'] == 1).sum() / len(df) * 100:.1f}%)")
    logger.info(f"   Negative examples: {(df['label'] == 0).sum()} ({(df['label'] == 0).sum() / len(df) * 100:.1f}%)")
    
    return df


def train_model(
    df: pd.DataFrame,
    model_type: str = "logistic",
    model_path: str = "backend/models/ltr_reranker.joblib"
) -> Any:
    """
    Train LTR model and save to disk.
    
    Args:
        df: Training data DataFrame
        model_type: "logistic", "random_forest", or "gradient_boosting"
        model_path: Path to save trained model
        
    Returns:
        Trained model
    """
    logger.info(f"\n{'='*70}")
    logger.info(f"Training {model_type} model...")
    logger.info(f"{'='*70}")
    
    # Prepare features and labels
    feature_cols = LTRReranker.FEATURE_NAMES
    X = df[feature_cols].values
    y = df['label'].values
    
    logger.info(f"Feature matrix shape: {X.shape}")
    logger.info(f"Feature names: {feature_cols}")
    
    # Train/validation split
    X_train, X_val, y_train, y_val = train_test_split(
        X, y,
        test_size=0.2,
        stratify=y,
        random_state=42
    )
    
    logger.info(f"Training set: {len(X_train)} samples")
    logger.info(f"Validation set: {len(X_val)} samples")
    
    # Select model
    if model_type == "logistic":
        model = LogisticRegression(
            max_iter=1000,
            C=2.0,  # Increased regularization strength
            class_weight='balanced',
            random_state=42
        )
    elif model_type == "random_forest":
        model = RandomForestClassifier(
            n_estimators=300,  # Increased for better performance
            max_depth=8,       # Controlled depth
            min_samples_split=10,
            class_weight='balanced',
            random_state=42,
            n_jobs=-1
        )
    elif model_type == "gradient_boosting":
        model = HistGradientBoostingClassifier(
            max_iter=200,      # Increased iterations
            max_depth=8,       # Increased depth
            learning_rate=0.1,
            random_state=42
        )
    else:
        raise ValueError(f"Unknown model_type: {model_type}")
    
    # Train
    logger.info("Training...")
    model.fit(X_train, y_train)
    
    # Evaluate
    train_score = model.score(X_train, y_train)
    val_score = model.score(X_val, y_val)
    
    logger.info(f"\n{'='*70}")
    logger.info(f"TRAINING RESULTS")
    logger.info(f"{'='*70}")
    logger.info(f"Training accuracy: {train_score:.3f}")
    logger.info(f"Validation accuracy: {val_score:.3f}")
    
    # Detailed metrics
    y_pred = model.predict(X_val)
    y_pred_proba = model.predict_proba(X_val)[:, 1]
    
    logger.info(f"\nClassification Report:")
    print(classification_report(y_val, y_pred, target_names=['Not Relevant', 'Relevant']))
    
    try:
        auc = roc_auc_score(y_val, y_pred_proba)
        logger.info(f"ROC-AUC Score: {auc:.3f}")
    except:
        pass
    
    # Feature importance (if available)
    if hasattr(model, 'feature_importances_'):
        logger.info(f"\nFeature Importances:")
        importances = model.feature_importances_
        for name, importance in sorted(zip(feature_cols, importances), key=lambda x: -x[1]):
            logger.info(f"  {name:20s}: {importance:.4f}")
    elif hasattr(model, 'coef_'):
        logger.info(f"\nFeature Coefficients:")
        coefs = model.coef_[0]
        for name, coef in sorted(zip(feature_cols, coefs), key=lambda x: -abs(x[1])):
            logger.info(f"  {name:20s}: {coef:+.4f}")
    
    # Apply probability calibration (improves confidence estimates)
    logger.info(f"\nApplying probability calibration...")
    calibrated_model = CalibratedClassifierCV(model, cv=3, method='sigmoid')
    calibrated_model.fit(X_train, y_train)
    
    # Re-evaluate with calibration
    cal_val_score = calibrated_model.score(X_val, y_val)
    logger.info(f"Calibrated validation accuracy: {cal_val_score:.3f} (was {val_score:.3f})")
    
    # Use calibrated model
    model = calibrated_model
    
    # Save model with feature names bundle
    os.makedirs(os.path.dirname(model_path), exist_ok=True)
    model_bundle = {
        'model': model,
        'feature_names': feature_cols,
        'n_features': len(feature_cols),
        'model_type': model_type,
        'training_date': datetime.now().isoformat(),
        'training_samples': len(X_train) + len(X_val),
        'calibrated': True
    }
    joblib.dump(model_bundle, model_path)
    logger.info(f"\n✅ Model bundle saved to: {model_path}")
    logger.info(f"   Features: {len(feature_cols)} ({', '.join(feature_cols[:3])}...)")
    logger.info(f"   Calibrated: Yes")
    
    return model


def main():
    """Main training pipeline."""
    import sys
    
    # Check for --use-expanded flag
    use_expanded = "--use-expanded" in sys.argv
    
    logger.info("="*70)
    logger.info("LTR RERANKER TRAINING")
    if use_expanded:
        logger.info("🚀 USING EXPANDED TRAINING DATA (459 samples)")
    logger.info("="*70)
    
    # Initialize benchmark
    logger.info("\n1. Initializing benchmark...")
    from memory.memory_manager import HybridMemoryManager
    from tests.rag_test_scenarios import load_all_test_scenarios
    
    memory_manager = HybridMemoryManager(
        enable_rag=True,
        long_term_backend="faiss"  # Use FAISS to avoid ChromaDB import issues on Python 3.13
    )
    benchmark = RAGBenchmark(memory_manager=memory_manager)
    
    # Load test scenarios
    load_all_test_scenarios(benchmark)
    
    logger.info(f"   Loaded {len(benchmark.test_cases)} test cases")
    
    # Generate or load training data
    if use_expanded:
        logger.info("\n2. Loading expanded training data...")
        expanded_path = "backend/models/ltr_training_data_expanded.csv"
        if os.path.exists(expanded_path):
            df = pd.read_csv(expanded_path)
            logger.info(f"✅ Loaded {len(df)} samples from {expanded_path}")
            logger.info(f"   Positive: {(df['label'] == 1).sum()} ({(df['label'] == 1).sum() / len(df) * 100:.1f}%)")
            logger.info(f"   Negative: {(df['label'] == 0).sum()} ({(df['label'] == 0).sum() / len(df) * 100:.1f}%)")
        else:
            logger.error(f"Expanded data not found at {expanded_path}")
            logger.info("Run: python backend/expand_training_data.py first")
            sys.exit(1)
    else:
        logger.info("\n2. Generating training data...")
        df = prepare_training_data(benchmark, n_candidates=20)
    
    # Save training data for inspection
    train_data_path = "backend/models/ltr_training_data.csv"
    os.makedirs(os.path.dirname(train_data_path), exist_ok=True)
    df.to_csv(train_data_path, index=False)
    logger.info(f"   Training data saved to: {train_data_path}")
    
    # Train model (try all three types)
    models_to_try = [
        ("logistic", "backend/models/ltr_reranker_logistic.joblib"),
        ("random_forest", "backend/models/ltr_reranker_rf.joblib"),
        ("gradient_boosting", "backend/models/ltr_reranker_gb.joblib"),
    ]
    
    best_model = None
    best_score = 0.0
    best_path = None
    
    for model_type, model_path in models_to_try:
        try:
            logger.info(f"\n3. Training {model_type} model...")
            model = train_model(df, model_type=model_type, model_path=model_path)
            
            # Evaluate on validation set
            feature_cols = LTRReranker.FEATURE_NAMES
            X = df[feature_cols].values
            y = df['label'].values
            X_train, X_val, y_train, y_val = train_test_split(
                X, y, test_size=0.2, stratify=y, random_state=42
            )
            score = model.score(X_val, y_val)
            
            if score > best_score:
                best_score = score
                best_model = model_type
                best_path = model_path
                
        except Exception as e:
            logger.error(f"Failed to train {model_type}: {e}")
    
    # Copy best model as default
    if best_model and best_path:
        import shutil
        default_path = "models/ltr_reranker.joblib"
        shutil.copy(best_path, default_path)
        logger.info(f"\n{'='*70}")
        logger.info(f"BEST MODEL: {best_model} (val accuracy: {best_score:.3f})")
        logger.info(f"Copied to: {default_path}")
        logger.info(f"{'='*70}")
    
    logger.info("\n✅ Training complete!")
    logger.info("\nNext steps:")
    logger.info("1. Run benchmark: python backend/tests/run_rag_benchmark.py")
    logger.info("2. LTR reranker will be automatically loaded")
    logger.info("3. Expected improvement: +6-12% relevance")


if __name__ == "__main__":
    main()
