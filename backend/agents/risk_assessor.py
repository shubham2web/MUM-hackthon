# agents/risk_assessor.py
class RiskAssessor:
    def __init__(self, config=None):
        self.config = config or {}

    def assess(self, dossier):
        # placeholder risk calculation
        return {"risk_level": "low", "reasons": []}
