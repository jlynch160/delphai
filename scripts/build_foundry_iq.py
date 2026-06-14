"""Build the Foundry IQ knowledge index on Azure AI Search.

One-time / idempotent. Chunks the synthetic knowledge corpus exactly the way the
runtime does (via DataStore), embeds each chunk with text-embedding-3-small, and
(re)creates a vector + keyword index so the Curator / Assessment / Verifier agents
can run hybrid retrieval against real Azure AI Search — the substrate Foundry IQ
is built on.

    python scripts/build_foundry_iq.py

Reads the same env as src/connectors/foundry_iq.py. AZURE_SEARCH_KEY must be an
*admin* key here (index creation); the runtime can use a query key.
Synthetic data only — the corpus under data/knowledge/ contains no PII.
"""
from __future__ import annotations
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.data_store import get_store               # noqa: E402  (path bootstrap)
from src.connectors.foundry_iq import embed, EMBED_DIMS  # noqa: E402

from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    SearchIndex, SimpleField, SearchableField, SearchField, SearchFieldDataType,
    VectorSearch, HnswAlgorithmConfiguration, VectorSearchProfile,
    SemanticConfiguration, SemanticSearch, SemanticPrioritizedFields, SemanticField,
)


def _key(source_id: str, i: int) -> str:
    safe = "".join(c if (c.isalnum() or c in "-_") else "_" for c in source_id)
    return f"{safe}_{i}"


def build() -> None:
    endpoint = os.getenv("AZURE_SEARCH_ENDPOINT", "").strip()
    key = os.getenv("AZURE_SEARCH_KEY", "").strip()
    index_name = os.getenv("AZURE_SEARCH_INDEX", "delphai-knowledge").strip()
    if not (endpoint and key):
        sys.exit("Set AZURE_SEARCH_ENDPOINT and AZURE_SEARCH_KEY (admin key) first.")

    cred = AzureKeyCredential(key)

    # 1) chunks — identical to the runtime grounding corpus
    store = get_store()
    chunks = store.knowledge
    print(f"Chunked {len(chunks)} heading-scoped passages from data/knowledge/.")

    # 2) (re)create the index: keyword-searchable text + a 1536-d vector field
    index = SearchIndex(
        name=index_name,
        fields=[
            SimpleField(name="id", type=SearchFieldDataType.String, key=True),
            SimpleField(name="source_id", type=SearchFieldDataType.String, filterable=True, facetable=True),
            SearchableField(name="doc_title", type=SearchFieldDataType.String),
            SearchableField(name="heading", type=SearchFieldDataType.String),
            SearchableField(name="text", type=SearchFieldDataType.String),
            SearchField(
                name="vector",
                type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
                searchable=True,
                vector_search_dimensions=EMBED_DIMS,
                vector_search_profile_name="hnsw-profile",
            ),
        ],
        vector_search=VectorSearch(
            algorithms=[HnswAlgorithmConfiguration(name="hnsw")],
            profiles=[VectorSearchProfile(name="hnsw-profile", algorithm_configuration_name="hnsw")],
        ),
        semantic_search=SemanticSearch(configurations=[
            SemanticConfiguration(
                name="default",
                prioritized_fields=SemanticPrioritizedFields(
                    title_field=SemanticField(field_name="heading"),
                    content_fields=[SemanticField(field_name="text")],
                ),
            )
        ]),
    )
    idx_client = SearchIndexClient(endpoint=endpoint, credential=cred)
    idx_client.create_or_update_index(index)
    print(f"Index '{index_name}' created/updated (vector + keyword + semantic).")

    # 3) embed + upload
    docs = []
    for i, c in enumerate(chunks):
        vec = embed(c.text)
        if vec is None:
            sys.exit("Embedding failed — check AZURE_EMBED_ENDPOINT / AZURE_EMBED_KEY / deployment.")
        docs.append({
            "id": _key(c.source_id, i),
            "source_id": c.source_id,
            "doc_title": c.doc_title,
            "heading": c.heading,
            "text": c.text,
            "vector": vec,
        })
    sc = SearchClient(endpoint=endpoint, index_name=index_name, credential=cred)
    result = sc.upload_documents(documents=docs)
    ok = sum(1 for r in result if r.succeeded)
    print(f"Uploaded {ok}/{len(docs)} documents to '{index_name}'.")
    print("Foundry IQ index ready. Set the same AZURE_SEARCH_* env on the runtime.")


if __name__ == "__main__":
    build()
