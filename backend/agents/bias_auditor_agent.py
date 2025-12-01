# agents/bias_auditor_agent.py
class BiasAuditorAgent:
    def __init__(self, config=None):
        self.config = config or {}

    def audit_text(self, text: str) -> dict:
        # Simple heuristics - count emotionally loaded words
        flags = []
        words = text.lower()
        if "insist" in words or "desperate" in words:
            flags.append({"type":"framing_bias", "severity":0.6, "explanation":"loaded language"})
        overall = min(1.0, 0.1 * len(flags))
        return {"flags": flags, "overall_score": overall}
