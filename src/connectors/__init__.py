"""Ingestion connectors — the seams where synthetic data is swapped for live
Microsoft sources (Graph/Work IQ, Foundry IQ, Fabric IQ). Agents consume the
*derived shape*, never the source, so connectors swap with zero agent changes.
"""
from .graph_calendar import (CalendarConnector, SyntheticCalendarConnector,
                             GraphCalendarConnector, get_calendar_connector)

__all__ = ["CalendarConnector", "SyntheticCalendarConnector",
           "GraphCalendarConnector", "get_calendar_connector"]
