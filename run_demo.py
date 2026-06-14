"""Entry point — run the certification-readiness multi-agent debate.

Examples:
    python run_demo.py                 # the dramatic default mission
    python run_demo.py --fast          # no typing delay
    python run_demo.py --weeks 8 --required 3
    python run_demo.py --cert AZ-400 --candidates L-1005 L-1010 L-1002 --required 2 --weeks 6
"""
from __future__ import annotations
import argparse
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # Windows cp1252 safety
except Exception:
    pass

from src.scenario import Scenario
from src.orchestrator import Orchestrator
from src import console_ui as ui


def build_scenario(args) -> Scenario:
    cert = args.cert
    candidates = args.candidates or ["L-2001", "L-2004", "L-2011", "L-2014",
                                     "L-2002", "L-2010", "L-2008", "L-2015"]
    label = (f"MISSION: certify {args.required} of {len(candidates)} engineers for "
             f"{cert} within {args.weeks} weeks  (contract bid readiness)")
    return Scenario(cert_id=cert, required=args.required, deadline_weeks=args.weeks,
                    candidate_ids=candidates, label=label)


def main() -> None:
    p = argparse.ArgumentParser(description="Certification Readiness multi-agent system")
    p.add_argument("--cert", default="SC-200")
    p.add_argument("--candidates", nargs="*", default=None)
    p.add_argument("--required", type=int, default=5)
    p.add_argument("--weeks", type=float, default=5)
    p.add_argument("--fast", action="store_true", help="no inter-turn delay")
    args = p.parse_args()

    orch = Orchestrator()
    scenario = build_scenario(args)

    ui.header(scenario.label, orch.model.detail)
    delay = 0.0 if args.fast else 0.9
    for turn in orch.run(scenario):
        if turn.kind in ("optimist", "verdict"):
            ui.divider("the council deliberates" if turn.kind == "optimist" else "reconciliation")
        ui.render_turn(turn, delay=delay)
    ui.closing()


if __name__ == "__main__":
    main()
