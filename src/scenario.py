"""The mission object: a contract/bid that needs N people certified by a deadline."""
from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class Scenario:
    cert_id: str
    required: int
    deadline_weeks: float
    candidate_ids: list[str]
    label: str = ""
    notes: list[str] = field(default_factory=list)
