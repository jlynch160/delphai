"""Verifier — the grounding/anti-hallucination integrity check. Confirms every
citation used by other agents actually resolves to the approved knowledge base, and
reports an integrity score. Ungrounded claims are flagged, not trusted."""
from __future__ import annotations

from .base import BaseAgent, Turn


class VerifierAgent(BaseAgent):
    name = "Omar Said"
    persona_label = "Compliance & Integrity"
    color = "bright_blue"
    system_prompt = ("You are Omar Said, the Compliance & Integrity officer. Terse and uncompromising "
                     "about provenance. You confirm every cited claim traces to an approved source and "
                     "you flag anything ungrounded. No claim gets a pass without a receipt.")

    def verify(self, citations_used: list[str], assessment_grounded: bool) -> Turn:
        unique = sorted({c for c in citations_used if c})
        verified = [c for c in unique if self.store.citation_exists(c)]
        unverified = [c for c in unique if not self.store.citation_exists(c)]
        integrity = round(len(verified) / max(len(unique), 1), 3)

        lines = [f"Citations checked: {len(unique)} → {len(verified)} verified, {len(unverified)} unverified",
                 "Verified sources: " + (", ".join(verified) if verified else "none")]
        if unverified:
            lines.append("⚠ UNVERIFIED (flagged, not trusted): " + ", ".join(unverified))
        if not assessment_grounded:
            lines.append("⚠ Assessment item's source not found in KB — question quarantined.")
        lines.append(f"Grounding integrity score: {integrity:.0%}")

        fallback = (f"Integrity {integrity:.0%}: {len(verified)}/{len(unique)} citations resolve to "
                    f"approved sources" + (". All claims grounded." if not unverified
                    else f"; flagged {len(unverified)} ungrounded."))
        headline = self.voice("Report the grounding integrity verdict.", "\n".join(lines), fallback)
        return Turn(self.name, self.persona_label, self.color, headline, lines, kind="verify",
                    data={"integrity": integrity, "unverified": unverified})
