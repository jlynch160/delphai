"""Foundry IQ grounding — real **Azure AI Search** hybrid retrieval.

This is the production grounding layer for the Curator / Assessment / Verifier
agents. It runs *hybrid* retrieval (BM25 keyword **+** dense vector, fused by
Azure AI Search's reciprocal-rank fusion) over an index built from the synthetic
knowledge corpus. Azure AI Search is the same indexing/retrieval substrate that
Microsoft Foundry IQ is built on, so this turns the earlier local stand-in into a
genuine Foundry IQ integration.

Design rule (matches `learn_mcp`): **never break the demo.** If the service is
unconfigured, the package is missing, or any call fails, every function returns
None / [] so `DataStore.search_knowledge` transparently falls back to the local
keyword corpus and the offline demo still runs.

Env (set as Container App secrets; blank locally = offline):
    AZURE_SEARCH_ENDPOINT      https://delphai-search.search.windows.net
    AZURE_SEARCH_KEY           <query or admin key>
    AZURE_SEARCH_INDEX         delphai-knowledge  (default)
    AZURE_EMBED_ENDPOINT       https://quorum-foundry-jl.openai.azure.com/
    AZURE_EMBED_KEY            <Azure OpenAI / AIServices key>
    AZURE_EMBED_DEPLOYMENT     text-embedding-3-small  (default)
    AZURE_EMBED_API_VERSION    2024-08-01-preview      (default)
"""
from __future__ import annotations
import os

EMBED_DIMS = 1536  # text-embedding-3-small


def _search_cfg() -> tuple[str, str, str]:
    return (
        os.getenv("AZURE_SEARCH_ENDPOINT", "").strip(),
        os.getenv("AZURE_SEARCH_KEY", "").strip(),
        os.getenv("AZURE_SEARCH_INDEX", "delphai-knowledge").strip(),
    )


def _embed_cfg() -> tuple[str, str, str, str]:
    return (
        (os.getenv("AZURE_EMBED_ENDPOINT") or os.getenv("AZURE_OPENAI_ENDPOINT") or "").strip(),
        (os.getenv("AZURE_EMBED_KEY") or os.getenv("AZURE_OPENAI_API_KEY") or "").strip(),
        os.getenv("AZURE_EMBED_DEPLOYMENT", "text-embedding-3-small").strip(),
        os.getenv("AZURE_EMBED_API_VERSION", "2024-08-01-preview").strip(),
    )


def is_configured() -> bool:
    """True when a real Azure AI Search endpoint + key are present."""
    ep, key, _ = _search_cfg()
    return bool(ep and key)


def embed(text: str) -> list[float] | None:
    """Embed a query with Azure OpenAI; None on any failure (→ text-only search)."""
    ep, key, deployment, api_version = _embed_cfg()
    if not (ep and key):
        return None
    try:
        from openai import AzureOpenAI
        client = AzureOpenAI(azure_endpoint=ep, api_key=key, api_version=api_version)
        resp = client.embeddings.create(model=deployment, input=text[:8000])
        return resp.data[0].embedding
    except Exception:
        return None


def retrieve(query: str, limit: int = 3) -> list[dict]:
    """Hybrid (vector + keyword) retrieval against Azure AI Search.

    Returns a list of dicts {source_id, doc_title, heading, text}; [] on any
    failure so the caller falls back to the local corpus. Degrades gracefully:
    hybrid → keyword-only (if embedding fails) → [] (if the service is down).
    """
    ep, key, index = _search_cfg()
    query = (query or "").strip()
    if not (ep and key and query):
        return []
    try:
        from azure.search.documents import SearchClient
        from azure.core.credentials import AzureKeyCredential

        client = SearchClient(endpoint=ep, index_name=index, credential=AzureKeyCredential(key))
        kwargs: dict = {
            "search_text": query,
            "top": limit,
            "select": ["source_id", "doc_title", "heading", "text"],
        }
        vec = embed(query)
        if vec is not None:
            try:
                from azure.search.documents.models import VectorizedQuery
                kwargs["vector_queries"] = [
                    VectorizedQuery(vector=vec, k_nearest_neighbors=max(limit, 3), fields="vector")
                ]
            except Exception:
                pass  # keyword-only is still a real Azure AI Search query
        results = client.search(**kwargs)
        out: list[dict] = []
        for r in results:
            out.append({
                "source_id": r.get("source_id") or "KB",
                "doc_title": r.get("doc_title") or "",
                "heading": r.get("heading") or "Overview",
                "text": r.get("text") or "",
            })
            if len(out) >= limit:
                break
        return out
    except Exception:
        return []
