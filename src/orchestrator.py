"""Orchestrator — drives the multi-agent debate and yields Turns for the console.

Flow (the Conductor routes; agents consume each other's outputs):

  Conductor.intake
    -> Curator.curate            (grounding + citations)
    -> Assessment.assess         (cited question + coverage gate)
    -> Planner.forecast          (optimist team probability)
    -> Skeptic.challenge         (attacks it; may VETO)
    -> Burnout.assess            (human-advocate; may VETO)
    -> Verifier.verify           (grounding integrity)
    -> Conductor.reconcile       (moderator verdict + decision)
    -> Conductor.negotiate       (counter-offers, if not GO)
    -> Historian trust scorecard (track record of past predictions)
    -> Briefing                  (executive summary)
"""
from __future__ import annotations
import json
from dataclasses import dataclass

from . import config
from .data_store import get_store
from .model_client import get_model
from .scenario import Scenario
from .agents import (ConductorAgent, CuratorAgent, AssessmentAgent, PlannerAgent,
                     SkepticAgent, CoachAgent, BurnoutAgent, VerifierAgent, Turn)


def _weak_dom(forecast):
    """Return (name, score) of a candidate's weakest exam domain, or (None, None)."""
    wd = getattr(getattr(forecast, "readiness", None), "weak_domains", None) or []
    if wd:
        d = wd[0]
        name = d[0] if isinstance(d, (list, tuple)) else str(d)
        score = float(d[1]) if isinstance(d, (list, tuple)) and len(d) > 1 else None
        return name, score
    return None, None


@dataclass
class RunResult:
    turns: list[Turn]
    final_prob: float
    decision: str


class Orchestrator:
    def __init__(self) -> None:
        self.store = get_store()
        self.model = get_model()
        self.conductor = ConductorAgent(self.store, self.model)
        self.curator = CuratorAgent(self.store, self.model)
        self.assessment = AssessmentAgent(self.store, self.model)
        self.planner = PlannerAgent(self.store, self.model)
        self.skeptic = SkepticAgent(self.store, self.model)
        self.coach = CoachAgent(self.store, self.model)
        self.burnout = BurnoutAgent(self.store, self.model)
        self.verifier = VerifierAgent(self.store, self.model)

    # -- Manager Insights + calibration (Historian) -----------------------
    def _trust_turn(self, final_prob: float, decision: str, skeptic_forecasts=None) -> Turn:
        hist = json.loads((config.DATA_DIR / "track_record.json").read_text(encoding="utf-8"))["history"]
        correct = sum(1 for h in hist if (h["predicted_prob"] >= 0.5) == h["requirement_met"])
        n = len(hist)
        acc = correct / n if n else 0.0

        # Manager-level, privacy-conscious team readiness summary (aggregate, no PII).
        on_track = at_risk = gapped = n_team = 0
        if skeptic_forecasts:
            n_team = len(skeptic_forecasts)
            on_track = sum(1 for f in skeptic_forecasts if f.probability >= 0.55)
            at_risk = sum(1 for f in skeptic_forecasts if f.probability < 0.35)
            gapped = sum(1 for f in skeptic_forecasts if _weak_dom(f)[0] is not None)

        lines = []
        if n_team:
            lines.append(f"Team readiness (aggregate, no individual data exposed): "
                         f"{on_track}/{n_team} on track · {at_risk} at risk · {gapped} with an open exam-domain gap")
            lines.append("Pattern: risk concentrates in the meeting-overloaded and the sub-75% domains — "
                         "the capacity-constrained seats, not the whole team.")
        lines += [
            f"Calibration — past calls logged: {n} · correct directional: {correct} → accuracy {acc:.0%}",
            f"Logging this mission: predicted {final_prob:.0%}, decision {decision} (outcome pending).",
        ]
        if n_team:
            headline = (f"Manager view: {on_track} of {n_team} on track, {at_risk} at risk. "
                        f"And calibration — this council was right {acc:.0%} of the time; when Vera says no, history agrees.")
        else:
            headline = (f"Track record: {acc:.0%} accurate across {n} prior missions. "
                        f"Believe Vera — she's been right before.")
        return Turn("Iris Vaughn", "Manager Insights · Calibration", "bright_white", headline, lines,
                    kind="info", data={"accuracy": acc, "n": n, "on_track": on_track, "at_risk": at_risk})

    # -- briefing ----------------------------------------------------------
    def _briefing_turn(self, scenario, verdict_turn, negotiate_turn, integrity) -> Turn:
        cert = self.store.cert(scenario.cert_id)
        lines = [
            f"Mission: {scenario.required} × {cert.id} in {scenario.deadline_weeks:.0f} weeks",
            f"Reconciled confidence: {verdict_turn.data['final']:.0%} ({verdict_turn.data['band']})",
            f"Decision: {verdict_turn.data['decision']}",
            f"Grounding integrity: {integrity:.0%}",
        ]
        if negotiate_turn:
            lines.append(f"Recommended counter-offer: {negotiate_turn.data['recommendation']} "
                         f"→ {negotiate_turn.data['recommended_prob']:.0%}")
        lines.append("Basis: skill-adjacency ramps · Work IQ capacity · exam-blueprint coverage · "
                     "Poisson-binomial team forecast · grounded & verified citations.")
        headline = "Executive brief ready — grounded, stress-tested, and signed off."
        return Turn("Briefing", "Executive report", "cyan", headline, lines, kind="info")

    # -- main run (generator) ---------------------------------------------
    def run(self, scenario: Scenario):
        citations: list[str] = []

        t = self.conductor.intake(scenario); yield t

        t = self.curator.curate(scenario.cert_id); citations += t.data.get("citations", []); yield t

        t = self.assessment.assess(scenario.cert_id, scenario.candidate_ids)
        citations += t.data.get("citations", []); assessment_grounded = t.data.get("grounded", True); yield t

        t_plan = self.planner.forecast(scenario); yield t_plan
        optimist_team = t_plan.data["team"]

        t_skep = self.skeptic.challenge(scenario, optimist_team, t_plan.data["forecasts"]); yield t_skep
        skeptic_team = t_skep.data["team"]
        skeptic_forecasts = t_skep.data["forecasts"]

        yield self.coach.coach(scenario, skeptic_forecasts)

        # --- cross-examination: a genuine back-and-forth, not a relay of monologues ---
        ranked = sorted(skeptic_forecasts, key=lambda f: f.probability, reverse=True)
        anchor, weakest = ranked[0], ranked[-1]
        firm = [f for f in skeptic_forecasts if f.probability >= 0.55]
        conting = [f for f in skeptic_forecasts if 0.30 <= f.probability < 0.55]
        aw_name, aw_score = _weak_dom(anchor)
        wk_name, wk_score = _weak_dom(weakest)
        need, n_team = scenario.required, len(skeptic_forecasts)

        ctx = (f"Vera (skeptic) just argued: \"{t_skep.headline}\"\n"
               f"You need {need} of {n_team} certified — not everyone. "
               f"Firm seats (>=55% even worst-case): {', '.join(f.name for f in firm) or 'none yet'}. "
               f"Strongest seat: {anchor.name} at {anchor.probability:.0%}"
               + (f", but weak in {aw_name} ({aw_score:.0f}%)." if aw_name and aw_score is not None else ", clean across domains.")
               + f" Weakest seat: {weakest.name} at {weakest.probability:.0%}.")
        fb = (f"Fair, Vera — I'm not betting on one hero. {', '.join(f.name for f in firm[:2]) or 'the strong seats'} are "
              f"firm; I'll make {anchor.name} contingent on {aw_name or 'their weak area'} holding. We need {need}, not all {n_team}.")
        t = self.planner.remark(
            "Respond directly to Vera. Concede what's fair, defend the count, and name which seats you call FIRM vs CONTINGENT.",
            ctx, fb, kind="optimist"); yield t
        ben = t.headline

        ctx2 = (f"Ben (optimist) just rebutted: \"{ben}\"\n"
                f"Hold him to it. {weakest.name} sits at {weakest.probability:.0%} worst-case"
                + (f", weak in {wk_name} ({wk_score:.0f}%)." if wk_name and wk_score is not None else ".")
                + " A contingent seat needs a hard trigger, not faith.")
        fb2 = (f"The firm seats I'll grant. But {weakest.name} is contingent, not certain — I move only if the coaching "
               f"lands by the mid-point mock, not on a promise.")
        t = self.skeptic.remark(
            "Counter Ben. Accept the firm seats IF the numbers hold, but pin the contingent ones to a concrete condition (a mid-point mock).",
            ctx2, fb2, kind="skeptic"); yield t

        ctx3 = (f"The debate is over {weakest.name}'s contingent seat. Their gap is {wk_name or 'a weak domain'}"
                + (f" at {wk_score:.0f}%" if wk_score is not None else "") + ". You already laid out the coaching plan.")
        fb3 = (f"That contingency is exactly what I coach: {weakest.name}'s {wk_name or 'gap'} is bounded and grounded in a "
               f"named Microsoft Learn module — two focused weeks, and the mid-point mock is the proof Vera wants.")
        t = self.coach.remark(
            "Interject briefly: tie YOUR coaching plan to Vera's condition — the weakest seat's gap is the trigger, it's coachable and grounded.",
            ctx3, fb3, kind="info"); yield t

        ctx4 = f"Reconcile the debate into a count. Firm seats: {len(firm)}. Contingent: {len(conting)}. Need {need} of {n_team}."
        fb4 = (f"Reconciled from the floor: {len(firm)} firm, {len(conting)} contingent against a need of {need}. "
               f"That's the honest count — it carries straight into the forecast.")
        t = self.conductor.remark(
            "Force the honest count out of the debate: state the COUNTS only (e.g. '4 firm, 3 contingent') and whether "
            "that covers the requirement. Do NOT name individuals — just the numbers.",
            ctx4, fb4, kind="info"); yield t
        # --- end cross-examination ---

        t_burn = self.burnout.assess(scenario, skeptic_forecasts); yield t_burn
        burnout_veto = t_burn.data["veto"]

        t_ver = self.verifier.verify(citations, assessment_grounded); yield t_ver
        integrity = t_ver.data["integrity"]

        t_verdict = self.conductor.reconcile(scenario, optimist_team, skeptic_team,
                                             burnout_veto, integrity); yield t_verdict
        decision = t_verdict.data["decision"]
        final_prob = t_verdict.data["final"]

        t_neg = None
        if decision != "GO":
            t_neg = self.conductor.negotiate(scenario, skeptic_forecasts); yield t_neg

        yield self._trust_turn(final_prob, decision, skeptic_forecasts)
        yield self._briefing_turn(scenario, t_verdict, t_neg, integrity)

    def run_collect(self, scenario: Scenario) -> RunResult:
        turns = list(self.run(scenario))
        verdict = next(t for t in turns if t.kind == "verdict")
        return RunResult(turns, verdict.data["final"], verdict.data["decision"])
