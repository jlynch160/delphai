# Foundry IQ — live runtime proof

_Captured 2026-06-13 23:51 UTC by `scripts/prove_foundry_iq.py`._

- **Model surface:** `foundry` — Azure OpenAI · quorum-gpt41
- **Foundry IQ configured:** `True` (Azure AI Search index `delphai-knowledge`)

## 1 · A live Curator turn grounds through Azure AI Search

- **Grounding source after the agent searched:** `foundry_iq`
- **Cited chunks returned by Foundry IQ:** 3
  - `KB-ENABLE-001` — AZ-204 — Developing Solutions for Azure
  - `KB-REPORT-002` — Overview
  - `KB-ENABLE-001` — Domain: Security (15% of exam)

**Curator headline (narrated live by Foundry gpt-4.1, grounded in the retrieved chunks):**

> The heaviest SC-200 exam domain is Microsoft Sentinel at 40%; mastery is best closed via the Microsoft Learn module “Configure SIEM security operations with Microsoft Sentinel.” Concretely, ‘ready’ means being able to create a KQL-based Sentinel analytics rule (e.g., SecurityIncident | where Severity == 'High' | summarize by AlertName), as established by KB-ENABLE-001 and internal analytics (KB-REPORT-002).

## 2 · Vector hybrid retrieval (semantic, not keyword)

- **Query:** _“how much studying makes someone likely to pass the exam”_
- **Grounding source:** `foundry_iq`
  - `KB-REPORT-002` — Interpretation: “## Interpretation A single high average can mask a weak domain. Readiness should be evaluated per exam domain, not on th…”
  - `KB-REPORT-002` — Aggregate Metrics: “## Aggregate Metrics - Average study time: 21 hours - Overall first-attempt pass rate: 68%…”

The correlation passage is retrieved despite sharing almost no exact words with the query — that is the dense-vector half of the hybrid search working, which the local keyword fallback could not do.

