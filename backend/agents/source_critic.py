# agents/source_critic.py
class SourceCritic:
    def __init__(self, config=None):
        self.config = config or {}

    def critique(self, evidence_bundle):
        # returns small list of flags for low-authority sources
        flags = []
        for e in evidence_bundle:
            if e.get("authority", 0.5) < 0.3:
                flags.append({"source": e.get("source_id"), "reason": "low_authority"})
        return flags
