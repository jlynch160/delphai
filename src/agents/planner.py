"""Forecast Planner — the optimist. Builds the best-case staffing plan and the
team probability of hitting the deadline, surfacing skill-adjacency ramp savings."""
from __future__ import annotations

from .base import BaseAgent, Turn
from ..skill_graph import SkillGraph
from ..pipeline import evaluate_pool
from .. import readiness


class PlannerAgent(BaseAgent):
    name = "Ben Russo"
    persona_label = "Head of Delivery"
    color = "yellow"
    system_prompt = ("You are Ben Russo, the Head of Delivery and the board's optimist. Upbeat, "
                     "ambitious, can-do. You build the best-case plan and make the confident case "
                     "that the team can hit the deadline — but you always cite your numbers.")

    def forecast(self, scenario) -> Turn:
        cert = self.store.cert(scenario.cert_id)
        sg = SkillGraph(self.store)
        fcs = evaluate_pool(self.store, sg, scenario.candidate_ids, cert,
                            scenario.deadline_weeks, "optimist")
        team = readiness.team_forecast(fcs, scenario.required, "optimist")

        lines = []
        for f in fcs:
            ramp = f.ramp
            disc = f" (ramp −{ramp.discount:.0%} via {ramp.nearest_held or 'prerequisite credit'})" if ramp.discount else ""
            lines.append(
                f"{f.name}: {f.probability:.0%} on-time · needs {f.hours_needed:.0f}h "
                f"≈ {f.weeks_needed:.1f} wks, buffer {f.buffer_weeks:+.1f}{disc}"
            )
        lines.append(f"Expected certified ≈ {team.expected_certified:.1f} of {len(fcs)}")
        lines.append(f"P(≥{scenario.required} certified by deadline) = "
                     f"{team.prob_meet_requirement:.0%}  [Poisson-binomial]")

        fallback = (f"Best case: I have us at {team.prob_meet_requirement:.0%} to land "
                    f"{scenario.required} certifications — adjacency savings shorten several ramps "
                    f"and the buffers hold. I say we commit.")
        headline = self.voice("Make the optimistic case for hitting the deadline.",
                              "\n".join(lines), fallback)
        return Turn(self.name, self.persona_label, self.color, headline, lines, kind="optimist",
                    data={"team": team, "forecasts": fcs})
