"""Agent base class and the Turn object the console renders."""
from __future__ import annotations
from dataclasses import dataclass, field

from ..data_store import DataStore
from ..model_client import ModelClient


@dataclass
class Turn:
    agent: str                 # display name
    persona_label: str         # short role tag
    color: str                 # rich color
    headline: str              # one/two-line spoken summary (model voice or fallback)
    lines: list[str] = field(default_factory=list)   # structured detail bullets
    data: dict = field(default_factory=dict)         # payload for downstream agents
    kind: str = "info"         # info|optimist|skeptic|burnout|verify|verdict|negotiate|gate


class BaseAgent:
    name: str = "Agent"
    persona_label: str = ""
    color: str = "white"
    system_prompt: str = ""

    def __init__(self, store: DataStore, model: ModelClient) -> None:
        self.store = store
        self.model = model

    def voice(self, instruction: str, findings_text: str, fallback: str) -> str:
        """Narrate findings in character. Uses the model when online; the
        deterministic fallback (which is already presentable) when offline."""
        user = (f"{instruction}\n\nSTRUCTURED FINDINGS:\n{findings_text}\n\n"
                "Respond in 1-2 punchy sentences, in character, no preamble.")
        return self.model.narrate(self.system_prompt, user, fallback)

    def remark(self, instruction: str, context: str, fallback: str, kind: str = "info") -> "Turn":
        """A responsive turn in a live debate — quotes/answers the prior speaker
        instead of summarising findings, so the council reads as a real argument."""
        user = (f"{instruction}\n\nDEBATE SO FAR (respond directly to this):\n{context}\n\n"
                "Reply in character, 2-3 sentences, addressing the prior speaker by name. No preamble.")
        headline = self.model.narrate(self.system_prompt, user, fallback)
        return Turn(self.name, self.persona_label, self.color, headline, [], kind=kind)
