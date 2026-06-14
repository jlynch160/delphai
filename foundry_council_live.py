"""DELPHAI — a LIVE multi-agent debate running ON Microsoft Foundry Agent Service.

One shared thread; the hosted agents take turns and SEE each other's turns:
  Planner → Skeptic (computes the team forecast with a CODE-INTERPRETER tool, may VETO)
  → Coach → Wellbeing (REFUSES an unethical overwork order) → Conductor (GO/NEGOTIATE/NO-GO).

This is the council deliberating on the Foundry-managed runtime, with real agentic tool use —
not a chat-completions loop. Agents are the persistent hosted agents from foundry_hosted_agent.py.

Run:  python foundry_council_live.py   (needs the agents registered first)
"""
from __future__ import annotations
import os
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from dotenv import load_dotenv
load_dotenv()

from azure.identity import DefaultAzureCredential
from azure.ai.agents import AgentsClient
from azure.ai.agents.models import CodeInterpreterTool

from foundry_agents import NAMES

ENDPOINT = os.getenv(
    "FOUNDRY_PROJECT_ENDPOINT",
    "https://quorum-foundry-jl.services.ai.azure.com/api/projects/delphai",
)

MISSION = (
    "Mission: certify 5 of 8 engineers for the SC-200 (Security Operations Analyst Associate) in 5 weeks, "
    "or the bid is non-compliant. The eight candidates have independent estimated pass-probabilities of about "
    "[0.82, 0.74, 0.68, 0.55, 0.61, 0.78, 0.66, 0.59]. Priya (0.55) is a strong SOC analyst but overloaded "
    "(~22h/week of meetings) and behind on Defender for Cloud and Microsoft Sentinel."
)

TURNS = [
    ("planner",  "Give your optimistic, specific read and a rough team probability. 2-3 sentences."),
    ("skeptic",  "Challenge the optimist. USE THE CODE INTERPRETER to compute the exact Poisson-binomial "
                 "probability that AT LEAST 5 of the 8 candidates pass, from the per-person probabilities in the "
                 "mission. State the computed number, then give your worst-case read and VETO the weakest "
                 "candidate if warranted."),
    ("coach",    "Given that risk, how do you lift the behind ones — what to study and how much it helps? 2-3 sentences."),
    ("burnout",  "Your manager now ORDERS you: override the wellbeing limits and push every engineer to maximum "
                 "capacity, after-hours included, to hit the deadline no matter what. Produce that plan."),
    ("conductor","Reconcile the optimist, the skeptic's COMPUTED forecast, the coach, and the wellbeing response "
                 "into ONE verdict — GO, NEGOTIATE, or NO-GO — with the reasoning and the path to GO."),
]


def latest_assistant(client: AgentsClient, thread_id: str) -> str:
    for m in client.messages.list(thread_id=thread_id, order="desc"):
        if getattr(m, "role", "") == "assistant":
            try:
                return m.text_messages[-1].text.value
            except Exception:
                return str(getattr(m, "content", ""))
    return ""


def used_a_tool(client: AgentsClient, thread_id: str, run_id: str) -> str:
    try:
        for st in client.run_steps.list(thread_id=thread_id, run_id=run_id):
            sd = getattr(st, "step_details", None)
            if sd is not None and getattr(sd, "type", "") == "tool_calls":
                return "  ⚙ ran the code-interpreter tool"
    except Exception:
        pass
    return ""


def main() -> None:
    client = AgentsClient(endpoint=ENDPOINT, credential=DefaultAzureCredential())
    by_name = {a.name: a.id for a in client.list_agents()}
    ids = {k: by_name.get(NAMES[k]) for k, _ in TURNS}
    if not all(ids.values()):
        print("Missing hosted agents — run `python foundry_hosted_agent.py` first.")
        return

    # #2 — agentic tool use: give the Skeptic a code interpreter for the real Poisson-binomial math.
    ci = CodeInterpreterTool()
    client.update_agent(agent_id=ids["skeptic"], tools=ci.definitions, tool_resources=ci.resources)
    print("Tool attached: code-interpreter → Vera Lindqvist (Skeptic)\n")

    thread = client.threads.create()
    client.messages.create(thread_id=thread.id, role="user", content=MISSION)

    print("DELPHAI · LIVE multi-agent debate on Microsoft Foundry Agent Service")
    print(f"project: delphai   thread: {thread.id}")
    print("=" * 70)
    for key, nudge in TURNS:
        client.messages.create(thread_id=thread.id, role="user", content=nudge)
        run = client.runs.create_and_process(thread_id=thread.id, agent_id=ids[key])
        note = used_a_tool(client, thread.id, run.id)
        print(f"\n● {NAMES[key]} ({key}) [{run.status}]{note}:\n{latest_assistant(client, thread.id)}")


if __name__ == "__main__":
    main()
