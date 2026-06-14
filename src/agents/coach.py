"""Enablement Coach — the constructive counterpart to the Skeptic. Instead of only
saying who won't make it, it says HOW to lift them: which weak exam domains to close,
which approved/Microsoft Learn sources to study, and the projected score uplift. It
also recommends new sources to ingest into the knowledge base to strengthen grounding.
"""
from __future__ import annotations

from .base import BaseAgent, Turn
from ..skill_graph import SkillGraph
from .. import readiness


class CoachAgent(BaseAgent):
    name = "Sam Ellison"
    persona_label = "L&D Coach"
    color = "cyan"
    system_prompt = ("You are Sam Ellison, the Learning & Development Coach. Warm, practical, and "
                     "encouraging — you see potential, not write-offs. You turn weak readiness into a "
                     "concrete plan: the exact domains to lift, the best approved sources to study, "
                     "and the projected gain. You're realistic about the study time it takes.")

    # Domain -> recommended grounded study sources (synthetic + Microsoft Learn references).
    RESOURCES = {
        "API Development": [("MS Learn: Manage APIs with Azure API Management",
                             "learn.microsoft.com/training/modules/publish-manage-apis-azure-api-management")],
        "Azure Functions": [("MS Learn: Create serverless logic with Azure Functions",
                             "learn.microsoft.com/training/paths/create-serverless-applications"),
                            ("KB-ENABLE-001 · Azure Functions (triggers vs bindings)", "internal")],
        "Storage": [("MS Learn: Store data in Azure Blob Storage",
                     "learn.microsoft.com/training/paths/store-data-in-azure")],
        "Security": [("MS Learn: Implement managed identities",
                      "learn.microsoft.com/training/modules/implement-managed-identities")],
        "CI/CD": [("MS Learn: Build applications with Azure DevOps",
                   "learn.microsoft.com/training/paths/build-applications-with-azure-devops")],
        "Monitoring": [("MS Learn: Monitor app performance",
                        "learn.microsoft.com/training/modules/monitor-app-performance")],
        "Data Processing": [("MS Learn: Data engineering with Azure Synapse",
                             "learn.microsoft.com/training/paths/data-engineering-azure-synapse")],
    }

    def _sources(self, domain: str) -> list[tuple[str, str]]:
        return self.RESOURCES.get(domain, [(f"MS Learn: search '{domain}' learning path",
                                            "learn.microsoft.com")])

    def coach(self, scenario, skeptic_forecasts: list[readiness.CandidateForecast]) -> Turn:
        cert = self.store.cert(scenario.cert_id)
        sg = SkillGraph(self.store)
        projections, lines, ground_sources = [], [], set()

        weak_fcs = [f for f in skeptic_forecasts if f.readiness.weak_domains]
        for f in weak_fcs:
            learner = self.store.learner(f.learner_id)
            ramp = sg.ramp_estimate(cert.id, learner.holds_certifications)
            cap = readiness.assess_capacity(learner.work, float((learner.human or {}).get("life_hit", 0)))
            proj = readiness.project_with_coaching(learner, cert, ramp, cap, f.probability,
                                                   scenario.deadline_weeks)
            projections.append(proj)

            domains = ", ".join(n for n, _, _ in proj.gaps)
            lines.append(f"{f.name}: lift {domains} → ceiling {proj.ceiling_prob:.0%} "
                         f"(now {proj.current_prob:.0%}); ~{proj.in_deadline_prob:.0%} within "
                         f"{scenario.deadline_weeks:.0f} wks — needs ~{proj.weeks_to_close:.1f} wks focused study")
            for n, _, _ in proj.gaps:
                for title, url in self._sources(n):
                    lines.append(f"   study [{n}]: {title}")
                    if url != "internal":
                        ground_sources.add(title)

        if ground_sources:
            lines.append("ground these in Foundry IQ to harden assessment: "
                         + "; ".join(sorted(ground_sources)[:3]))
        if not weak_fcs:
            lines.append("No coverage gaps — every candidate clears all exam domains. No coaching needed.")

        top = max(projections, key=lambda p: p.ceiling_prob - p.current_prob, default=None)
        if top:
            fallback = (f"Biggest upside is {top.name}: close {len(top.gaps)} weak domain(s) and the "
                        f"competence ceiling rises to {top.ceiling_prob:.0%} (from {top.current_prob:.0%}) — "
                        f"but it needs ~{top.weeks_to_close:.1f} weeks of study, so pair it with time.")
        else:
            fallback = "The roster already clears every exam domain — no enablement gaps to close."
        headline = self.voice("Give the enablement plan: who to coach, on what, and the projected lift.",
                              "\n".join(lines), fallback)
        return Turn(self.name, self.persona_label, self.color, headline, lines, kind="info",
                    data={"projections": projections})
