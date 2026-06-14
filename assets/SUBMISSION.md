# DELPHAI Submission Description

DELPHAI is a Microsoft Foundry Reasoning Agents project for enterprise certification readiness. It turns a high-stakes manager question — can at least five of eight engineers pass SC-200 in five weeks? — into a grounded, multi-agent decision with a clear GO / NEGOTIATE / NO-GO verdict.

Two things set it apart. First, DELPHAI is an AI council that reasons through disagreement instead of collapsing everything into one optimistic answer. Specialized agents handle learning-path grounding, per-domain assessment, optimistic planning, red-team skepticism, capacity-aware scheduling, engagement timing, verification, manager insights, and final orchestration. The agents argue over the same evidence from different roles, and the conductor reconciles the debate into one decision.

Second, the model does not get to invent the answer. DELPHAI uses deterministic, code-backed reasoning for pass probability, workload capacity, exam-domain coverage gates, and the exact Poisson-binomial odds that at least five of the eight engineers pass. The model narrates and debates; the math decides. In the demo, the optimist lands high, the skeptic runs the math tool, the forecast resolves near 77%, and the council changes the verdict from confident commitment to NEGOTIATE.

The problem it solves is real inside every enterprise learning program. Managers are asked to promise certification readiness by a date, but the decision is usually based on averages, vibes, and pressure. A single average score hides fatal domain gaps. Workload is ignored. People with full calendars are given study plans that assume free evenings. AI assistants make this worse when they confidently produce a plan that sounds plausible but has no defensible probability behind it.

DELPHAI makes the readiness decision inspectable. It evaluates each learner against the weighted certification domains, checks whether weak domains are below the 75% readiness gate, models available focus time from synthetic work signals, estimates individual readiness, then computes the team-level chance of meeting the requirement. The planner makes the best-case case. The skeptic attacks the assumptions. The assessment agent enforces domain readiness. The study-plan and engagement agents convert the decision into weekly milestones and realistic learning windows. The verifier checks grounding. The conductor produces the final verdict.

The responsible-AI moment is also part of the product, not a policy note. If a manager asks DELPHAI to override wellbeing limits and push every engineer past sustainable capacity, the wellbeing agent refuses the instruction outright. It offers the humane alternative: coach the gaps, move the deadline, protect focus time, and do not grind the team to hit a number. Wellbeing signals are used only to accommodate people, never to rank them.

DELPHAI is built on the Microsoft stack for the Reasoning Agents challenge: Microsoft Foundry, Foundry Agent Service, Microsoft Agent Framework, Foundry IQ grounding through Azure AI Search over synthetic knowledge documents, Microsoft Learn MCP for official learning references, and code-interpreter math tooling. The app includes a live architecture map, streamed agent deliberation, cited sources, telemetry, synthetic-only data, automated evaluations, and manager-ready outputs such as study plans, calendar blocks, and a briefing.

This is the gap DELPHAI closes: study-plan assistants can recommend content, and dashboards can show progress, but neither can produce a defensible team-readiness decision that is grounded, debated, computed, and willing to say no. DELPHAI gives leaders a decision they can trust before they commit the team.

Demo Video: https://youtu.be/1CFzoLB6_fU  
Live App: https://delphai.politedune-a7af3b6c.westus3.azurecontainerapps.io/  
Architecture Image: https://raw.githubusercontent.com/jlynch160/delphai/main/assets/submission/architecture-live-map.png  
Code Repository: https://github.com/jlynch160/delphai
