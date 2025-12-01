# agents/evidence_synthesizer.py
class EvidenceSynthesizer:
    def __init__(self, config=None):
        self.config = config or {}

    def enrich(self, evidence_bundle):
        # annotate evidence with simple metadata if missing
        for idx, e in enumerate(evidence_bundle):
            e.setdefault("authority", e.get("authority", 0.5))
            e.setdefault("snippet", e.get("snippet", e.get("excerpt","")))
        return evidence_bundle
