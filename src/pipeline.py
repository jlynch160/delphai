"""Per-candidate evaluation pipeline shared by the Planner, Skeptic and Negotiation.

Chains: skill-adjacency ramp -> Work IQ capacity -> readiness/coverage -> forecast.
Keeping it in one place guarantees the optimist, skeptic, and negotiation all reason
over the *same* underlying math (only the perspective differs).
"""
from __future__ import annotations

from .data_store import DataStore, Learner, Certification
from .skill_graph import SkillGraph
from . import readiness


def evaluate_candidate(store: DataStore, skillgraph: SkillGraph, learner: Learner,
                       cert: Certification, deadline_weeks: float,
                       perspective: str) -> readiness.CandidateForecast:
    ramp = skillgraph.ramp_estimate(cert.id, learner.holds_certifications)
    cap = readiness.assess_capacity(learner.work, float((learner.human or {}).get("life_hit", 0)))
    rd = readiness.assess_readiness(learner, cert)
    return readiness.forecast_candidate(learner, cert, ramp, cap, rd, deadline_weeks, perspective)


def evaluate_pool(store: DataStore, skillgraph: SkillGraph, learner_ids: list[str],
                  cert: Certification, deadline_weeks: float,
                  perspective: str) -> list[readiness.CandidateForecast]:
    return [evaluate_candidate(store, skillgraph, store.learner(lid), cert, deadline_weeks, perspective)
            for lid in learner_ids]
