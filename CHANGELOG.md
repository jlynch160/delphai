# Changelog

All notable changes to DELPHAI (Microsoft Agents League, Battle #2 — Reasoning Agents on Microsoft Foundry).

## 2026-06-13

### Added — Foundry IQ on real Azure AI Search
- Grounding upgraded from a local keyword stand-in to a genuine **Foundry IQ** integration: a real
  **Azure AI Search** service (`delphai-search`), index `delphai-knowledge`, **hybrid vector + keyword**
  retrieval with `text-embedding-3-small` embeddings and verified citations.
- `src/connectors/foundry_iq.py` — runtime retriever; degrades gracefully (hybrid → keyword-only → local
  corpus) so the offline demo never breaks.
- `scripts/build_foundry_iq.py` — idempotent indexer (reuses the same `DataStore` chunking).
- `DataStore.search_knowledge` now prefers Foundry IQ and records `last_grounding_source`; `/api/health`
  reports `grounding: foundry_iq | local`.
- `scripts/prove_foundry_iq.py` + `FOUNDRY_IQ_PROOF.md` — live runtime proof that a Foundry gpt-4.1 turn
  grounds through Azure AI Search.

### Added — Live Architecture Map
- New interactive home-page section: 5 colour-coded stages (Request → Foundry → Council → Grounding →
  Decision), per-node spec pills, a stats strip, icon tiles, and animated arrowhead connectors.
- "▶ Trace a request" animates the flow end-to-end with travelling pulses; click any node to inspect it;
  auto-plays once on scroll.

### Changed
- README + UI now describe Foundry IQ as real Azure AI Search (no longer a "stand-in").
- Added an Observability / tracing / proof-artifacts section to the README.
- Rewrote the README as a professional showcase (badges, TOC, overview, problem, solution,
  differentiators, key features, architecture, tech stack, getting started, project structure,
  rubric mapping, roadmap) and added GitHub repository topics.

### Fixed / hygiene
- Removed a real email address from `.env.example` (synthetic/no-PII compliance).
- Added `LICENSE` (MIT).

### Deploy
- Image `quorum-aegis:v86` live on Container App `delphai` + the static mirror.
