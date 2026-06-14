"""Loads and indexes the synthetic dataset and the grounded knowledge base.

This is the only place that touches disk. Everything downstream reasons over the
objects returned here. The knowledge base doubles as the grounding/citation source
for the Curator, Assessment, and Verifier agents. Retrieval runs against **Foundry IQ**
(real Azure AI Search hybrid vector + keyword) when configured, and transparently
falls back to this local corpus offline — see connectors/foundry_iq.py.
"""
from __future__ import annotations
import json
import re
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Optional

from . import config


# ---------------------------------------------------------------------------
# Domain objects
# ---------------------------------------------------------------------------
@dataclass
class Certification:
    id: str
    title: str
    level: str
    skills: list[str]
    recommended_hours: int
    first_pass_rate: float
    prerequisites: list[str]
    exam_domains: list[dict]  # [{"name", "weight"}]

    @property
    def domain_names(self) -> list[str]:
        return [d["name"] for d in self.exam_domains]


@dataclass
class Learner:
    learner_id: str
    name: str
    role: str
    target_certification: str
    holds_certifications: list[str]
    practice_score_avg: int
    hours_studied: int
    domain_scores: dict[str, int]
    exam_outcome: str
    first_attempt_history: Optional[str]
    work: dict = field(default_factory=dict)   # joined work signal
    human: dict = field(default_factory=dict)  # self-disclosed wellbeing/availability signals
    skills: dict = field(default_factory=dict)  # skill -> proficiency 1-5, matched vs cert.skills
    level: str = "Mid"                          # Principal | Senior | Mid | Associate


@dataclass
class KnowledgeChunk:
    source_id: str
    doc_title: str
    heading: str
    text: str

    @property
    def citation(self) -> str:
        return f"[{self.source_id} · {self.heading}]"


# ---------------------------------------------------------------------------
# Store
# ---------------------------------------------------------------------------
class DataStore:
    def __init__(self) -> None:
        self.certs: dict[str, Certification] = {}
        self.learners: dict[str, Learner] = {}
        self.knowledge: list[KnowledgeChunk] = []
        self.pass_threshold: int = config.PASS_PRACTICE_THRESHOLD
        self.last_grounding_source: str = "local"   # "foundry_iq" (Azure AI Search) | "local"
        self._load()

    # -- loading ----------------------------------------------------------
    def _load(self) -> None:
        certs_raw = json.loads((config.DATA_DIR / "certifications.json").read_text(encoding="utf-8"))
        self.pass_threshold = certs_raw.get("pass_threshold_practice", config.PASS_PRACTICE_THRESHOLD)
        for c in certs_raw["certifications"]:
            self.certs[c["id"]] = Certification(
                id=c["id"], title=c["title"], level=c["level"], skills=c["skills"],
                recommended_hours=c["recommended_hours"], first_pass_rate=c["first_pass_rate"],
                prerequisites=c["prerequisites"], exam_domains=c["exam_domains"],
            )

        # Work IQ signals come through a swappable connector (synthetic by default;
        # set WORK_IQ_SOURCE=graph to derive them live from Outlook via Microsoft Graph).
        from .connectors.graph_calendar import get_calendar_connector
        self.work_connector = get_calendar_connector()
        signal_by_learner = self.work_connector.fetch_all()

        learners_raw = json.loads((config.DATA_DIR / "learners.json").read_text(encoding="utf-8"))["learners"]
        for l in learners_raw:
            self.learners[l["learner_id"]] = Learner(
                learner_id=l["learner_id"], name=l["name"], role=l["role"],
                target_certification=l["target_certification"],
                holds_certifications=l.get("holds_certifications", []),
                practice_score_avg=l["practice_score_avg"], hours_studied=l["hours_studied"],
                domain_scores=l.get("domain_scores", {}), exam_outcome=l.get("exam_outcome", "Untested"),
                first_attempt_history=l.get("first_attempt_history"),
                work=signal_by_learner.get(l["learner_id"], {}),
                human=l.get("human", {}),
                skills=l.get("skills", {}),
                level=l.get("level", "Mid"),
            )

        self._load_knowledge()

    def _load_knowledge(self) -> None:
        """Split each markdown doc into heading-scoped chunks for citation."""
        for path in sorted(config.KNOWLEDGE_DIR.glob("*.md")):
            raw = path.read_text(encoding="utf-8")
            source_id = "UNKNOWN"
            m = re.search(r"Source ID:\s*([A-Z0-9\-]+)", raw)
            if m:
                source_id = m.group(1)
            title_m = re.search(r"^#\s+(.*)$", raw, re.MULTILINE)
            doc_title = title_m.group(1).strip() if title_m else path.stem

            # chunk on ## / ### headings
            parts = re.split(r"\n(?=#{2,3}\s)", raw)
            for part in parts:
                hm = re.match(r"#{2,3}\s+(.*)", part.strip())
                heading = hm.group(1).strip() if hm else "Overview"
                text = part.strip()
                if len(text) > 20:
                    self.knowledge.append(KnowledgeChunk(source_id, doc_title, heading, text))

    # -- lookups ----------------------------------------------------------
    def cert(self, cert_id: str) -> Certification:
        return self.certs[cert_id]

    def learner(self, learner_id: str) -> Learner:
        return self.learners[learner_id]

    def candidates_for(self, cert_id: str) -> list[Learner]:
        return [l for l in self.learners.values() if l.target_certification == cert_id]

    def bench_for(self, cert_id: str, exclude: set[str]) -> list[Learner]:
        """Other trainable candidates: anyone not already selected who does not
        already hold the target certification."""
        out = []
        for l in self.learners.values():
            if l.learner_id in exclude:
                continue
            if cert_id in l.holds_certifications:
                continue
            out.append(l)
        return out

    def search_knowledge(self, *terms: str, limit: int = 3) -> list[KnowledgeChunk]:
        """Grounded retrieval. Prefers **Foundry IQ** (real Azure AI Search hybrid
        vector + keyword retrieval); transparently falls back to the local keyword
        corpus when Search is unconfigured or unavailable, so the offline demo never
        breaks. Either way it returns the same KnowledgeChunk shape."""
        terms = tuple(t for t in terms if t)
        try:
            from .connectors import foundry_iq
            if foundry_iq.is_configured():
                hits = foundry_iq.retrieve(" ".join(terms), limit=limit)
                if hits:
                    self.last_grounding_source = "foundry_iq"
                    return [KnowledgeChunk(h["source_id"], h["doc_title"], h["heading"], h["text"]) for h in hits]
        except Exception:
            pass  # any failure → local fallback below

        self.last_grounding_source = "local"
        terms_l = [t.lower() for t in terms]
        scored: list[tuple[int, KnowledgeChunk]] = []
        for chunk in self.knowledge:
            hay = (chunk.heading + " " + chunk.text).lower()
            score = sum(hay.count(t) for t in terms_l)
            if score:
                scored.append((score, chunk))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [c for _, c in scored[:limit]]

    def citation_exists(self, source_id: str) -> bool:
        return any(c.source_id == source_id for c in self.knowledge)


@lru_cache(maxsize=1)
def get_store() -> DataStore:
    return DataStore()
