"""Burnout Agent — the human advocate and third voice in the council. Flags plans
that exceed sustainable weekly capacity and can VETO for human reasons, on a
*different* basis than the skeptic (not 'will it fail?' but 'will it break people?').

Responsible-AI boundary: reasons ONLY about observable workload signals
(hours, meeting load, capacity). It does not assess health or wellbeing of a person.
"""
from __future__ import annotations

from .base import BaseAgent, Turn
from .. import readiness


class BurnoutAgent(BaseAgent):
    name = "Maya Devlin"
    persona_label = "Wellbeing Advocate"
    color = "magenta"
    system_prompt = ("You are Maya Devlin, the People & Wellbeing Advocate — empathetic but firm. You "
                     "protect people from unsustainable study load and you WILL say no to leadership "
                     "for ethical reasons. You reason only about workload, capacity, and self-disclosed "
                     "availability — never personal health — and you push for accommodations.")

    def assess(self, scenario, skeptic_forecasts: list[readiness.CandidateForecast]) -> Turn:
        assessments = []
        for f in skeptic_forecasts:
            work = self.store.learner(f.learner_id).work
            assessments.append(readiness.assess_burnout(f, work, scenario.deadline_weeks))

        veto = any(a.risk == "veto" for a in assessments)
        at_risk = [a for a in assessments if a.risk in ("high", "veto")]

        icon = {"ok": "🟢", "watch": "🟡", "high": "🟠", "veto": "⛔"}
        lines = []
        for a in assessments:
            lines.append(f"{icon[a.risk]} {a.name}: needs {a.weekly_study_required:.1f}h/wk = "
                         f"{a.load_ratio:.0%} of capacity — {a.flags[0]}")
        if veto:
            names = ", ".join(a.name for a in assessments if a.risk == "veto")
            lines.append(f"⛔ VETO: plan is infeasible/unsustainable for {names}. Extend or redistribute.")

        # Human factors — self-disclosed wellbeing signals (accommodate, never rank).
        human_lines = []
        for f in skeptic_forecasts:
            h = self.store.learner(f.learner_id).human or {}
            bits = []
            if h.get("life", "none") != "none":
                bits.append(h["life"])
            if h.get("anxiety", "none") != "none":
                bits.append(f"{h['anxiety']} test anxiety")
            if bits:
                human_lines.append(f"{f.name.split()[0]}: {' · '.join(bits)} → accommodate")
        if human_lines:
            lines.append("Human factors (accommodate, not rank): " + "  |  ".join(human_lines))

        fallback = (f"{len(at_risk)} of {len(assessments)} candidates are pushed past sustainable load. "
                    + ("I'm vetoing this plan — it will burn people out. "
                       if veto else "Watch the flagged candidates closely. ")
                    + "Extend the timeline or redistribute before committing.")
        headline = self.voice("Give your human-advocate verdict on plan sustainability.",
                              "\n".join(lines), fallback)
        return Turn(self.name, self.persona_label, self.color, headline, lines, kind="burnout",
                    data={"assessments": assessments, "veto": veto})
