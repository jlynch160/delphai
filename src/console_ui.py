"""Rich console rendering for the agent debate — the showcase surface.

Each Turn becomes a colored panel in the agent's voice, with its structured
reasoning beneath. Debate turns (optimist/skeptic/burnout/verdict) get extra
emphasis so the argument reads like a boardroom, not a log dump.
"""
from __future__ import annotations
import time

from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.rule import Rule
from rich import box

from .agents.base import Turn

console = Console()

_KIND_TAG = {
    "info": "", "gate": "COVERAGE GATE", "optimist": "OPTIMIST", "skeptic": "SKEPTIC ⚔",
    "burnout": "HUMAN ADVOCATE", "verify": "INTEGRITY", "verdict": "VERDICT", "negotiate": "COUNTER-OFFER",
}


def header(scenario_label: str, mode_detail: str) -> None:
    console.print()
    console.print(Panel(
        Text.assemble(
            ("CERTIFICATION READINESS  ·  multi-agent reasoning system\n", "bold bright_cyan"),
            (scenario_label + "\n", "bold white"),
            (f"model: {mode_detail}", "dim"),
        ),
        box=box.DOUBLE, border_style="bright_cyan", padding=(1, 3),
    ))
    console.print()


def render_turn(turn: Turn, delay: float = 0.0) -> None:
    tag = _KIND_TAG.get(turn.kind, "")
    title = Text.assemble((f" {turn.agent} ", f"bold {turn.color}"),
                          (f" {turn.persona_label} ", "dim"))
    if tag:
        title.append(f"  [{tag}]", style=f"bold {turn.color}")

    body = Text()
    body.append(turn.headline.strip() + "\n", style=f"italic {turn.color}")
    if turn.lines:
        body.append("\n")
        for ln in turn.lines:
            style = "white"
            if ln.startswith("⛔") or "VETO" in ln:
                style = "bold bright_red"
            elif ln.startswith("⚠"):
                style = "bold yellow"
            elif ln.startswith("DECISION"):
                style = "bold bright_white"
            elif ln.lstrip().startswith("•") or ln.startswith("Recommend"):
                style = "bright_white"
            body.append("  " + ln + "\n", style=style)

    border = turn.color
    if turn.kind == "verdict":
        border = "bright_white"
    console.print(Panel(body, title=title, title_align="left", border_style=border,
                        box=box.ROUNDED, padding=(0, 2)))
    if delay:
        time.sleep(delay)


def divider(label: str) -> None:
    console.print(Rule(label, style="dim"))


def closing() -> None:
    console.print()
    console.print(Panel(
        Text("Every probability above is computed — skill-adjacency ramps, Work IQ capacity, "
             "exam-blueprint coverage, and an exact Poisson-binomial team forecast — then "
             "stress-tested by the skeptic, checked by the burnout advocate, and verified for "
             "grounding. Reasoning you can see, audit, and defend.",
             justify="left", style="dim"),
        border_style="dim", box=box.SIMPLE, padding=(0, 2)))
    console.print()
