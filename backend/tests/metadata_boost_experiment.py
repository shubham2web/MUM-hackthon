"""
Metadata Boost Experiment - Test multiplicative recency + authority boosts.

Formula: final_score = hybrid_score * (1 + recency_weight * recency_score + authority_weight * authority_score)

Grid:
- recency_weight ∈ [0.2, 0.4]
- authority_weight ∈ [0.4, 0.7]
"""
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# TODO: Implement metadata boost testing
# For now, user should manually test combinations after alpha sweep completes

print("Metadata Boost Experiment - Coming after alpha sweep completes")
print("\nTest combinations:")
print("1. recency=0.2, authority=0.4")
print("2. recency=0.2, authority=0.7")
print("3. recency=0.4, authority=0.4")
print("4. recency=0.4, authority=0.7")
print("\nImplementation: Modify hybrid_fusion.py apply_metadata_boost() method")
