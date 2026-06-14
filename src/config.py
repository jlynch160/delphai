"""Central configuration: paths, reasoning thresholds, and model settings.

All thresholds are sourced from the synthetic knowledge docs so the reasoning is
explainable and traceable to an approved source rather than hard-coded magic numbers.
"""
from __future__ import annotations
import os
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass  # dotenv optional; env vars may be set another way

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
KNOWLEDGE_DIR = DATA_DIR / "knowledge"

# ---------------------------------------------------------------------------
# Reasoning thresholds  (traceable to KB-* synthetic documents)
# ---------------------------------------------------------------------------
PASS_PRACTICE_THRESHOLD = 75      # KB-ENABLE-001 / KB-REPORT-002
STRONG_HOURS_THRESHOLD = 20       # KB-REPORT-002 key correlation
FOCUS_TO_STUDY_RATIO = 0.40       # KB-WORKLOAD-003: ~40% of focus hours
HIGH_MEETING_LOAD = 20            # KB-WORKLOAD-003: >20 meeting hrs -> penalty
HIGH_MEETING_PENALTY = 0.70       # capacity multiplier when meeting-overloaded
SUSTAINABLE_LOAD_CEILING = 0.90   # KB-WORKLOAD-003: >90% capacity for 6+ wks = burnout
SUSTAINABLE_WEEKS_LIMIT = 6

# Readiness band cut points (probability of certifying)
BAND_EXAM_READY = 0.70
BAND_ON_TRACK = 0.45

# Negotiation target — the confidence the system tries to reach for a "GO"
GO_CONFIDENCE_TARGET = 0.80

# ---------------------------------------------------------------------------
# Model settings (Microsoft Foundry).  If no endpoint is set, the system runs
# fully offline using a deterministic demo brain — the quantitative reasoning is
# identical; only the natural-language narration differs.
# ---------------------------------------------------------------------------
AZURE_AI_PROJECT_ENDPOINT = os.getenv("AZURE_AI_PROJECT_ENDPOINT", "").strip()
AZURE_AI_MODEL_DEPLOYMENT = os.getenv("AZURE_AI_MODEL_DEPLOYMENT", "gpt-4o").strip()
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT", "").strip()
AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY", "").strip()
AZURE_OPENAI_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION", "2024-08-01-preview").strip()
