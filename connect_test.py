"""Quick check that the live Microsoft Foundry model is wired up.
Run:  python connect_test.py
"""
import sys
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from src.model_client import get_model

m = get_model()
print("mode  :", m.mode)
print("detail:", m.detail)
print("-" * 50)
out = m.narrate(
    "You are the Skeptic agent on a certification-readiness council. Terse and sharp.",
    "In ONE short sentence, confirm the model connection works and mention the cert SC-200.",
    "[OFFLINE FALLBACK — model not connected]",
)
print("model says:", out)
print("-" * 50)
print("RESULT:", "LIVE FOUNDRY ✓" if m.mode == "foundry" and "FALLBACK" not in out else "still offline ✗")
