"""
Calendar automation module.
Scans Google Calendar for meetings that include hello@heysago.com
and extracts participant data for downstream automation.
"""

from .main import get_calendar_service, scan_upcoming_meetings, get_external_participants, run_demo

__all__ = ["get_calendar_service", "scan_upcoming_meetings", "get_external_participants", "run_demo"]
