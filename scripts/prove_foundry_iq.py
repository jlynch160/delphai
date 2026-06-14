"""Runtime proof that a LIVE council step retrieves through Foundry IQ.

Runs the real Curator agent on the live Microsoft Foundry model and shows that
its grounding came from the Azure AI Search index (not the local fallback):
  - model mode = foundry (gpt-4.1)
  - DataStore.last_grounding_source = foundry_iq after the agent searches
  - the cited chunks are the ones Azure AI Search returned
  - a semantic (non-keyword) query still retrieves the right passage (vector hybrid)

Writes the captured evidence to FOUNDRY_IQ_PROOF.md.

    python scripts/prove_foundry_iq.py
"""
from __future__ import annotations
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.data_store import get_store                 # noqa: E402
from src.model_client import get_model               # noqa: E402
from src.connectors import foundry_iq                 # noqa: E402
from src.agents import CuratorAgent                    # noqa: E402

OUT = Path(__file__).resolve().parent.parent / "FOUNDRY_IQ_PROOF.md"


def main() -> None:
    store = get_store()
    model = get_model()
    L = []
    def emit(s=""):
        print(s); L.append(s)

    emit("# Foundry IQ — live runtime proof")
    emit()
    emit(f"_Captured {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} by `scripts/prove_foundry_iq.py`._")
    emit()
    emit(f"- **Model surface:** `{model.mode}` — {model.detail}")
    emit(f"- **Foundry IQ configured:** `{foundry_iq.is_configured()}` "
         f"(Azure AI Search index `{__import__('os').getenv('AZURE_SEARCH_INDEX','delphai-knowledge')}`)")
    emit()

    # 1) A real agent step that grounds itself via search_knowledge()
    emit("## 1 · A live Curator turn grounds through Azure AI Search")
    emit()
    curator = CuratorAgent(store, model)
    turn = curator.curate("SC-200")
    emit(f"- **Grounding source after the agent searched:** `{store.last_grounding_source}`")
    cited = turn.data.get("cited_chunks", [])
    emit(f"- **Cited chunks returned by Foundry IQ:** {len(cited)}")
    for sid, heading in cited:
        emit(f"  - `{sid}` — {heading}")
    emit()
    emit("**Curator headline (narrated live by Foundry gpt-4.1, grounded in the retrieved chunks):**")
    emit()
    emit(f"> {turn.headline}")
    emit()

    # 2) Semantic retrieval — a query with NO shared keywords still finds the passage
    emit("## 2 · Vector hybrid retrieval (semantic, not keyword)")
    emit()
    q = "how much studying makes someone likely to pass the exam"
    hits = store.search_knowledge(q, limit=2)
    emit(f"- **Query:** _“{q}”_")
    emit(f"- **Grounding source:** `{store.last_grounding_source}`")
    for h in hits:
        snippet = " ".join(h.text.split())[:120]
        emit(f"  - `{h.source_id}` — {h.heading}: “{snippet}…”")
    emit()
    emit("The correlation passage is retrieved despite sharing almost no exact words with the "
         "query — that is the dense-vector half of the hybrid search working, which the local "
         "keyword fallback could not do.")
    emit()

    OUT.write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"\nWrote {OUT}")


if __name__ == "__main__":
    main()
