"""Conductor — the orchestration brain. Opens the mission, and after the council
debates it (1) reconciles optimist vs skeptic vs burnout into one honest verdict
(moderator role) and (2) negotiates contract counter-offers when the verdict
falls short of the GO target."""
from __future__ import annotations
from dataclasses import replace

from .base import BaseAgent, Turn
from .. import config, readiness
from ..scenario import Scenario
from ..skill_graph import SkillGraph
from ..pipeline import evaluate_pool, evaluate_candidate


class ConductorAgent(BaseAgent):
    name = "Dana Whitfield"
    persona_label = "Chief of Staff"
    color = "bright_cyan"
    system_prompt = ("You are Dana Whitfield, the Chief of Staff who chairs a certification-readiness "
                     "review board. Calm, decisive, executive. You keep the room on point, weigh the "
                     "skeptic (Vera) over the optimist (Ben), and make the final call without hedging.")

    # -- open the mission --------------------------------------------------
    def intake(self, scenario: Scenario) -> Turn:
        cert = self.store.cert(scenario.cert_id)
        names = [self.store.learner(c).name for c in scenario.candidate_ids]
        lines = [
            f"Target: {cert.id} — {cert.title} ({cert.level})",
            f"Requirement: certify {scenario.required} of {len(names)} candidates in {scenario.deadline_weeks:.0f} weeks",
            f"Candidates: {', '.join(names)}",
            "Route: Curator → Assessment → Planner ⚔ Skeptic → Burnout → Verifier → reconcile → (negotiate)",
        ]
        fallback = (f"Mission: land {scenario.required} {cert.id} certifications in "
                    f"{scenario.deadline_weeks:.0f} weeks across {len(names)} candidates. "
                    f"Spinning up the council now.")
        headline = self.voice("State the mission and what you'll orchestrate.", "\n".join(lines), fallback)
        return Turn(self.name, self.persona_label, self.color, headline, lines, kind="info")

    # -- reconcile (moderator) --------------------------------------------
    def reconcile(self, scenario, optimist_team, skeptic_team, burnout_veto, integrity) -> Turn:
        opt = optimist_team.prob_meet_requirement
        skep = skeptic_team.prob_meet_requirement
        # Skeptic-weighted blend (honesty over hope); stronger when grounding is clean.
        final = round(skep * 0.65 + opt * 0.35, 4)
        band = ("high confidence" if final >= config.GO_CONFIDENCE_TARGET
                else "moderate confidence" if final >= config.BAND_ON_TRACK else "low confidence")

        if burnout_veto:
            decision = "REVISE — sustainable plan required"
        elif final >= config.GO_CONFIDENCE_TARGET:
            decision = "GO"
        elif final >= config.BAND_ON_TRACK:
            decision = "NEGOTIATE"
        else:
            decision = "NO-GO as scoped"

        lines = [
            f"Optimist {opt:.0%}  vs  Skeptic {skep:.0%}  →  reconciled {final:.0%} ({band})",
            f"Grounding integrity {integrity:.0%}" + ("" if integrity == 1 else " — skeptic weighted up"),
            f"Burnout veto: {'YES' if burnout_veto else 'no'}",
            f"DECISION: {decision} (GO target {config.GO_CONFIDENCE_TARGET:.0%})",
        ]
        fallback = (f"Reconciled confidence is {final:.0%}. "
                    + {"GO": "We can commit as scoped.",
                       "NEGOTIATE": "Short of target — taking it to negotiation.",
                       "NO-GO as scoped": "Not deliverable as scoped — negotiating terms.",
                       "REVISE — sustainable plan required": "Burnout veto stands — we revise before committing."}[decision])
        headline = self.voice("Deliver the reconciled verdict and decision.", "\n".join(lines), fallback)
        return Turn(self.name, self.persona_label, self.color, headline, lines, kind="verdict",
                    data={"final": final, "decision": decision, "band": band})

    # -- negotiate counter-offers -----------------------------------------
    def _skeptic_team(self, scenario: Scenario):
        cert = self.store.cert(scenario.cert_id)
        sg = SkillGraph(self.store)
        fcs = evaluate_pool(self.store, sg, scenario.candidate_ids, cert,
                            scenario.deadline_weeks, "skeptic")
        return readiness.team_forecast(fcs, scenario.required, "skeptic"), fcs

    def negotiate(self, scenario: Scenario, skeptic_forecasts) -> Turn:
        cert = self.store.cert(scenario.cert_id)
        sg = SkillGraph(self.store)
        base_prob = readiness.team_forecast(skeptic_forecasts, scenario.required, "skeptic").prob_meet_requirement
        options: list[tuple[str, float, Scenario]] = []

        # A) Extend the deadline +2 weeks
        s_a = replace(scenario, deadline_weeks=scenario.deadline_weeks + 2)
        options.append(("Extend deadline +2 weeks", self._skeptic_team(s_a)[0].prob_meet_requirement, s_a))

        # B) Add the strongest bench candidate (keep requirement)
        bench = self.store.bench_for(scenario.cert_id, set(scenario.candidate_ids))
        best_bench = None
        if bench:
            ranked = sorted(
                bench,
                key=lambda l: evaluate_candidate(self.store, sg, l, cert, scenario.deadline_weeks, "skeptic").probability,
                reverse=True,
            )
            best_bench = ranked[0]
            s_b = replace(scenario, candidate_ids=scenario.candidate_ids + [best_bench.learner_id])
            options.append((f"Add bench candidate {best_bench.name}",
                            self._skeptic_team(s_b)[0].prob_meet_requirement, s_b))

        # C) Swap weakest selected for strongest bench
        if best_bench:
            weakest = min(skeptic_forecasts, key=lambda f: f.probability)
            new_ids = [i for i in scenario.candidate_ids if i != weakest.learner_id] + [best_bench.learner_id]
            s_c = replace(scenario, candidate_ids=new_ids)
            options.append((f"Swap {weakest.name} → {best_bench.name}",
                            self._skeptic_team(s_c)[0].prob_meet_requirement, s_c))

        # D) Coach the weakest candidate + extend (develop, don't replace)
        weakest = min(skeptic_forecasts, key=lambda f: f.probability)
        wl = self.store.learner(weakest.learner_id)
        if weakest.readiness.weak_domains:
            ext = scenario.deadline_weeks + 3
            ramp = sg.ramp_estimate(cert.id, wl.holds_certifications)
            cap = readiness.assess_capacity(wl.work, float((wl.human or {}).get("life_hit", 0)))
            proj = readiness.project_with_coaching(wl, cert, ramp, cap, weakest.probability, ext)
            others = [evaluate_candidate(self.store, sg, self.store.learner(i), cert, ext, "skeptic").probability
                      for i in scenario.candidate_ids if i != weakest.learner_id]
            coach_prob = readiness.poisson_binomial_at_least(others + [proj.in_deadline_prob], scenario.required)
            s_d = replace(scenario, deadline_weeks=ext)
            options.append((f"Coach {weakest.name} + extend 3 wks (develop in place)", coach_prob, s_d))

        options.sort(key=lambda o: o[1], reverse=True)
        best = options[0]
        target = config.GO_CONFIDENCE_TARGET

        lines = [f"Current (as scoped): {base_prob:.0%}"]
        for label, prob, _ in options:
            hit = "← crosses GO target" if prob >= target else ""
            lines.append(f"• {label}: {prob:.0%} ({prob-base_prob:+.0%}) {hit}")
        rec = (f"Recommend: {best[0]} → {best[1]:.0%}"
               + (" (meets GO target)" if best[1] >= target else " (closest available)"))
        lines.append(rec)

        fallback = (f"As scoped we're at {base_prob:.0%}. Best lever is '{best[0]}', taking us to "
                    f"{best[1]:.0%}. " + ("Counter with that." if best[1] >= target
                    else "Still short of target — combine levers or restaff."))
        headline = self.voice("Present the counter-offer the executive should make.",
                              "\n".join(lines), fallback)
        return Turn(self.name, self.persona_label, self.color, headline, lines, kind="negotiate",
                    data={"options": [(l, p) for l, p, _ in options], "recommendation": best[0],
                          "recommended_prob": best[1]})
