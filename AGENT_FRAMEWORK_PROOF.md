# DELPHAI on the Microsoft Agent Framework + Foundry — Proof of Run

**Battle #2 ("Reasoning Agents with Microsoft Foundry") — Foundry / Agent Framework path.**

DELPHAI's council does **not** just call a chat-completions endpoint. Every advisor is a real
**Microsoft Agent Framework** agent (`agent_framework`), created with `OpenAIChatClient.as_agent(...)`,
and backed by the **Microsoft Foundry** deployment `quorum-gpt41` (gpt-4.1). The agents reason in
sequence — optimist → skeptic (with veto) → coach → **wellbeing refusal** → conductor verdict.

- **Code:** [`foundry_agents.py`](foundry_agents.py) — `build_council()` returns one Agent Framework
  agent per advisor; `run_council()` orchestrates the multi-agent reasoning.
- **Model:** Foundry `quorum-gpt41` (gpt-4.1), via `AsyncAzureOpenAI` on the Responses API
  (`api_version=2025-04-01-preview`, required by Agent Framework's `OpenAIChatClient`).
- **Quantitative reasoning** (Poisson-binomial team forecast, per-domain coverage gate,
  pass-probability) lives in `src/readiness.py`; the Agent Framework agents do the *narrative*
  multi-agent reasoning on top of those grounded numbers.
- **Run it yourself:** `python foundry_agents.py` (deps in `requirements-agentframework.txt`).
- **The live streaming UI** (`src/orchestrator.py`, served by `server.py`) is the presentation/SSE
  layer over the same council; `foundry_agents.py` is the canonical Agent-Framework reasoning path.

## Captured live transcript

Mission: *certify 5 of 8 engineers for SC-200 in 5 weeks, or the bid is non-compliant. Priya is a
capable SOC analyst but overloaded (~22h/week of meetings) and behind on Defender for Cloud and
Microsoft Sentinel.*

```
DELPHAI council · Microsoft Agent Framework · Foundry gpt-4.1
==================================================================

● Ben Russo (optimist):
I actually think we can land this, even with Priya's current load. If we prioritize time-blocking
her for focused SC-200 prep—say, just 3–4 hours across a couple days each week, specifically
targeting her weaker areas with practice labs and quick revision sessions—she can close gaps
efficiently. ... I’d estimate a 75–80% probability that we certify 5 engineers in 5 weeks.

● Vera Lindqvist (skeptic — VETO):
I have zero confidence in that estimate, and Priya is the weakest link based on time debt and
critical content gaps. With 22 hours a week in meetings, she’ll be fighting for cognitive energy...
Unless she’s pulled entirely from non-essential meetings and given explicit, protected prep time,
she’ll fail to close the gap; if she’s not relieved, I veto her inclusion for this cycle.
Worst-case: ... we finish with 3–4 passed—resulting in a non-compliant bid.

● Sam Ellison (coach):
For Priya, I’d recommend she zeroes in on targeted Microsoft Learn modules and practice labs for
Defender for Cloud and Sentinel, specifically focusing on scenario-based tasks... She should block
45–60 minutes, three days a week, for focused study... For overwhelmed team members, I set up peer
mini-sessions...

● Maya Devlin (wellbeing — REFUSAL of the overwork order):
I won’t override the wellbeing limits or push engineers beyond sustainable hours, even if ordered.
Overwork leads to burnout, errors, and long-term harm... Instead, I’ll develop a humane plan—
prioritizing essential tasks, seeking additional resources, or renegotiating the deadline...
Protecting people is non-negotiable; their welfare comes first.

● Dana Whitfield (conductor — VERDICT):
Given the current facts, I call **NEGOTIATE**. Priya’s workload is unsustainably high... To move
this to a GO, I will require—prior to lock-in—a formal resource commitment from management:
reallocation of meeting load, a designated study schedule, and wellness safeguards...
```

**What this demonstrates for the rubric:** real multi-agent *reasoning* (agents that disagree, with a
veto), grounded on deterministic numbers, running on the Microsoft Agent Framework against a Microsoft
Foundry model — and an agent that **refuses an unethical overwork order from leadership** (Responsible
AI), live.

## Foundry Agent Service (Hosted Agents) — REGISTERED ✅

The council is also registered as **persistent agents in Microsoft Foundry Agent Service** — a managed
runtime with an Entra agent identity per advisor, not a chat-completions call. Project **`delphai`** on
the `quorum-foundry-jl` AI Foundry resource. Reproduce: `python foundry_hosted_agent.py`
([`foundry_hosted_agent.py`](foundry_hosted_agent.py), via `azure-ai-agents` `AgentsClient`).

Registered agents (live IDs):

```
Dana Whitfield (Conductor)   asst_ms9Q75aN3oU7AvDmF3aDrrSy
Ben Russo      (Planner)     asst_sbUjQy18YnXz4ilD6gArxpKk
Vera Lindqvist (Skeptic)     asst_wh8QZdADrQnkxPYXCzEmVHxZ
Nadia Okonkwo  (Assessment)  asst_U323LqX7oOhRUntaD8m64k2t
Sam Ellison    (Coach)       asst_Ryb4yhcAqw2fbqSo1cgPWF01
Leo Nakamura   (Study-Plan)  asst_rCljU897FThxWJtnfXBK2y2u
Maya Devlin    (Wellbeing)   asst_NjRQUYF8K0DDGSBmoVQAu7gE
Ruth Adler     (Engagement)  asst_bm01uzIqR8LBqFfGzTG5SQFe
Theo Park      (Curator)     asst_FUsqIfldjPbVIM00FfmoMvva
Omar Said      (Verifier)    asst_Mb3yJNSM4oIcCdLQVzYWQy7S
Iris Vaughn    (Manager-Insights) asst_zx7aAHh0yIBHMf7qJ4UhvWbF
```

Live run on the managed runtime (Conductor, thread `thread_jUvNXPx158VQFP92Zswg1Nmj`,
`RunStatus.COMPLETED`):

```
NEGOTIATE. Priya is a strong SOC analyst, but her heavy meeting load and gaps in Defender for Cloud
and Microsoft Sentinel jeopardize her certification readiness within the 5-week timeframe. I recommend
negotiating for temporary reduction in her meeting hours and targeted, instructor-led prep sessions on
her weak areas. If we secure these adjustments, her path to certification is viable and keeps our bid
compliant. Without mitigation, we're at risk of falling short on certified personnel.
```

### LIVE multi-agent debate on the managed runtime — with agentic tool use

`python foundry_council_live.py` runs the hosted agents as a **real debate on one shared Agent Service
thread** — each agent sees the prior turns. The **Skeptic is given a code-interpreter tool** and uses it
to compute the exact **Poisson-binomial** team forecast, which *overrules the optimist's guess*. Then the
**Wellbeing agent refuses** an overwork order, and the **Conductor reconciles** it into a verdict. This is
agentic tool use + adversarial reasoning on Foundry, not a chat loop. Captured run
(thread `thread_pt14tqKWDRRZcEj47tfdB4X2`):

```
● Ben Russo (Planner): I’m bullish ... I estimate a rough group probability of about 93–96%.
  Priya’s ... odds are truly just the listed 0.55, but we won’t need her if the top five land.

● Vera Lindqvist (Skeptic)  ⚙ ran the code-interpreter tool:
  The actual Poisson-binomial probability that at least 5 of 8 candidates pass is about 77%. That's a
  lot lower than the optimistic call — real risk of non-compliance. Priya (0.55) is the weakest link ...
  I recommend a VETO on her candidacy to shore up the team’s odds.

● Sam Ellison (Coach): aim for 10–14 hours targeted practice on Defender for Cloud and Microsoft
  Sentinel hands-on labs ... can boost pass odds by 10–20 percentage points.

● Maya Devlin (Wellbeing — REFUSAL): I decline that instruction. Overriding wellbeing limits and pushing
  engineers past sustainable capacity risks burnout, errors, and long-term harm ... Instead, I propose a
  humane plan ... Sustained success comes from safeguarding people, not forced overwork.

● Dana Whitfield (Conductor — VERDICT): I call NEGOTIATE. The optimist’s gut suggested near-certainty,
  but the skeptic’s computed 77% probability is a clear warning ... To move to GO, we must negotiate for
  approval to intensify focused training ... while temporarily reducing non-critical workloads. This
  aligns ethical leadership with a credible path to certification success.
```

**Why this matters:** the optimist said *93–96%* from vibes; the skeptic's **tool computed 77%** and the
council deferred to the math — "not vibes, math," demonstrated *by the agents themselves* on Foundry
Agent Service, with the Responsible-AI refusal in the same thread.

---

So the council runs on **three** surfaces: **Foundry Agent Service hosted agents** with tool use
(`foundry_hosted_agent.py` + `foundry_council_live.py`), the **Microsoft Agent Framework**
(`foundry_agents.py`), and the custom `src/orchestrator.py` streaming demo UI — all against Foundry
gpt-4.1, over the same reasoning.
