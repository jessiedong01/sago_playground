"""
Sago Calendar Automation

Scans Google Calendar for upcoming meetings that include hello@heysago.com.
When found, extracts meeting details and participants.
Outputs structured data for downstream automation (e.g. Brief).
"""

import os
import sys
import json
import datetime
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

SCOPES = [
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/gmail.send",
]
SAGO_EMAIL = "hello@heysago.com"
TALIPOT_DOMAIN = "talipot.com"

# Resolve credential paths relative to this file so they work
# regardless of where the script is invoked from.
_HERE = os.path.dirname(os.path.abspath(__file__))
_CREDENTIALS_PATH = os.path.join(_HERE, "credentials.json")
_TOKEN_PATH = os.path.join(_HERE, "token.json")


def get_calendar_service():
    """Authenticate and return a Google Calendar API service."""
    creds = None

    if os.path.exists(_TOKEN_PATH):
        creds = Credentials.from_authorized_user_file(_TOKEN_PATH, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(_CREDENTIALS_PATH, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(_TOKEN_PATH, "w") as token:
            token.write(creds.to_json())

    return build("calendar", "v3", credentials=creds)


def has_sago_participant(event):
    """Check if hello@heysago.com is an attendee on this event."""
    attendees = event.get("attendees", [])
    return any(a.get("email", "").lower() == SAGO_EMAIL for a in attendees)


def get_all_participants(event):
    """Extract all attendees (excluding Sago itself)."""
    attendees = event.get("attendees", [])
    return [
        {
            "email": a["email"],
            "name": a.get("displayName", ""),
            "response": a.get("responseStatus", "unknown"),
        }
        for a in attendees
        if a.get("email", "").lower() != SAGO_EMAIL
    ]


def get_external_participants(meeting_data):
    """
    Split participants into two groups:
      - talipot: those with @talipot.com addresses (Sago's client — brief recipients)
      - external: everyone else (the fund/company being met with — brief subjects)
    """
    talipot = []
    external = []
    for p in meeting_data.get("participants", []):
        domain = p["email"].split("@")[-1].lower()
        if domain == TALIPOT_DOMAIN:
            talipot.append(p)
        else:
            external.append(p)
    return talipot, external


def print_meeting(meeting_data):
    """Pretty-print a detected meeting."""
    talipot, external = get_external_participants(meeting_data)
    print(f"\n{'='*60}")
    print(f"  SAGO MEETING DETECTED")
    print(f"{'='*60}")
    print(f"  Title:     {meeting_data['summary']}")
    print(f"  Start:     {meeting_data['start']}")
    print(f"  Organizer: {meeting_data['organizer']}")
    if meeting_data.get("html_link"):
        print(f"  Link:      {meeting_data['html_link']}")
    print(f"\n  Talipot participants (brief recipients):")
    for p in talipot:
        name = f" ({p['name']})" if p["name"] else ""
        print(f"    -> {p['email']}{name}")
    print(f"\n  External participants (brief subjects):")
    for p in external:
        name = f" ({p['name']})" if p["name"] else ""
        print(f"    -> {p['email']}{name}")
    print(f"\n  --> Triggering Brief for {len(external)} external participant(s)...")
    print(f"{'='*60}\n")


def scan_upcoming_meetings(service, days_ahead=7):
    """Scan upcoming calendar events for Sago-flagged meetings."""
    now = datetime.datetime.now(datetime.UTC)
    time_min = now.isoformat()
    time_max = (now + datetime.timedelta(days=days_ahead)).isoformat()

    print(f"Scanning calendar for next {days_ahead} days...")
    print(f"Looking for events with: {SAGO_EMAIL}\n")

    events_result = (
        service.events()
        .list(
            calendarId="primary",
            timeMin=time_min,
            timeMax=time_max,
            singleEvents=True,
            orderBy="startTime",
        )
        .execute()
    )

    events = events_result.get("items", [])
    sago_meetings = []

    for event in events:
        if not has_sago_participant(event):
            continue

        start = event["start"].get("dateTime", event["start"].get("date"))
        participants = get_all_participants(event)

        meeting_data = {
            "event_id": event["id"],
            "summary": event.get("summary", "(no title)"),
            "start": start,
            "organizer": event.get("organizer", {}).get("email", ""),
            "participants": participants,
            "html_link": event.get("htmlLink", ""),
        }

        sago_meetings.append(meeting_data)
        print_meeting(meeting_data)

    if not sago_meetings:
        print("No upcoming meetings found with hello@heysago.com")

    return sago_meetings


def run_demo():
    """Run with sample data to demonstrate the automation flow."""
    print("DEMO MODE")
    print("---------\n")
    print(f"Scanning calendar for next 7 days...")
    print(f"Looking for events with: {SAGO_EMAIL}\n")

    now = datetime.datetime.now(datetime.UTC)

    demo_meetings = [
        {
            "event_id": "demo_001",
            "summary": "Talipot x Sago — Q1 Portfolio Review",
            "start": (now + datetime.timedelta(days=1, hours=2)).strftime("%Y-%m-%dT%H:%M:%S-08:00"),
            "organizer": "jessie@talipot.com",
            "participants": [
                {"email": "jessie@talipot.com", "name": "Jessie Dong", "response": "accepted"},
                {"email": "sarah.chen@talipot.com", "name": "Sarah Chen", "response": "accepted"},
                {"email": "mike.r@founderco.com", "name": "Mike Rodriguez", "response": "tentative"},
            ],
            "html_link": "https://calendar.google.com/calendar/event?eid=demo001",
        },
        {
            "event_id": "demo_002",
            "summary": "Intro: Sago <> Series A Candidate",
            "start": (now + datetime.timedelta(days=3, hours=5)).strftime("%Y-%m-%dT%H:%M:%S-08:00"),
            "organizer": "alex@sequoiacap.com",
            "participants": [
                {"email": "alex@sequoiacap.com", "name": "Alex Kim", "response": "accepted"},
                {"email": "jessie@talipot.com", "name": "Jessie Dong", "response": "accepted"},
                {"email": "founder@newstartup.ai", "name": "Jordan Lee", "response": "needsAction"},
            ],
            "html_link": "https://calendar.google.com/calendar/event?eid=demo002",
        },
    ]

    for meeting in demo_meetings:
        print_meeting(meeting)

    return demo_meetings


def main():
    print()
    print("  Sago Calendar Automation")
    print("  ========================\n")

    if "--demo" in sys.argv:
        meetings = run_demo()
    else:
        service = get_calendar_service()
        meetings = scan_upcoming_meetings(service)

    if meetings:
        output_file = os.path.join(_HERE, "sago_meetings.json")
        with open(output_file, "w") as f:
            json.dump(meetings, f, indent=2)
        print(f"Saved {len(meetings)} meeting(s) to {output_file}")


if __name__ == "__main__":
    main()
