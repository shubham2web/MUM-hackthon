"""
DebateScorer: A comprehensive, configurable toolkit for analyzing debate quality.

This module provides a DebateScorer class to compute various metrics such as
trustworthiness, participant coverage, evidence diversity, and more from
debate transcripts and metadata.

Example Usage:
    from utils import DebateScorer  # Assuming file is named utils.py

    scorer = DebateScorer(precision=3)
    evidence = [{"type": "academic"}, {"type": "news"}]
    transcript = "--- STATEMENT FROM: Alice ---\\n--- STATEMENT FROM: Bob ---"
    turn_metrics = {"turn_count": 10, "rebuttal_count": 2, "audited_turn_count": 5}

    # Get a simple dictionary of scores
    scores = scorer.score(evidence, transcript, turn_metrics)
    print(scores)

    # Get a full breakdown with diagnostics
    explanation = scorer.explain(evidence, transcript, turn_metrics)
    print(explanation['diagnostics']['trustworthiness_details'])
"""
import json
import re
from collections import Counter
import math
from typing import List, Dict, Optional, Literal, Set, Union, TypedDict, Callable

# --- Type Definitions for clearer API contracts ---

class MetricsDict(TypedDict, total=False):
    trustworthiness_score: Optional[float]
    coverage_score: Optional[float]
    diversity_score: Optional[float]
    contradiction_ratio: Optional[float]
    bias_coverage: Optional[float]
    composite_score: Optional[float]

class CoverageDetails(TypedDict):
    role_counts: Dict[str, int]
    method: str
    raw_score: Optional[float]

class DiversityDetails(TypedDict):
    unique_types_found: List[str]
    possible_types: List[str]
    unknown_types_found: List[str]
    raw_score: Optional[float]

class TrustworthinessDetails(TypedDict):
    average_raw_score: Optional[float]
    per_item_scores: List[Dict[str, Union[str, float]]]
    unknown_types_found: List[str]

class RatioDetails(TypedDict):
    numerator: int
    denominator: int
    raw_score: Optional[float]

class CompositeScoreDetails(TypedDict):
    final_weights: Dict[str, float]
    adjusted_scores: Dict[str, float]
    final_score: Optional[float]

class DiagnosticsDict(TypedDict):
    coverage_details: CoverageDetails
    diversity_details: DiversityDetails
    trustworthiness_details: TrustworthinessDetails
    contradiction_ratio_details: RatioDetails
    bias_coverage_details: RatioDetails
    composite_score_details: Optional[CompositeScoreDetails]

class DetailedOutputDict(TypedDict):
    metrics: MetricsDict
    diagnostics: DiagnosticsDict

# --- Constants ---
DEFAULT_EVIDENCE_SCORES = {"academic": 1.0, "dataset": 0.9, "news": 0.7}
DEFAULT_EVIDENCE_SCORE_FALLBACK = 0.5
ROLE_PATTERN = re.compile(
    r"---\s*STATEMENT\s+FROM\s*[:-]?\s*(.+?)\s*(?:---\s*)?$",
    re.IGNORECASE | re.MULTILINE
)

# --- Standalone Utility Functions ---

def is_valid_http_url(url: str) -> bool:
    """Checks if a URL has a valid HTTP or HTTPS scheme."""
    if not isinstance(url, str):
        return False
    return url.strip().startswith(("http://", "https://"))

# --- Main Scorer Class ---

class DebateScorer:
    """A configurable class to compute advanced debate analytics."""

    def __init__(
        self,
        scoring_config: Optional[Dict] = None,
        composite_weights: Optional[Dict[str, float]] = None,
        composite_inverted_metrics: Optional[Set[str]] = None,
        coverage_method: Literal['cv', 'gini', 'entropy'] = 'cv',
        entropy_include_zeros: bool = False,
        role_normalizer: Optional[Callable[[str], str]] = None,
        precision: int = 3,
        logger: Optional[Callable[[str, dict], None]] = None,
    ):
        if composite_weights and any(w < 0 for w in composite_weights.values()):
            raise ValueError("Composite weights must be non-negative.")

        self.scoring_config = scoring_config or DEFAULT_EVIDENCE_SCORES
        self.all_types = [k for k in self.scoring_config if k != "__fallback__"]
        self.composite_weights = composite_weights
        self.composite_inverted_metrics = composite_inverted_metrics
        self.coverage_method = coverage_method
        self.entropy_include_zeros = entropy_include_zeros
        self.role_normalizer = role_normalizer or (lambda s: re.sub(r"\s+", " ", s.strip().lower()))
        self.precision = precision
        self.logger = logger

    @classmethod
    def from_config(cls, config: dict) -> 'DebateScorer':
        """Creates a DebateScorer instance from a configuration dictionary."""
        return cls(**config)

    def score(
        self,
        evidence_bundle: List[Dict],
        transcript: str,
        turn_metrics: Dict,
        expected_roles: Optional[List[str]] = None
    ) -> MetricsDict:
        """Computes and returns the core metrics for a debate."""
        result = self._compute_analytics(
            evidence_bundle, transcript, turn_metrics, expected_roles, detailed_output=False, include_composite=True
        )
        return result

    def explain(
        self,
        evidence_bundle: List[Dict],
        transcript: str,
        turn_metrics: Dict,
        expected_roles: Optional[List[str]] = None
    ) -> DetailedOutputDict:
        """Computes and returns metrics along with detailed diagnostics."""
        result = self._compute_analytics(
            evidence_bundle, transcript, turn_metrics, expected_roles, detailed_output=True, include_composite=True
        )
        return result

    def _compute_analytics(
        self, evidence_bundle, transcript, turn_metrics, expected_roles, detailed_output, include_composite
    ) -> Union[MetricsDict, DetailedOutputDict]:
        """Internal analytics pipeline, wrapped by score() and explain()."""
        if self.logger: self.logger("analytics_start", {"config_keys": self.all_types})

        ratio_details = self._compute_ratios(turn_metrics)
        raw_diversity_score, unique_types, unknown_types = self._compute_diversity(evidence_bundle)
        raw_coverage_score, role_counts = self._compute_coverage(transcript, expected_roles)
        raw_trustworthiness_score, trust_scores_details = self._compute_trustworthiness(evidence_bundle)

        metrics: MetricsDict = {
            "trustworthiness_score": self._sanitize_score(raw_trustworthiness_score),
            "coverage_score": self._sanitize_score(raw_coverage_score),
            "diversity_score": self._sanitize_score(raw_diversity_score),
            "contradiction_ratio": self._sanitize_score(ratio_details["contradiction_ratio"]["raw_score"]),
            "bias_coverage": self._sanitize_score(ratio_details["bias_coverage"]["raw_score"])
        }

        comp_details = None
        if include_composite:
            comp_details = self._compute_composite_score(metrics)
            metrics["composite_score"] = comp_details.get("final_score")

        if detailed_output:
            diagnostics: DiagnosticsDict = {
                "coverage_details": {"role_counts": role_counts, "method": self.coverage_method, "raw_score": raw_coverage_score},
                "diversity_details": {"unique_types_found": sorted(list(unique_types)), "possible_types": self.all_types, "unknown_types_found": sorted(list(unknown_types)), "raw_score": raw_diversity_score},
                "trustworthiness_details": {"average_raw_score": raw_trustworthiness_score, "per_item_scores": trust_scores_details, "unknown_types_found": sorted(list(unknown_types))},
                "contradiction_ratio_details": ratio_details["contradiction_ratio"],
                "bias_coverage_details": ratio_details["bias_coverage"],
                "composite_score_details": comp_details
            }
            if self.logger: self.logger("analytics_end", {"metrics": metrics, "diagnostics": diagnostics})
            return {"metrics": metrics, "diagnostics": diagnostics}
        
        if self.logger: self.logger("analytics_end", {"metrics": metrics})
        return metrics

    # --- Private Helper Methods ---
    def _sanitize_score(self, val: Optional[float]) -> Optional[float]:
        if val is None: return None
        multiplier = 10 ** self.precision
        return round(max(0.0, min(1.0, val)) * multiplier) / multiplier

    def _compute_trustworthiness(self, evidence_bundle: List[Dict]) -> (Optional[float], List[Dict]):
        if not evidence_bundle: return None, []
        fallback = self.scoring_config.get("__fallback__", DEFAULT_EVIDENCE_SCORE_FALLBACK)
        
        scores_details = []
        for item in evidence_bundle:
            item_type = item.get("type") or "unknown"
            score = self.scoring_config.get(item_type, fallback)
            scores_details.append({"type": item_type, "score": score})
            
        scores = [d['score'] for d in scores_details]
        avg_score = sum(scores) / len(scores) if scores else 0
        return max(0.0, min(1.0, avg_score)), scores_details

    def _compute_diversity(self, evidence_bundle: List[Dict]) -> (Optional[float], Set[str], Set[str]):
        known_types_set = set(self.all_types)
        seen_types = {item.get("type") for item in evidence_bundle if item.get("type")}
        unknown_types = seen_types - known_types_set
        known_seen_types = seen_types & known_types_set
        if not evidence_bundle or not self.all_types: return None, seen_types, unknown_types
        return len(known_seen_types) / len(self.all_types), seen_types, unknown_types

    def _compute_coverage(self, transcript: str, expected_roles: Optional[List[str]]) -> (Optional[float], Dict[str, int]):
        roles_found = [self.role_normalizer(r) for r in ROLE_PATTERN.findall(transcript)]
        role_counts = Counter(roles_found)
        if expected_roles:
            for role in (self.role_normalizer(r) for r in expected_roles):
                role_counts.setdefault(role, 0)
        if not role_counts: return None, {}
        score = self._calculate_balance(list(role_counts.values()))
        return score, dict(role_counts)

    def _calculate_balance(self, counts: List[int]) -> float:
        method = self.coverage_method
        if len(counts) < 2: return 1.0
        if method == 'entropy':
            total = sum(counts)
            if total == 0: return 1.0
            if self.entropy_include_zeros:
                proportions = [(c / total) if c > 0 else 0 for c in counts]
                k = len(counts)
            else:
                proportions = [c / total for c in counts if c > 0]
                k = len(proportions)
            if k < 2: return 1.0
            entropy = -sum(p * math.log2(p) for p in proportions if p > 0)
            max_entropy = math.log2(k)
            return entropy / max_entropy if max_entropy > 0 else 1.0
        if method == 'gini':
            total = sum(counts)
            if total == 0: return 1.0
            sorted_counts = sorted(counts); cum_sum, gini_sum, n = 0, 0, len(counts)
            for c in sorted_counts: cum_sum += c; gini_sum += cum_sum
            raw_gini = (2*gini_sum-total*(n+1))/(total*n) if total*n != 0 else 0
            return 1.0 - raw_gini
        # Default: CV
        mean = sum(counts) / len(counts);
        if mean == 0: return 1.0
        std_dev = math.sqrt(sum((x-mean)**2 for x in counts)/len(counts))
        return max(0, 1-(std_dev/mean))
        
    def _compute_ratios(self, turn_metrics: Dict) -> Dict[str, RatioDetails]:
        turn_count = turn_metrics.get("turn_count", 0)
        rebuttal_count = turn_metrics.get("rebuttal_count", 0)
        audited_turn_count = turn_metrics.get("audited_turn_count", 0)
        contra_score = (rebuttal_count / turn_count) if turn_count > 0 else None
        bias_score = (audited_turn_count / turn_count) if turn_count > 0 else None
        return {
            "contradiction_ratio": {"numerator": rebuttal_count, "denominator": turn_count, "raw_score": contra_score},
            "bias_coverage": {"numerator": audited_turn_count, "denominator": turn_count, "raw_score": bias_score}
        }

    def _compute_composite_score(self, metrics: MetricsDict) -> CompositeScoreDetails:
        inverted_metrics = self.composite_inverted_metrics
        if inverted_metrics is None:
            inverted_metrics = {"contradiction_ratio", "bias_coverage"}

        default_weights = {
            "trustworthiness_score": 0.3, "coverage_score": 0.25, "diversity_score": 0.2,
            "contradiction_ratio": 0.15, "bias_coverage": 0.1
        }
        final_weights = self.composite_weights or default_weights
        
        valid_metrics = {k: v for k, v in metrics.items() if v is not None and k in final_weights}
        
        final_score = None
        adjusted_metrics = {}
        if valid_metrics:
            adjusted_metrics = {k: self._sanitize_score(1 - v if k in inverted_metrics else v) for k, v in valid_metrics.items()}
            total_weight = sum(final_weights[k] for k in adjusted_metrics.keys())
            if total_weight > 0:
                weighted_sum = sum(adjusted_metrics[k] * final_weights[k] for k in adjusted_metrics.keys())
                final_score = round(weighted_sum / total_weight, self.precision)
                
        return {
            "final_weights": {k: final_weights.get(k) for k in valid_metrics},
            "adjusted_scores": adjusted_metrics,
            "final_score": final_score
        }

# --- SERVER HELPER FUNCTIONS ---

def compute_advanced_analytics(evidence: List[Dict], transcript: str, turn_metrics: Dict) -> Dict:
    """
    A convenience function to quickly compute debate analytics using DebateScorer.
    This acts as a simple entry point for the server.
    """
    # Use a fresh scorer instance for each analysis
    scorer = DebateScorer(precision=4)
    
    # The 'explain' method provides a detailed breakdown, which is 
    # suitable for the "advanced analytics" endpoint.
    return scorer.explain(evidence, transcript, turn_metrics)

def format_sse(data: dict, event: str = None) -> str:
    """
    Formats a dictionary into a compliant Server-Sent Event (SSE) string.
    """
    # Convert the data dictionary to a JSON string
    json_data = json.dumps(data)
    
    # Format the payload according to the SSE specification
    payload = f"data: {json_data}\n"
    if event:
        payload = f"event: {event}\n{payload}"
    
    # The final newline is crucial for the client to recognize the end of the event
    return f"{payload}\n"
