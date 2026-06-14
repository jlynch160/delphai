"""DELPHAI council registered in **Microsoft Foundry Agent Service** (Hosted Agents).

Each advisor becomes a *persistent Foundry agent* on the `delphai` project of the
`quorum-foundry-jl` AI Foundry resource — a managed runtime with an Entra agent identity,
not just a chat-completions call. We then open a thread and run the Conductor to prove the
managed runtime answers, capturing the transcript.

Run:   python foundry_hosted_agent.py
Auth:  DefaultAzureCredential (run `az login` first; uses your Azure CLI credential).
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

from foundry_agents import NAMES, PERSONAS, _DEPTH

ENDPOINT = os.getenv(
    "FOUNDRY_PROJECT_ENDPOINT",
    "https://quorum-foundry-jl.services.ai.azure.com/api/projects/delphai",
)
MODEL = os.getenv("AZURE_AI_MODEL_DEPLOYMENT", "quorum-gpt41")

MISSION = (
    "Mission: certify 5 of 8 engineers for the SC-200 (Security Operations Analyst Associate) "
    "in 5 weeks, or the bid is non-compliant. Priya is a capable SOC analyst but overloaded "
    "(~22h/week of meetings) and behind on Defender for Cloud and Microsoft Sentinel. "
    "Give a GO / NEGOTIATE / NO-GO call with the reasoning and the path to GO."
)


def main() -> None:
    print("DELPHAI · Microsoft Foundry Agent Service (Hosted Agents)")
    print("=" * 64)
    print(f"project endpoint : {ENDPOINT}")
    print(f"model deployment : {MODEL}\n")

    cred = DefaultAzureCredential()
    client = AgentsClient(endpoint=ENDPOINT, credential=cred)

    created = {}
    for key in PERSONAS:
        a = client.create_agent(model=MODEL, name=NAMES[key], instructions=PERSONAS[key] + _DEPTH)
        created[key] = a.id
        print(f"registered  {NAMES[key]:<22}  {a.id}")

    print(f"\n✓ {len(created)} council agents registered on Foundry Agent Service "
          f"(project 'delphai').\n")

    # Prove the managed runtime answers: open a thread and run the Conductor on the mission.
    print("--- live run: Conductor on the Foundry-managed runtime ---")
    run = client.create_thread_and_process_run(
        agent_id=created["conductor"],
        thread={"messages": [{"role": "user", "content": MISSION}]},
    )
    print(f"run status: {run.status}  (thread {run.thread_id})\n")
    for m in client.messages.list(thread_id=run.thread_id):
        if getattr(m, "role", "") == "assistant":
            try:
                print(m.text_messages[-1].text.value)
            except Exception:
                print(getattr(m, "content", m))
            break


if __name__ == "__main__":
    main()
