# agents/forensic_agent.py
class ForensicAgent:
    def __init__(self, config=None):
        self.config = config or {}

    def build_dossier(self, entities: list) -> dict:
        # For now, simple placeholder
        dossier = {"entities": []}
        for ent in entities:
            dossier["entities"].append({
                "name": ent,
                "reputation_score": 0.5,
                "red_flags": [],
                "sources": []
            })
        return dossier
