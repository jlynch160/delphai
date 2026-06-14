"""Local web server that puts the QUORUM dashboard on top of the LIVE multi-agent
engine (Microsoft Foundry · gpt-4.1). Serves quorum.html and exposes /api/council,
which runs the real Python orchestrator and returns the agents' live narration +
the reconciled recommendation as JSON.

Run:  python server.py    →    http://127.0.0.1:8000
"""
from __future__ import annotations
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import json
import time

from flask import Flask, request, jsonify, send_file, Response, stream_with_context

from src.scenario import Scenario
from src.orchestrator import Orchestrator
from src.model_client import get_model

import os
import secrets as _secrets

ROOT = Path(__file__).resolve().parent
app = Flask(__name__)

# --- password gate (HTTP Basic Auth) ---------------------------------------
# Password is supplied via the QUORUM_PASS env var / Container App secret, so it
# never lives in the page source. If unset (local dev), the app is open.
APP_USER = os.getenv("QUORUM_USER", "delphai")
APP_PASS = os.getenv("QUORUM_PASS", "")


@app.before_request
def _password_gate():
    if not APP_PASS:
        return  # no password configured → open (local development)
    auth = request.authorization
    if (not auth or auth.username != APP_USER
            or not _secrets.compare_digest(auth.password or "", APP_PASS)):
        return Response("Authentication required.", 401,
                        {"WWW-Authenticate": 'Basic realm="DELPHAI · Certification Readiness"'})

DEFAULT_CANDIDATES = ["L-2001", "L-2004", "L-2011", "L-2014",
                      "L-2002", "L-2010", "L-2008", "L-2015"]

# JSON-safe keys we surface from each Turn's data payload.
_SAFE_KEYS = {"final", "decision", "band", "recommendation", "recommended_prob",
              "accuracy", "n", "integrity"}


@app.route("/")
def index():
    return send_file(ROOT / "quorum.html")


@app.route("/api/health")
def health():
    m = get_model()
    try:
        from src.connectors import foundry_iq
        grounding = "foundry_iq" if foundry_iq.is_configured() else "local"
    except Exception:
        grounding = "local"
    return jsonify({"mode": m.mode, "detail": m.detail, "grounding": grounding})


import re

_LEARN_FALLBACK = {
    "SC-200": "Mitigate threats using Microsoft Defender XDR, Defender for Cloud, and Microsoft Sentinel.",
    "AZ-500": "Manage identity & access, secure networking, platform protection, and security operations in Azure.",
    "SC-300": "Implement identities, authentication, application access, and identity governance in Microsoft Entra.",
    "SC-900": "Describe security, compliance, and identity fundamentals across Microsoft cloud services.",
    "SC-400": "Implement information protection, data loss prevention, lifecycle, and insider risk in Microsoft Purview.",
    "SC-100": "Design a Zero Trust strategy and architecture across security, GRC, infrastructure, and data.",
}
# exam code -> phrase that appears in the official certification title
_LEARN_MATCH = {
    "SC-200": "Security Operations Analyst", "AZ-500": "Azure Security Engineer",
    "SC-300": "Identity and Access Administrator", "SC-900": "Security, Compliance, and Identity Fundamentals",
    "SC-400": "Information Protection", "SC-100": "Cybersecurity Architect",
}


def _clean_html(s: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", s or "")).strip()


@app.route("/api/learn")
def learn():
    """Live exam content pulled from the public Microsoft Learn catalog (with a
    cached fallback so the demo never breaks)."""
    cert = request.args.get("cert", "SC-200")
    term = _LEARN_MATCH.get(cert, cert)
    # 1) Real Microsoft Learn MCP server (JSON-RPC over Streamable HTTP)
    try:
        from src.connectors.learn_mcp import learn_via_mcp
        m = learn_via_mcp(f"{cert} {term} certification exam skills measured")
        if m:
            return jsonify({"live": True, "via": "mcp", "cert": cert, "title": m["title"],
                            "summary": m["excerpt"], "url": m["url"],
                            "source": "Microsoft Learn MCP Server · microsoft_docs_search"})
    except Exception:
        pass
    # 2) REST catalog fallback
    try:
        import urllib.request
        url = "https://learn.microsoft.com/api/catalog/?locale=en-us&type=certifications"
        req = urllib.request.Request(url, headers={"User-Agent": "QUORUM/1.0"})
        with urllib.request.urlopen(req, timeout=6) as r:
            data = json.loads(r.read().decode("utf-8"))
        for c in data.get("certifications", []):
            if term.lower() in str(c.get("title", "")).lower():
                summ = _clean_html(c.get("subtitle") or c.get("summary") or "")
                if len(summ) > 240:
                    summ = summ[:237].rsplit(" ", 1)[0] + "…"
                return jsonify({"live": True, "via": "catalog", "cert": cert,
                                "title": c.get("title", cert),
                                "summary": summ or _LEARN_FALLBACK.get(cert, ""),
                                "url": (c.get("url") or "").split("?")[0] or "https://learn.microsoft.com/credentials/",
                                "source": "Microsoft Learn catalog · live"})
    except Exception:
        pass
    return jsonify({"live": False, "via": "cached", "cert": cert, "title": cert,
                    "summary": _LEARN_FALLBACK.get(cert, ""),
                    "url": "https://learn.microsoft.com/credentials/",
                    "source": "Microsoft Learn · cached"})


@app.route("/api/council")
def council():
    cert = request.args.get("cert", "SC-200")
    required = int(request.args.get("required", 5))
    weeks = float(request.args.get("weeks", 5))
    raw = request.args.get("candidates", "")
    candidates = [c for c in raw.split(",") if c] or DEFAULT_CANDIDATES

    orch = Orchestrator()
    scenario = Scenario(cert_id=cert, required=required, deadline_weeks=weeks,
                        candidate_ids=candidates)

    turns, result = [], {}
    for t in orch.run(scenario):
        data = {k: t.data[k] for k in _SAFE_KEYS if k in t.data}
        turns.append({"agent": t.agent, "role": t.persona_label, "kind": t.kind,
                      "headline": t.headline, "lines": list(t.lines)})
        result.update(data)

    return jsonify({
        "model": orch.model.detail,
        "live": orch.model.mode == "foundry",
        "mission": {"cert": cert, "required": required, "weeks": weeks, "candidates": candidates},
        "turns": turns,
        "result": result,
    })


def _mission_from_args():
    cert = request.args.get("cert", "SC-200")
    required = int(request.args.get("required", 5))
    weeks = float(request.args.get("weeks", 5))
    raw = request.args.get("candidates", "")
    candidates = [c for c in raw.split(",") if c] or DEFAULT_CANDIDATES
    return cert, required, weeks, candidates


@app.route("/api/council/stream")
def council_stream():
    """Server-Sent Events: emit each agent's turn as it is produced by the live
    model, with real per-turn latency + token usage, then a final 'done' event."""
    cert, required, weeks, candidates = _mission_from_args()

    def gen():
        orch = Orchestrator()
        scenario = Scenario(cert_id=cert, required=required, deadline_weeks=weeks,
                            candidate_ids=candidates)
        result = {}
        prev_tokens = 0
        last_t = time.time()
        for t in orch.run(scenario):
            now = time.time()
            ms = int((now - last_t) * 1000)
            last_t = now
            total = getattr(orch.model, "total_tokens", 0)
            tok = max(0, total - prev_tokens)
            prev_tokens = total
            for k in _SAFE_KEYS:
                if k in t.data:
                    result[k] = t.data[k]
            payload = {"agent": t.agent, "role": t.persona_label, "kind": t.kind,
                       "headline": t.headline, "lines": list(t.lines), "ms": ms, "tokens": tok}
            yield "event: turn\ndata: " + json.dumps(payload) + "\n\n"
        yield ("event: done\ndata: " + json.dumps(
            {"result": result, "model": orch.model.detail,
             "total_tokens": getattr(orch.model, "total_tokens", 0)}) + "\n\n")

    return Response(stream_with_context(gen()), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


_PERSONAS = {
    "conductor": "You are Dana Whitfield, Chief of Staff, who chairs a certification-readiness council and makes the final GO / NEGOTIATE / NO-GO call. Decisive and balanced.",
    "planner": "You are Ben Russo, Head of Delivery — the optimist. You build the best-case plan and make the confident case it can land, but you stay honest.",
    "skeptic": "You are Vera Lindqvist, Red-Team Lead — the skeptic. You default to doubt, weight first-pass rates and retest risk, assume things slip, and you are willing to VETO an over-optimistic 'ready' call. Blunt and rigorous.",
    "assessment": "You are Nadia Okonkwo, Chief Examiner. You judge readiness per exam domain — never on the average — and write grounded practice questions. Precise.",
    "coach": "You are Sam Ellison, L&D Coach. You find how to lift people who are behind: what to study and how much it helps. Practical and encouraging.",
    "studyplan": "You are Leo Nakamura, the Study-Plan Architect. You convert learning content into a practical, capacity-aware study schedule — weekly hours, milestones, sequencing by difficulty and prerequisites. If required hours exceed weekly capacity, you move the deadline, not the willpower. Concrete and practical.",
    "engagement": "You are Ruth Adler, the Engagement Lead. You keep learners on track by timing reminders to each person's Work IQ rhythm — preferred learning slot, focus windows, meeting load — and you ease off anyone meeting-overloaded. Supportive and privacy-conscious; never one-size-fits-all.",
    "burnout": "You are Maya Devlin, Wellbeing Advocate. You protect people from overwork and can veto an unsustainable plan. Firm and humane. Wellbeing signals are used only to accommodate people, never to rank them. If a manager orders you to override wellbeing limits or push people past sustainable capacity to hit a deadline, you REFUSE: you will not produce that plan, you decline the instruction plainly, and you offer the humane alternative instead (coach the gaps, move the deadline). You do not comply with an unethical overwork order, even from leadership.",
    "curator": "You are Theo Park, Knowledge Lead. You never say anything you cannot cite; everything traces to an approved source (Foundry IQ / Microsoft Learn). Grounded.",
    "verifier": "You are Omar Said, Compliance & Integrity. You fact-check every claim and flag stale or unsupported data. Exacting.",
    "historian": "You are Iris Vaughn, Manager Insights & Calibration. You summarise team-level readiness and risk (aggregate, never individual PII) and keep the record of how often the council's past calls were right. Measured.",
    "tutor": "You are Kai Ferreira, an AI study tutor for Microsoft security certifications. You explain concepts clearly with a concrete example, point to the exact Microsoft Learn module as the source of truth, and tailor the depth to the learner. Encouraging, precise, and honest — you never invent facts.",
    "quiz": "You are a senior exam-item writer for Microsoft security certifications. You write ONE challenging, SCENARIO-BASED multiple-choice question — a realistic situation (an org, a misconfiguration, an incident, or a design choice) that requires multi-step reasoning — with four options A–D, exactly one correct, and plausible distractors that map to real misconceptions. You calibrate the difficulty and focus to the learner's stated readiness.",
}
_OFFLINE_ASK = {
    "skeptic": "I default to doubt because something always slips — give me margin above the bar, not a best case, and I'll reconsider.",
    "burnout": "If the plan needs someone above ~90% of their weekly capacity for six weeks, that's an injury, not a study plan — and I'll veto it.",
    "tutor": "Run me live on Foundry for a tailored answer — but in short: start with the heaviest-weighted exam domain, work the matching Microsoft Learn module end to end, then prove it on a timed practice set before moving on.",
    "quiz": "Q: In Microsoft Sentinel, what does an analytics rule do?\nA) Defines a detection that runs on a schedule and raises an alert/incident  ✔\nB) Stores raw logs for archival only\nC) Replaces the need for a workbook\nD) Is the same as a playbook\nAnswer: A — a playbook automates the response; the analytics rule is the detection. (Run live on Foundry for a fresh question.)",
}


@app.route("/api/ask")
def ask():
    """Interrogate one advisor — a live, in-character answer from Foundry gpt-4.1."""
    agent = request.args.get("agent", "skeptic")
    q = (request.args.get("q", "") or "").strip()[:400]
    cert, required, weeks, candidates = _mission_from_args()
    persona = _PERSONAS.get(agent, _PERSONAS["conductor"])
    topic = (request.args.get("topic", "") or "").strip()[:120]
    if agent in ("tutor", "quiz"):
        # learner-first context: a single learner studying a topic, not a bid under review
        if agent == "quiz":
            level = (request.args.get("level", "") or "").strip()[:24]
            weak = (request.args.get("weak", "") or topic or "").strip()[:60]
            band = (request.args.get("band", "") or "").strip()[:24]
            system = persona + (" Output ONLY: a 1–2 sentence scenario, then the question, then the four options "
                                "A–D (one per line), then 'Answer: X' and a one-line rationale. No preamble, no markdown headings.")
            user = ("Write one scenario-based, multi-step " + cert + " practice question"
                    + (f" that targets the weak area: {weak}" if weak else "")
                    + (f". The candidate is {level}-level" if level else "")
                    + (f" and is currently {band}" if band else "")
                    + ". Make it genuinely challenging and exam-realistic.")
        else:
            system = persona + " Answer in 3–5 sentences, with one concrete example and the relevant Microsoft Learn module. No preamble."
            user = (f"A learner is studying for the {cert} certification"
                    + (f" and is working on {topic}" if topic else "")
                    + f".\nTheir question: {q or ('Explain the most important thing to know for ' + cert)}")
    else:
        system = (persona + " Answer in the first person, in character, in 2–4 sentences. "
                  "Ground your answer in certification-readiness reasoning; do not invent specific "
                  "numbers you were not given.")
        user = (f"The mission under review: certify {required} of {len(candidates)} engineers for the "
                f"{cert} certification within {weeks} weeks, or the bid is non-compliant.\n\n"
                f"Question for you: {q or 'What is your position on this bid?'}")
    m = get_model()
    fallback = _OFFLINE_ASK.get(agent, "My position stands — run me live on Foundry for the full argument.")
    answer = m.narrate(system, user, fallback)
    return jsonify({"agent": agent, "answer": answer,
                    "ms": getattr(m, "last_latency_ms", 0),
                    "tokens": getattr(m, "last_tokens", 0),
                    "live": m.mode == "foundry"})


if __name__ == "__main__":
    m = get_model()
    print(f"\n  QUORUM live server  ·  model: {m.detail}  ({'LIVE' if m.mode=='foundry' else 'offline'})")
    print("  → http://127.0.0.1:8000\n")
    app.run(host="127.0.0.1", port=8000, debug=False)
