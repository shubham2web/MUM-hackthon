# agents/factual_analyst.py
class FactualAnalyst:
    def __init__(self, config=None):
        self.config = config or {}

    def extract_claims(self, article_text: str):
        """
        Return list of primary factual claims extracted from text.
        Implementation: basic heuristics for now; replace with NER+model later.
        """
        # naive: split by sentences and return first 1-3 sentences as claims
        parts = [s.strip() for s in article_text.split('.') if s.strip()]
        return parts[:3]
