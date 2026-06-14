"""Minimal client for the **Microsoft Learn MCP Server** (the real MCP protocol,
not the REST catalog). Speaks JSON-RPC 2.0 over Streamable HTTP:

    initialize  ->  notifications/initialized  ->  tools/call(microsoft_docs_search)

Returns the top documentation chunk (title / excerpt / url) for a query, or None on
any failure so callers can fall back gracefully. Stdlib only — no extra deps.

Endpoint + protocol confirmed live against https://learn.microsoft.com/api/mcp
(serverInfo: "Microsoft Learn MCP Server", protocolVersion 2025-06-18).
"""
from __future__ import annotations
import json
import re
import urllib.request

MCP_ENDPOINT = "https://learn.microsoft.com/api/mcp"
PROTOCOL_VERSION = "2025-06-18"


def _post(body: dict, session: str | None, timeout: float):
    data = json.dumps(body).encode("utf-8")
    headers = {"Content-Type": "application/json",
               "Accept": "application/json, text/event-stream"}
    if session:
        headers["Mcp-Session-Id"] = session
    req = urllib.request.Request(MCP_ENDPOINT, data=data, headers=headers, method="POST")
    return urllib.request.urlopen(req, timeout=timeout)


def _parse(raw: str):
    """The transport returns either raw JSON or an SSE 'data:' frame."""
    raw = (raw or "").strip()
    if raw.startswith("{"):
        try:
            return json.loads(raw)
        except Exception:
            return None
    for line in raw.splitlines():
        if line.startswith("data:"):
            try:
                return json.loads(line[5:].strip())
            except Exception:
                continue
    return None


def _clean(md: str, limit: int = 240) -> str:
    """Trim a markdown chunk to a short plain-text excerpt."""
    txt = re.sub(r"^#.*$", "", md or "", flags=re.MULTILINE)      # drop heading lines
    txt = re.sub(r"[#*`>\-]", " ", txt)
    txt = re.sub(r"\s+", " ", txt).strip()
    if len(txt) > limit:
        txt = txt[: limit - 1].rsplit(" ", 1)[0] + "…"
    return txt


def learn_via_mcp(query: str, timeout: float = 9.0) -> dict | None:
    """Run microsoft_docs_search over MCP and return the best chunk, or None."""
    try:
        # 1) initialize -> session id
        r = _post({"jsonrpc": "2.0", "id": 1, "method": "initialize",
                   "params": {"protocolVersion": PROTOCOL_VERSION, "capabilities": {},
                              "clientInfo": {"name": "quorum", "version": "1.0"}}},
                  None, timeout)
        session = r.headers.get("Mcp-Session-Id")
        _parse(r.read().decode("utf-8", "replace"))
        # 2) initialized notification (best-effort)
        try:
            _post({"jsonrpc": "2.0", "method": "notifications/initialized"}, session, timeout).read()
        except Exception:
            pass
        # 3) tools/call microsoft_docs_search
        r3 = _post({"jsonrpc": "2.0", "id": 3, "method": "tools/call",
                    "params": {"name": "microsoft_docs_search", "arguments": {"query": query}}},
                   session, timeout)
        msg = _parse(r3.read().decode("utf-8", "replace"))
        content = (msg or {}).get("result", {}).get("content", [])
        if not content:
            return None
        text = content[0].get("text", "")
        try:
            payload = json.loads(text)
            results = payload.get("results", []) if isinstance(payload, dict) else []
        except Exception:
            results = []
        if not results:
            return None
        top = results[0]
        return {
            "title": top.get("title") or "Microsoft Learn",
            "excerpt": _clean(top.get("content", "")),
            "url": top.get("contentUrl") or top.get("url") or "https://learn.microsoft.com",
            "tool": "microsoft_docs_search",
            "server": "Microsoft Learn MCP Server",
        }
    except Exception:
        return None
