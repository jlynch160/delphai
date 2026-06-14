"""Calendar connector — the Work IQ ingestion seam.

Every agent that needs work context only ever sees a *derived* signal shape:

    {"meeting_hours_per_week", "focus_hours_per_week", "preferred_learning_slot", ...}

In the demo this is read from synthetic JSON. In production the SAME shape is
derived from a user's Outlook calendar via Microsoft Graph. Because agents consume
the derived signal — not the source — swapping the connector requires no change to
any agent (Burnout, Engagement, Skeptic).

Select the source with the WORK_IQ_SOURCE env var:  "synthetic" (default) | "graph".
"""
from __future__ import annotations
import json
import os

from .. import config


class CalendarConnector:
    """Interface: return the weekly work signal for a person."""

    def fetch_work_signal(self, person_id: str) -> dict:
        raise NotImplementedError

    def fetch_all(self) -> dict[str, dict]:
        raise NotImplementedError


class SyntheticCalendarConnector(CalendarConnector):
    """Demo connector — reads fabricated signals from work_signals.json.
    SYNTHETIC ONLY: no PII, no real calendars."""

    source_label = "SyntheticCalendarConnector (work_signals.json)"

    def __init__(self) -> None:
        raw = json.loads((config.DATA_DIR / "work_signals.json").read_text(encoding="utf-8"))
        self._by_learner = {s["learner_id"]: s for s in raw["work_signals"]}

    def fetch_all(self) -> dict[str, dict]:
        return dict(self._by_learner)

    def fetch_work_signal(self, learner_id: str) -> dict:
        return self._by_learner.get(learner_id, {})


class GraphCalendarConnector(CalendarConnector):
    """PRODUCTION PATH (stub) — derives the same work-signal shape from Outlook
    via Microsoft Graph. Not used by default: the hackathon mandates synthetic
    data. This is the exact code path a live deployment would take.

    Auth — Microsoft Entra ID. Use DefaultAzureCredential (managed identity, or the
    hosted agent's Entra *agent identity*) or a confidential-client app holding the
    Calendars.Read application permission (admin-consented, scoped down with an
    Exchange application access policy so only the relevant mailboxes are readable).

    Endpoint — calendarView expands recurring meetings across a window:
        GET https://graph.microsoft.com/v1.0/users/{id}/calendarView
            ?startDateTime={iso}&endDateTime={iso}

    Privacy — aggregate hours only (never meeting subjects/attendees). The Burnout
    agent reasons on workload, not content.
    """

    source_label = "GraphCalendarConnector (graph.microsoft.com/.../calendarView)"
    GRAPH = "https://graph.microsoft.com/v1.0"
    SCOPE = "https://graph.microsoft.com/.default"

    def __init__(self, working_hours_per_week: float = 40.0) -> None:
        self.working_hours = working_hours_per_week

    def _bearer(self) -> str:
        from azure.identity import DefaultAzureCredential  # lazy
        return DefaultAzureCredential().get_token(self.SCOPE).token

    def fetch_all(self) -> dict[str, dict]:
        # Real impl would enumerate the team's user ids (from a roster / group) and
        # call fetch_work_signal per user. Left unimplemented in the stub.
        raise NotImplementedError("Provide a team roster, then fan out fetch_work_signal per user.")

    def fetch_work_signal(self, user_id: str, start_iso: str | None = None,
                          end_iso: str | None = None) -> dict:
        import requests  # lazy
        headers = {"Authorization": f"Bearer {self._bearer()}",
                   "Prefer": 'outlook.timezone="UTC"'}
        url = (f"{self.GRAPH}/users/{user_id}/calendarView"
               f"?startDateTime={start_iso}&endDateTime={end_iso}")
        events = requests.get(url, headers=headers, timeout=30).json().get("value", [])
        return self._derive_signal(events)

    def _derive_signal(self, events: list[dict]) -> dict:
        """Aggregate a week of calendar events into the work-signal shape."""
        from datetime import datetime
        meeting_hours = 0.0
        slot_load = {"Morning": 0.0, "Afternoon": 0.0, "Evening": 0.0}
        for e in events:
            if e.get("isCancelled"):
                continue
            start = datetime.fromisoformat(e["start"]["dateTime"][:19])
            end = datetime.fromisoformat(e["end"]["dateTime"][:19])
            hours = max(0.0, (end - start).total_seconds() / 3600.0)
            meeting_hours += hours
            slot = "Morning" if start.hour < 12 else "Afternoon" if start.hour < 17 else "Evening"
            slot_load[slot] += hours
        busiest = max(slot_load, key=slot_load.get)
        preferred = {"Morning": "Afternoon", "Afternoon": "Morning", "Evening": "Morning"}[busiest]
        return {
            "meeting_hours_per_week": round(meeting_hours, 1),
            "focus_hours_per_week": round(max(0.0, self.working_hours - meeting_hours), 1),
            "preferred_learning_slot": preferred,
        }


def get_calendar_connector() -> CalendarConnector:
    """Factory: synthetic by default; live Graph when WORK_IQ_SOURCE=graph + creds exist."""
    if os.getenv("WORK_IQ_SOURCE", "synthetic").lower() == "graph":
        try:
            return GraphCalendarConnector()
        except Exception:
            pass
    return SyntheticCalendarConnector()
