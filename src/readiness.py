"""Deterministic reasoning core — the defensible math behind every agent claim.

Nothing here is hallucinated. The optimist and skeptic agents narrate these numbers;
they do not invent them. Every coefficient traces to a synthetic knowledge doc.

Contents:
  * capacity model        -> realistic weekly study budget from Work IQ signals
  * pass-probability model -> validated to reproduce the synthetic exam outcomes
  * exam-blueprint coverage gate
  * optimist / skeptic per-candidate forecasts (genuinely different assumptions)
  * Poisson-binomial team forecast -> P(at least N certified by the deadline)
  * burnout / sustainability assessment
"""
from __future__ import annotations
import math
from dataclasses import dataclass, field, replace

from . import config
from .data_store import Learner, Certification
from .skill_graph import RampEstimate


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


# ---------------------------------------------------------------------------
# Capacity  (Work IQ layer)
# ---------------------------------------------------------------------------
@dataclass
class CapacityAssessment:
    weekly_capacity_hours: float
    meeting_overloaded: bool
    notes: list[str]


# Test-anxiety lowers exam-day performance (applied to pass-probability in the forecast).
ANXIETY = {"none": {"optimist": 1.0, "skeptic": 1.0},
           "moderate": {"optimist": 0.98, "skeptic": 0.93},
           "high": {"optimist": 0.95, "skeptic": 0.85}}


def assess_capacity(work: dict, life_hit: float = 0.0) -> CapacityAssessment:
    focus = max(2.0, float(work.get("focus_hours_per_week", 10)) - life_hit)
    meetings = float(work.get("meeting_hours_per_week", 15))
    cap = focus * config.FOCUS_TO_STUDY_RATIO
    notes = [f"{focus:.0f} effective focus hrs × {config.FOCUS_TO_STUDY_RATIO:.0%} = {cap:.1f} hrs base [KB-WORKLOAD-003]"]
    if life_hit:
        notes.append(f"life factor: −{life_hit:.0f} focus hrs/wk")
    overloaded = meetings > config.HIGH_MEETING_LOAD
    if overloaded:
        cap *= config.HIGH_MEETING_PENALTY
        notes.append(f"meeting load {meetings:.0f}h > {config.HIGH_MEETING_LOAD}h → ×{config.HIGH_MEETING_PENALTY} penalty → {cap:.1f} hrs")
    return CapacityAssessment(round(cap, 2), overloaded, notes)


# ---------------------------------------------------------------------------
# Pass-probability + coverage  (validated against synthetic outcomes)
# ---------------------------------------------------------------------------
@dataclass
class ReadinessAssessment:
    pass_probability: float
    band: str
    practice_factor: float
    hours_factor: float
    synergy: float
    coverage_penalty: float
    weak_domains: list[tuple[str, float, float]]  # (name, score, weight)
    rationale: list[str]


def _band(p: float) -> str:
    if p >= config.BAND_EXAM_READY:
        return "Exam Ready"
    if p >= config.BAND_ON_TRACK:
        return "On Track"
    return "Not Ready"


def coverage_gaps(learner: Learner, cert: Certification) -> list[tuple[str, float, float]]:
    """Per-exam-domain weak spots. Missing domain score falls back to the average."""
    gaps = []
    for d in cert.exam_domains:
        score = learner.domain_scores.get(d["name"], learner.practice_score_avg)
        if score < config.PASS_PRACTICE_THRESHOLD:
            gaps.append((d["name"], float(score), float(d["weight"])))
    return gaps


PROFICIENT = 3   # 1-5 scale; >=3 = job-ready on that skill


def skill_match(learner: Learner, cert: Certification) -> dict:
    """How many of the cert's required skills the learner is proficient (>=3/5) in."""
    sk = learner.skills or {}
    need = cert.skills or []
    profs = [sk.get(s, 0) for s in need]
    proficient = sum(1 for v in profs if v >= PROFICIENT)
    avg = (sum(profs) / len(need)) if need else 0.0
    missing = [s for s in need if sk.get(s, 0) < PROFICIENT]
    return {"has": proficient, "total": len(need),
            "frac": (proficient / len(need)) if need else 1.0,
            "avg": round(avg, 1), "missing": missing}


def assess_readiness(learner: Learner, cert: Certification) -> ReadinessAssessment:
    practice_factor = (learner.practice_score_avg - config.PASS_PRACTICE_THRESHOLD) / 25.0
    hours_factor = _clamp((learner.hours_studied - cert.recommended_hours) / cert.recommended_hours, -1.0, 1.0)
    synergy = 0.12 if (learner.practice_score_avg > config.PASS_PRACTICE_THRESHOLD
                       and learner.hours_studied > config.STRONG_HOURS_THRESHOLD) else 0.0

    gaps = coverage_gaps(learner, cert)
    weighted_below = sum(w for _, _, w in gaps)
    coverage_penalty = 0.10 * weighted_below

    sm = skill_match(learner, cert)
    skill_term = 0.12 * (sm["frac"] - 0.5)   # already-has-the-skills signal

    score = (cert.first_pass_rate
             + 0.40 * practice_factor
             + 0.12 * hours_factor
             + synergy
             - coverage_penalty
             + skill_term)
    score = _clamp(score, 0.03, 0.97)

    rationale = [
        f"base first-pass rate for {cert.id} = {cert.first_pass_rate:.0%} [KB-REPORT-002]",
        f"practice {learner.practice_score_avg} vs {config.PASS_PRACTICE_THRESHOLD} → {practice_factor:+.2f} ×0.40",
        f"hours {learner.hours_studied} vs rec {cert.recommended_hours} → {hours_factor:+.2f} ×0.12",
    ]
    if synergy:
        rationale.append(f">20h AND >75% synergy bonus +{synergy:.2f} [KB-REPORT-002]")
    if gaps:
        rationale.append("weak domains " + ", ".join(f"{n} {s:.0f}%" for n, s, _ in gaps)
                         + f" → −{coverage_penalty:.2f} coverage penalty")
    return ReadinessAssessment(round(score, 3), _band(score), round(practice_factor, 3),
                               round(hours_factor, 3), synergy, round(coverage_penalty, 3),
                               gaps, rationale)


# ---------------------------------------------------------------------------
# Per-candidate forecast  (optimist vs skeptic — different assumptions)
# ---------------------------------------------------------------------------
@dataclass
class CandidateForecast:
    learner_id: str
    name: str
    ramp: RampEstimate
    capacity: CapacityAssessment
    readiness: ReadinessAssessment
    hours_needed: float
    weeks_needed: float
    buffer_weeks: float
    p_time: float
    p_pass: float
    probability: float
    perspective: str          # "optimist" | "skeptic"
    reasons: list[str] = field(default_factory=list)


def forecast_candidate(learner: Learner, cert: Certification, ramp: RampEstimate,
                       capacity: CapacityAssessment, readiness: ReadinessAssessment,
                       deadline_weeks: float, perspective: str) -> CandidateForecast:
    weak = len(readiness.weak_domains)
    reasons: list[str] = []

    if perspective == "optimist":
        eff_capacity = capacity.weekly_capacity_hours
        hours_needed = max(0.0, ramp.adjusted_hours - learner.hours_studied)
        p_pass = _clamp(readiness.pass_probability + 0.25, 0.10, 0.95)
        reasons.append("assumes full focus capacity and that prep closes the gap by exam day")
        reasons.append("assumes a single exam attempt is enough")
    else:  # skeptic
        eff_capacity = capacity.weekly_capacity_hours * 0.80
        hours_needed = max(0.0, ramp.adjusted_hours - learner.hours_studied) + 3.0 * weak
        p_pass = _clamp(readiness.pass_probability * 0.60 + cert.first_pass_rate * 0.40 - 0.04 * weak, 0.05, 0.90)
        reasons.append("haircuts focus capacity 20% for real-world interruptions")
        if weak:
            reasons.append(f"adds {3*weak:.0f}h to remediate {weak} weak exam domain(s)")
        reasons.append(f"weights {cert.id} first-pass rate {cert.first_pass_rate:.0%} (retest risk)")

    # Test anxiety lowers exam-day performance (self-disclosed; used to inform, not to rank).
    anxiety = (learner.human or {}).get("anxiety", "none")
    anx_factor = ANXIETY.get(anxiety, ANXIETY["none"])[perspective]
    if anx_factor < 1.0:
        p_pass = _clamp(p_pass * anx_factor, 0.03, 0.95)
        reasons.append(f"{anxiety} test anxiety → exam-day factor ×{anx_factor:.2f}")

    eff_capacity = max(eff_capacity, 0.5)
    weeks_needed = round(hours_needed / eff_capacity, 2)
    buffer = round(deadline_weeks - weeks_needed, 2)
    p_time = round(_sigmoid(1.0 * buffer), 3)
    probability = round(_clamp(p_time * p_pass, 0.02, 0.98), 3)

    return CandidateForecast(
        learner_id=learner.learner_id, name=learner.name, ramp=ramp, capacity=capacity,
        readiness=readiness, hours_needed=round(hours_needed, 1), weeks_needed=weeks_needed,
        buffer_weeks=buffer, p_time=p_time, p_pass=round(p_pass, 3), probability=probability,
        perspective=perspective, reasons=reasons,
    )


# ---------------------------------------------------------------------------
# Team forecast  (exact Poisson-binomial)
# ---------------------------------------------------------------------------
def poisson_binomial_at_least(probs: list[float], k: int) -> float:
    """Exact P(>= k successes) given independent, differing success probabilities."""
    dist = [1.0]  # dist[j] = P(exactly j successes so far)
    for p in probs:
        nxt = [0.0] * (len(dist) + 1)
        for j, pj in enumerate(dist):
            nxt[j] += pj * (1 - p)
            nxt[j + 1] += pj * p
        dist = nxt
    return round(sum(dist[k:]), 4)


@dataclass
class TeamForecast:
    perspective: str
    required: int
    candidate_probs: list[tuple[str, float]]
    expected_certified: float
    prob_meet_requirement: float


def team_forecast(forecasts: list[CandidateForecast], required: int, perspective: str) -> TeamForecast:
    probs = [f.probability for f in forecasts]
    return TeamForecast(
        perspective=perspective,
        required=required,
        candidate_probs=[(f.name, f.probability) for f in forecasts],
        expected_certified=round(sum(probs), 2),
        prob_meet_requirement=poisson_binomial_at_least(probs, required),
    )


# ---------------------------------------------------------------------------
# Coaching projection  (the Enablement uplift)
# ---------------------------------------------------------------------------
@dataclass
class CoachProjection:
    learner_id: str
    name: str
    current_prob: float          # realistic (skeptic) prob today
    in_deadline_prob: float      # projected if gaps closed within the current deadline
    ceiling_prob: float          # projected with adequate study time (competence ceiling)
    weeks_to_close: float        # weeks of focused study to close the gaps
    gaps: list[tuple[str, float, float]]


def project_with_coaching(learner: Learner, cert: Certification, ramp: RampEstimate,
                          capacity: CapacityAssessment, current_prob: float,
                          deadline_weeks: float) -> CoachProjection:
    """Project readiness if the learner's weak exam domains are remediated to the
    pass threshold. Honest about time: closing gaps costs study hours, so the
    in-deadline number can stay low even when the competence ceiling is high."""
    gaps = coverage_gaps(learner, cert)
    if not gaps:
        return CoachProjection(learner.learner_id, learner.name, current_prob,
                               current_prob, current_prob, 0.0, [])

    lifted = {**learner.domain_scores, **{n: config.PASS_PRACTICE_THRESHOLD for n, _, _ in gaps}}
    domain_vals = [lifted.get(d["name"], learner.practice_score_avg) for d in cert.exam_domains]
    new_practice = max(learner.practice_score_avg, round(sum(domain_vals) / len(domain_vals)))
    coached = replace(learner, domain_scores=lifted, practice_score_avg=new_practice)
    rd = assess_readiness(coached, cert)

    remediation_hours = max(0.0, ramp.adjusted_hours - learner.hours_studied) + 3.0 * len(gaps)
    eff_capacity = max(capacity.weekly_capacity_hours * 0.80, 0.5)
    weeks_to_close = round(remediation_hours / eff_capacity, 2)
    p_pass = _clamp(rd.pass_probability * 0.60 + cert.first_pass_rate * 0.40, 0.05, 0.90)

    in_deadline = round(_clamp(_sigmoid(deadline_weeks - weeks_to_close) * p_pass, 0.02, 0.98), 3)
    ceiling = round(_clamp(0.95 * p_pass, 0.02, 0.98), 3)  # given adequate time
    return CoachProjection(learner.learner_id, learner.name, current_prob, in_deadline,
                           ceiling, weeks_to_close, gaps)


# ---------------------------------------------------------------------------
# Burnout / sustainability  (the human-advocate guardrail)
# ---------------------------------------------------------------------------
@dataclass
class BurnoutAssessment:
    learner_id: str
    name: str
    weekly_study_required: float
    load_ratio: float           # required study / weekly capacity
    sustained_weeks: float
    risk: str                   # "ok" | "watch" | "high" | "veto"
    flags: list[str]


def assess_burnout(forecast: CandidateForecast, work: dict, deadline_weeks: float) -> BurnoutAssessment:
    cap = max(forecast.capacity.weekly_capacity_hours, 0.5)
    weekly_required = round(forecast.hours_needed / max(deadline_weeks, 0.5), 2)
    load_ratio = round(weekly_required / cap, 2)
    flags: list[str] = []

    if work.get("meeting_hours_per_week", 0) > config.HIGH_MEETING_LOAD:
        flags.append(f"meeting-overloaded ({work['meeting_hours_per_week']}h/wk)")
    if work.get("recent_after_hours_study_sessions", 0) >= 3:
        flags.append(f"{work['recent_after_hours_study_sessions']} recent after-hours sessions")
    if work.get("open_deadlines", 0) >= 2:
        flags.append(f"{work['open_deadlines']} competing deadlines")

    sustained = forecast.weeks_needed
    risk = "ok"
    if load_ratio > 1.10:
        risk = "veto"
        flags.append(f"required {weekly_required:.1f}h/wk exceeds capacity {cap:.1f}h/wk — infeasible")
    elif load_ratio > config.SUSTAINABLE_LOAD_CEILING and sustained >= config.SUSTAINABLE_WEEKS_LIMIT:
        risk = "high"
        flags.append(f"{load_ratio:.0%} of capacity for {sustained:.0f} wks (> {config.SUSTAINABLE_WEEKS_LIMIT}) [KB-WORKLOAD-003]")
    elif load_ratio > config.SUSTAINABLE_LOAD_CEILING:
        risk = "watch"
        flags.append(f"{load_ratio:.0%} of weekly capacity — monitor")

    if not flags:
        flags.append("load within sustainable limits")
    return BurnoutAssessment(forecast.learner_id, forecast.name, weekly_required,
                             load_ratio, sustained, risk, flags)
