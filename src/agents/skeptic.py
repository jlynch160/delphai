"""Red-Team Skeptic — the dissent engine. Attacks the optimistic forecast with
grounded objections (first-pass rates, coverage gaps, capacity haircut, retest risk),
and VETOES specific over-optimistic "ready" calls. This is the system's catch:
the AI that says no — and keeps a track record of how often it was right."""
from __future__ import annotations

from .base import BaseAgent, Turn
from ..skill_graph import SkillGraph
from ..pipeline import evaluate_pool
from .. import readiness


class SkepticAgent(BaseAgent):
    name = "Vera Lindqvist"
    persona_label = "Red-Team Lead"
    color = "bright_red"
    system_prompt = ("You are Vera Lindqvist, the Red-Team Lead — blunt, dry, and contrarian, the one "
                     "who says no. Your job is to REFUTE optimistic delivery forecasts. You default to "
                     "doubt when the data is thin and you cite first-pass rates and weak domains. "
                     "You'd rather be the unwelcome truth than a comfortable guess.")

    def challenge(self, scenario, optimist_team: readiness.TeamForecast,
                  optimist_forecasts: list[readiness.CandidateForecast]) -> Turn:
        cert = self.store.cert(scenario.cert_id)
        sg = SkillGraph(self.store)
        fcs = evaluate_pool(self.store, sg, scenario.candidate_ids, cert,
                            scenario.deadline_weeks, "skeptic")
        team = readiness.team_forecast(fcs, scenario.required, "skeptic")
        opt_by_id = {f.learner_id: f.probability for f in optimist_forecasts}

        # Per-candidate VETO: optimist counts on them, the grounded numbers don't.
        vetoes = [f for f in fcs if opt_by_id.get(f.learner_id, 0.0) >= 0.50 and f.probability < 0.25]

        drop = team.prob_meet_requirement - optimist_team.prob_meet_requirement  # negative
        lines = []
        for f in fcs:
            opt = opt_by_id.get(f.learner_id, 0.0)
            lines.append(f"{f.name}: {f.probability:.0%} on-time (optimist said {opt:.0%}) — {f.reasons[-1]}")
        lines.append(f"Realistic P(≥{scenario.required} certified) = {team.prob_meet_requirement:.0%} "
                     f"— {drop:+.0%} vs the optimist's {optimist_team.prob_meet_requirement:.0%}")

        objections = []
        for f in fcs:
            if f.buffer_weeks < 0:
                objections.append(f"{f.name}: {-f.buffer_weeks:.1f} wks SHORT at realistic capacity")
            if f.readiness.weak_domains:
                objections.append(f"{f.name}: {len(f.readiness.weak_domains)} unmet exam domain(s)")
        objections.append(f"{cert.id} first-pass rate only {cert.first_pass_rate:.0%} — retests eat the buffer")
        lines += [f"objection: {o}" for o in objections[:4]]

        for f in vetoes:
            lines.append(f"⛔ VETO on {f.name}: optimist's {opt_by_id[f.learner_id]:.0%} is not supported "
                         f"by the numbers — realistic {f.probability:.0%}.")

        veto_names = ", ".join(f.name for f in vetoes)
        fallback = (f"Not so fast — at realistic capacity and a {cert.first_pass_rate:.0%} first-pass "
                    f"rate I have us at {team.prob_meet_requirement:.0%}, not "
                    f"{optimist_team.prob_meet_requirement:.0%}."
                    + (f" I'm vetoing the call on {veto_names}." if vetoes else ""))
        headline = self.voice("Refute the optimist; name who you're vetoing and why.",
                              "\n".join(lines), fallback)
        return Turn(self.name, self.persona_label, self.color, headline, lines, kind="skeptic",
                    data={"team": team, "forecasts": fcs, "veto": bool(vetoes),
                          "veto_ids": [f.learner_id for f in vetoes], "objections": objections})
