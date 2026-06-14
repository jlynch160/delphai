"""Skill-adjacency reasoning (the Fabric IQ ontology layer).

Models certifications as a graph of shared skills + prerequisite edges, then reasons
that a learner already holding an adjacent/prerequisite cert ramps *faster* — so the
forecast is smarter than a flat lookup table.
"""
from __future__ import annotations
from dataclasses import dataclass

from .data_store import DataStore, Certification


@dataclass
class RampEstimate:
    base_hours: int
    adjusted_hours: float
    discount: float                 # 0..1 fraction shaved off
    reasons: list[str]
    nearest_held: str | None        # the held cert that helped most


def _jaccard(a: list[str], b: list[str]) -> float:
    sa, sb = set(a), set(b)
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


class SkillGraph:
    def __init__(self, store: DataStore) -> None:
        self.store = store

    def adjacency(self, cert_a: str, cert_b: str) -> float:
        """Skill-overlap similarity between two certifications (0..1)."""
        ca, cb = self.store.cert(cert_a), self.store.cert(cert_b)
        return round(_jaccard(ca.skills, cb.skills), 3)

    def shared_skills(self, cert_a: str, cert_b: str) -> list[str]:
        ca, cb = self.store.cert(cert_a), self.store.cert(cert_b)
        return sorted(set(ca.skills) & set(cb.skills))

    def ramp_estimate(self, target_cert: str, held_certs: list[str]) -> RampEstimate:
        """How many study hours this person realistically needs, discounted by
        adjacency to certs they already hold. Caps the total discount at 40%."""
        cert: Certification = self.store.cert(target_cert)
        base = cert.recommended_hours
        reasons: list[str] = []
        discount = 0.0
        nearest_held = None
        best_sim = 0.0

        held = [h for h in held_certs if h in self.store.certs]

        # Prerequisite credit: foundation already built.
        for pre in cert.prerequisites:
            if pre in held:
                discount += 0.15
                reasons.append(f"holds prerequisite {pre} (+15% foundation credit)")

        # Adjacency credit: shared skills shorten the ramp.
        for h in held:
            sim = _jaccard(cert.skills, self.store.cert(h).skills)
            if sim > best_sim:
                best_sim = sim
                nearest_held = h
            if sim > 0:
                shared = self.shared_skills(target_cert, h)
                credit = round(min(0.25, sim * 0.5), 3)
                if credit >= 0.02:
                    discount += credit
                    reasons.append(
                        f"shares {', '.join(shared)} with {h} "
                        f"(sim {sim:.2f} → -{credit*100:.0f}%)"
                    )

        discount = min(0.40, round(discount, 3))
        adjusted = round(base * (1 - discount), 1)
        if not reasons:
            reasons.append("no adjacent or prerequisite certs held — full ramp")
        return RampEstimate(base, adjusted, discount, reasons, nearest_held)
