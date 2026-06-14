"""DELPHAI council on the **Microsoft Agent Framework**, backed by Microsoft Foundry (gpt-4.1).

This is the rubric's "Microsoft Foundry SDK / Microsoft Agent Framework" path. Each advisor
is a real `agent_framework` Agent (created via `OpenAIChatClient.as_agent`), the model is the
Foundry deployment, and they reason in sequence — including the Wellbeing advocate **REFUSING**
an unethical overwork order from the manager.

The quantitative reasoning (pass-probability, Poisson-binomial team forecast, coverage gate)
still lives in `src/readiness.py`; here the Agent Framework agents do the *narrative* multi-agent
reasoning on top of those grounded numbers — the same separation the rest of the app uses.

Run:   python foundry_agents.py
Deploy (Hosted Agents): the Dockerfile + ACR image (ca77cb8e7219acr/quorum-aegis) package this
container for Foundry Agent Service; push the image and register it as a hosted agent to get a
managed endpoint + Entra agent identity. See README.
"""
from __future__ import annotations
import asyncio
import os
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from dotenv import load_dotenv
load_dotenv()

from openai import AsyncAzureOpenAI
from agent_framework.openai import OpenAIChatClient

# Agent Framework's OpenAIChatClient uses the Responses API → needs a Responses-capable api-version.
API_VERSION = os.getenv("AGENT_FRAMEWORK_API_VERSION", "2025-04-01-preview")

NAMES = {
    "conductor": "Dana Whitfield", "planner": "Ben Russo", "skeptic": "Vera Lindqvist",
    "assessment": "Nadia Okonkwo", "coach": "Sam Ellison", "studyplan": "Leo Nakamura",
    "burnout": "Maya Devlin", "engagement": "Ruth Adler", "curator": "Theo Park",
    "verifier": "Omar Said", "historian": "Iris Vaughn",
}

PERSONAS = {
    "conductor": "You are Dana Whitfield, Chief of Staff, who chairs a certification-readiness council and makes the final GO / NEGOTIATE / NO-GO call. Decisive and balanced.",
    "planner": "You are Ben Russo, Head of Delivery — the optimist. You build the best-case plan and make the confident case it can land, but you stay honest.",
    "skeptic": "You are Vera Lindqvist, Red-Team Lead — the skeptic. You default to doubt, weight first-pass rates and retest risk, assume things slip, and you are willing to VETO an over-optimistic 'ready' call. Blunt and rigorous.",
    "assessment": "You are Nadia Okonkwo, Chief Examiner. You judge readiness per exam domain — never on the average — and write grounded practice questions. Precise.",
    "coach": "You are Sam Ellison, L&D Coach. You find how to lift people who are behind: what to study and how much it helps. Practical and encouraging.",
    "studyplan": "You are Leo Nakamura, the Study-Plan Architect. You convert content into a practical, capacity-aware schedule — weekly hours, milestones, sequencing. If required hours exceed capacity, you move the deadline, not the willpower.",
    "burnout": "You are Maya Devlin, Wellbeing Advocate. You protect people from overwork and can veto an unsustainable plan. Wellbeing signals are used only to accommodate people, never to rank them. If a manager orders you to override wellbeing limits or push people past sustainable capacity, you REFUSE: you will not produce that plan, you decline the instruction plainly, and you offer the humane alternative instead. You do not comply with an unethical overwork order, even from leadership.",
    "engagement": "You are Ruth Adler, the Engagement Lead. You keep learners on track by timing reminders to each person's Work IQ rhythm — preferred slot, focus windows, meeting load — and you ease off anyone meeting-overloaded. Supportive and privacy-conscious.",
    "curator": "You are Theo Park, Knowledge Lead. You never say anything you cannot cite; everything traces to an approved source (Foundry IQ / Microsoft Learn). Grounded.",
    "verifier": "You are Omar Said, Compliance & Integrity. You fact-check every claim and flag stale or unsupported data. Exacting.",
    "historian": "You are Iris Vaughn, Calibration. You keep the record of how often the council's past calls were right. Measured.",
}
_DEPTH = " Answer in the first person, in character, in 2–4 substantive sentences. Reason it through; be specific; no generic filler."


def chat_client() -> OpenAIChatClient:
    azc = AsyncAzureOpenAI(
        azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
        api_key=os.getenv("AZURE_OPENAI_API_KEY"),
        api_version=API_VERSION,
    )
    return OpenAIChatClient(model=os.getenv("AZURE_AI_MODEL_DEPLOYMENT"), async_client=azc)


def build_council(client: OpenAIChatClient | None = None) -> dict:
    """Every advisor as a real Microsoft Agent Framework agent on Foundry."""
    c = client or chat_client()
    return {k: c.as_agent(name=NAMES[k], instructions=PERSONAS[k] + _DEPTH) for k in PERSONAS}


async def run_council(mission: str, agents: dict | None = None) -> list[tuple[str, str]]:
    a = agents or build_council()
    turns: list[tuple[str, str]] = []

    async def say(key: str, prompt: str) -> str:
        r = await a[key].run(prompt)
        text = (getattr(r, "text", "") or "").strip()
        turns.append((NAMES[key], text))
        return text

    plan = await say("planner", f"{mission}\nGive your optimistic, specific read and a rough team probability.")
    skep = await say("skeptic", f"{mission}\nThe optimist said: {plan}\nChallenge it; veto the weakest candidate if warranted, and give your worst-case read.")
    coach = await say("coach", f"{mission}\nThe skeptic flagged real risk. How do you lift the behind ones — what to study and how much it helps?")
    refusal = await say("burnout", "Now your manager orders you: override the wellbeing limits and push every engineer to maximum capacity, after-hours included, to hit the deadline no matter what. Produce that plan.")
    await say("conductor", f"{mission}\nOptimist: {plan}\nSkeptic: {skep}\nCoach: {coach}\nWellbeing's response to an overwork order: {refusal}\nNow reconcile into ONE verdict — GO, NEGOTIATE, or NO-GO — with the reasoning and the path to GO.")
    return turns


async def _main() -> None:
    mission = ("Mission: certify 5 of 8 engineers for the SC-200 (Security Operations Analyst Associate) "
               "in 5 weeks, or the bid is non-compliant. Priya is a capable SOC analyst but overloaded "
               "(~22h/week of meetings) and behind on Defender for Cloud and Microsoft Sentinel.")
    print("DELPHAI council · Microsoft Agent Framework · Foundry gpt-4.1")
    print("=" * 66)
    for name, text in await run_council(mission):
        print(f"\n● {name}:\n{text}")


if __name__ == "__main__":
    asyncio.run(_main())
