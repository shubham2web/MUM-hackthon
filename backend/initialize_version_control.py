"""
Initialize RAG Version Control with historical optimization data
Run this once to populate the version history with Steps 1-5
"""

from rag_version_control import RAGVersionControl

def initialize_history():
    """Populate version control with historical data from Steps 1-5"""
    
    vc = RAGVersionControl()
    
    print("\n" + "="*70)
    print("INITIALIZING RAG VERSION CONTROL WITH HISTORICAL DATA")
    print("="*70 + "\n")
    
    # Step 1: baseline-v1
    print("📦 Adding baseline-v1 (Step 1)...")
    vc.save_version(
        version_name="baseline-v1",
        relevance=71.78,
        alpha=0.75,
        tests_passed=5,
        total_tests=13,
        precision=32.95,
        recall=92.31,
        f1_score=47.51,
        notes="Step 1: Initial baseline with 75% vector / 25% lexical fusion",
        enable_reranking=False,
        tags=["baseline", "step-1"]
    )
    
    # Step 2: alpha-v2
    print("📦 Adding alpha-v2 (Step 2)...")
    vc.save_version(
        version_name="alpha-v2",
        relevance=72.95,
        alpha=0.85,
        tests_passed=5,
        total_tests=13,
        precision=32.95,
        recall=92.31,
        f1_score=47.51,
        notes="Step 2: Alpha sweep optimization found 0.85 optimal (+1.17% gain)",
        enable_reranking=False,
        tags=["optimized", "step-2"]
    )
    
    # Step 4: hgb-v3 (REJECTED)
    print("📦 Adding hgb-v3 (Step 4 - REJECTED)...")
    vc.save_version(
        version_name="hgb-v3",
        relevance=70.29,
        alpha=0.85,
        tests_passed=6,
        total_tests=13,
        precision=32.95,
        recall=92.31,
        f1_score=47.51,
        notes="Step 4: HGB soft bias (0.3 weight) REJECTED - caused -2.66% regression. Root: insufficient training data (57 samples), feature mismatch, poor generalization.",
        enable_reranking=True,
        tags=["rejected", "step-4", "hgb"]
    )
    
    # Step 5: alpha-v3 (CURRENT)
    print("📦 Adding alpha-v3 (Step 5 - CURRENT)...")
    vc.save_version(
        version_name="alpha-v3",
        relevance=73.51,
        alpha=0.90,
        tests_passed=5,
        total_tests=13,
        precision=32.95,
        recall=92.31,
        f1_score=47.51,
        notes="Step 5: Fine-grained alpha sweep found 0.90 optimal (+0.56% vs alpha-v2, +1.73% total from baseline)",
        enable_reranking=False,
        tags=["current", "optimized", "step-5", "stable"]
    )
    
    print("\n" + "="*70)
    print("✅ VERSION CONTROL INITIALIZED SUCCESSFULLY")
    print("="*70 + "\n")
    
    # Display version history
    vc.list_versions(verbose=False)
    
    # Promote alpha-v3
    print("\n" + "="*70)
    print("EVALUATING alpha-v3 FOR PROMOTION")
    print("="*70)
    
    promotion_criteria = {
        "min_relevance_gain": 0.5,   # Require ≥0.5pp improvement
        "no_test_regression": True,   # No test failures
        "min_relevance": 70.0,        # Minimum 70% relevance
    }
    
    vc.promote_version(
        version_name="alpha-v3",
        criteria=promotion_criteria,
        tags=["production", "recommended"]
    )
    
    # Compare alpha-v2 vs alpha-v3
    print("\n")
    vc.compare_versions("alpha-v2", "alpha-v3")
    
    # Export history
    print("\n")
    vc.export_history("rag_optimization_history.csv")
    
    print("\n" + "="*70)
    print("USAGE EXAMPLES:")
    print("="*70)
    print("\n# List all versions:")
    print("  python rag_version_control.py list --verbose")
    print("\n# Rollback to previous version:")
    print("  python rag_version_control.py rollback --version alpha-v2")
    print("\n# Compare versions:")
    print("  python rag_version_control.py compare --version baseline-v1 --version2 alpha-v3")
    print("\n# Save new version:")
    print("  python rag_version_control.py save --version alpha-v4 --relevance 74.2 --alpha 0.92 --notes 'Testing higher alpha'")
    print("\n# Promote version:")
    print("  python rag_version_control.py promote --version alpha-v4 --tags stable production")
    print("\n" + "="*70 + "\n")

if __name__ == "__main__":
    initialize_history()
