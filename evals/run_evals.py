"""Evaluation harness — proves the reasoning is trustworthy, not just plausible.

Checks:
  1. Outcome reproduction — the pass-probability model reproduces the synthetic exam
     outcomes (the two passes are not 'Not Ready'; the fail is not 'Exam Ready').
  2. Skeptic <= Optimist — the skeptic is never more optimistic than the optimist.
  3. Capacity penalty — meeting-overloaded learners get a reduced study budget.
  4. Coverage gate — a learner with a sub-75 domain is flagged.
  5. Poisson-binomial sanity — probabilities are bounded and monotone in k.
  6. Grounding — every citation the agents emit resolves to the knowledge base.

Run:  python -m evals.run_evals
"""
from __future__ import annotations
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # Windows cp1252 safety
except Exception:
    pass

from src.data_store import get_store
from src.skill_graph import SkillGraph
from src.pipeline import evaluate_pool
from src import readiness
from src.scenario import Scenario
from src.orchestrator import Orchestrator

PASS, FAIL = "PASS", "FAIL"
results: list[tuple[str, str, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((PASS if ok else FAIL, name, detail))


def main() -> int:
    store = get_store()
    sg = SkillGraph(store)

    # 1. Outcome reproduction (Aegis security team)
    expectations = {"L-2001": ("Fail", {"Not Ready"}),
                    "L-2002": ("Pass", {"Exam Ready", "On Track"}),
                    "L-2003": ("Pass", {"Exam Ready", "On Track"})}
    for lid, (outcome, allowed) in expectations.items():
        learner = store.learner(lid)
        cert = store.cert(learner.target_certification)
        band = readiness.assess_readiness(learner, cert).band
        check(f"outcome reproduction {lid} ({outcome})", band in allowed,
              f"band={band}, allowed={allowed}")

    # 2. Skeptic <= Optimist
    cert = store.cert("SC-200")
    ids = ["L-2001", "L-2002", "L-2010", "L-2011", "L-2004"]
    opt = readiness.team_forecast(evaluate_pool(store, sg, ids, cert, 5, "optimist"), 3, "optimist")
    skp = readiness.team_forecast(evaluate_pool(store, sg, ids, cert, 5, "skeptic"), 3, "skeptic")
    check("skeptic <= optimist team prob",
          skp.prob_meet_requirement <= opt.prob_meet_requirement + 1e-9,
          f"optimist={opt.prob_meet_requirement:.2f} skeptic={skp.prob_meet_requirement:.2f}")

    # 3. Capacity penalty for meeting overload (Priya = 22h meetings vs Tom = 12h)
    overloaded = readiness.assess_capacity(store.learner("L-2001").work)
    normal = readiness.assess_capacity(store.learner("L-2004").work)
    check("meeting-overload capacity penalty", overloaded.meeting_overloaded and
          overloaded.weekly_capacity_hours < normal.weekly_capacity_hours,
          f"L-2001={overloaded.weekly_capacity_hours} L-2004={normal.weekly_capacity_hours}")

    # 4. Coverage gate flags a weak domain (Priya: Defender for Cloud 58)
    gaps = readiness.coverage_gaps(store.learner("L-2001"), store.cert("SC-200"))
    check("coverage gate flags weak domain", any(n == "Defender for Cloud" for n, _, _ in gaps),
          f"gaps={[n for n,_,_ in gaps]}")

    # 5. Poisson-binomial sanity
    probs = [0.6, 0.5, 0.7, 0.4]
    p1 = readiness.poisson_binomial_at_least(probs, 1)
    p4 = readiness.poisson_binomial_at_least(probs, 4)
    p0 = readiness.poisson_binomial_at_least(probs, 0)
    check("poisson-binomial bounded & monotone", abs(p0 - 1.0) < 1e-9 and p1 >= p4 and 0 <= p4 <= 1,
          f"p0={p0} p1={p1} p4={p4}")

    # 6. Grounding — every emitted citation resolves
    orch = Orchestrator()
    turns = list(orch.run(Scenario("SC-200", 3, 5, ids)))
    emitted = [c for t in turns for c in t.data.get("citations", [])]
    unresolved = [c for c in set(emitted) if not store.citation_exists(c)]
    check("all emitted citations resolve to KB", not unresolved, f"unresolved={unresolved}")

    # report
    width = max(len(n) for _, n, _ in results)
    print("\n=== Reasoning evaluation ===")
    n_fail = 0
    for status, name, detail in results:
        mark = "✓" if status == PASS else "✗"
        line = f"  {mark} {status}  {name.ljust(width)}"
        if status == FAIL:
            n_fail += 1
            line += f"   -> {detail}"
        print(line)
    total = len(results)
    print(f"\n{total - n_fail}/{total} checks passed.\n")
    return 1 if n_fail else 0


if __name__ == "__main__":
    sys.exit(main())
