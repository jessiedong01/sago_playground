"""
Sago Brief Pipeline

End-to-end automation:
  1. Scan Google Calendar for meetings that include hello@heysago.com
  2. For each meeting, identify:
       - Talipot participants  (@talipot.com)  — the brief recipients
       - External participants (everyone else) — the entities to research
  3. Derive the fund/company name to research from the external participants
  4. Run the Brief agent to generate a PDF research report
  5. Print a delivery summary (email sending can be wired in below)

Usage:
  python pipeline.py                    # single run: scan once, process, exit
  python pipeline.py --watch             # continuous: scan every N min, process new meetings only
  python pipeline.py --watch --interval 300   # scan every 300 seconds (default: 300)
  python pipeline.py --demo              # single run with fake calendar data
  python pipeline.py --demo --watch      # continuous + demo data (new meetings simulated once)
"""

import sys
import asyncio
import re
import argparse
from pathlib import Path

# ---------------------------------------------------------------------------
# Calendar module
# ---------------------------------------------------------------------------
from sago_cal import (
    get_calendar_service,
    scan_upcoming_meetings,
    get_external_participants,
    run_demo as run_calendar_demo,
)

# ---------------------------------------------------------------------------
# Brief agent
# ---------------------------------------------------------------------------
from google.adk.sessions import InMemorySessionService
from google.adk.runners import Runner
from google.genai import types
from brief.agent import root_agent


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def derive_research_target(meeting_data, external_participants):
    """
    Best-effort extraction of a fund/company name to pass to the Brief agent.

    Priority:
      1. Meeting title (e.g. "Talipot x Sequoia — Q1 Review" → "Sequoia")
      2. External participant email domain (e.g. sequoiacap.com → "Sequoia Capital")
    """
    title = meeting_data.get("summary", "")

    # Try to extract after common separators in meeting titles
    for sep in [" x ", " <> ", " — ", " - ", " with ", " : "]:
        parts = title.split(sep)
        if len(parts) >= 2:
            # Return the part that isn't obviously Talipot or Sago
            for part in parts:
                clean = part.strip().split("—")[0].split("-")[0].strip()
                low = clean.lower()
                if "talipot" not in low and "sago" not in low and len(clean) > 2:
                    return clean

    # Fall back to the first external participant's email domain
    if external_participants:
        domain = external_participants[0]["email"].split("@")[-1]
        # Strip TLD and capitalise: sequoiacap.com → Sequoiacap
        name = domain.split(".")[0].capitalize()
        return name

    return title  # last resort: use full title


async def run_brief_for_meeting(meeting_data, external_participants, talipot_participants):
    """Invoke the Brief agent for a single meeting and return the output."""
    target = derive_research_target(meeting_data, external_participants)
    meeting_title = meeting_data["summary"]
    meeting_start = meeting_data["start"]

    # Build the prompt for the orchestrator
    external_names = ", ".join(
        p["name"] or p["email"] for p in external_participants
    )
    prompt = (
        f"Generate a briefing for: {target}\n\n"
        f"Context: Upcoming meeting — '{meeting_title}' on {meeting_start}.\n"
        f"External attendees: {external_names}.\n"
        f"Prepared for: Talipot Investment Team"
    )

    print(f"\n  Researching: {target}")
    print(f"  Prompt: {prompt[:120]}...")

    session_service = InMemorySessionService()
    session = await session_service.create_session(
        app_name="sago_pipeline",
        user_id="sago",
        session_id=meeting_data["event_id"],
    )

    runner = Runner(
        agent=root_agent,
        app_name="sago_pipeline",
        session_service=session_service,
    )

    final_response = None
    async for event in runner.run_async(
        user_id="sago",
        session_id=session.id,
        new_message=types.Content(
            role="user",
            parts=[types.Part(text=prompt)],
        ),
    ):
        if event.is_final_response():
            final_response = event.content.parts[0].text if event.content else ""

    return target, final_response


async def process_meetings(meetings):
    """Process meetings through the Brief pipeline. Returns set of event_ids that were processed."""
    processed_ids = set()
    if not meetings:
        return processed_ids

    for meeting in meetings:
        talipot, external = get_external_participants(meeting)

        if not talipot:
            print(f"  Skipping '{meeting['summary']}' — no talipot.com participants.")
            continue

        if not external:
            print(f"  Skipping '{meeting['summary']}' — no external participants to research.")
            continue

        print(f"\n{'='*60}")
        print(f"  Processing: {meeting['summary']}")
        print(f"  Brief recipients (talipot.com):")
        for p in talipot:
            print(f"    -> {p['email']}")
        print(f"  Research targets (external):")
        for p in external:
            print(f"    -> {p['email']}")

        try:
            target, response = await run_brief_for_meeting(meeting, external, talipot)
            processed_ids.add(meeting["event_id"])

            print(f"\n  Brief generated for: {target}")
            print(f"  To be sent to:")
            for p in talipot:
                print(f"    -> {p['email']} ({p['name'] or 'no name'})")

            # ----------------------------------------------------------------
            # Email delivery hook
            # Uncomment and configure to actually send the PDF via email.
            # ----------------------------------------------------------------
            # from email_utils import send_brief_email
            # pdf_path = find_latest_pdf()   # Brief agent saves PDF to disk
            # for p in talipot:
            #     send_brief_email(
            #         to=p["email"],
            #         name=p["name"],
            #         meeting_title=meeting["summary"],
            #         pdf_path=pdf_path,
            #     )
            # ----------------------------------------------------------------

            if response:
                print(f"\n  Agent summary:\n  {response[:300]}...")

        except Exception as e:
            print(f"  ERROR generating brief for '{meeting['summary']}': {e}")

    print(f"\n{'='*60}")
    print("  Pipeline complete.")
    print(f"{'='*60}\n")
    return processed_ids


# ---------------------------------------------------------------------------
# Watch loop: scan periodically, process only new meetings
# ---------------------------------------------------------------------------

async def run_watch(demo: bool, interval_seconds: int):
    """Continuously scan for meetings and run the brief for any that haven't been processed yet."""
    processed_ids = set()
    service = None if demo else get_calendar_service()

    print(f"  Watch mode: scanning every {interval_seconds}s. Ctrl+C to stop.\n")

    while True:
        if demo:
            meetings = run_calendar_demo()
        else:
            meetings = scan_upcoming_meetings(service)

        new_meetings = [m for m in meetings if m["event_id"] not in processed_ids]
        if new_meetings:
            print(f"  Found {len(new_meetings)} new meeting(s) to process.")
            processed_ids |= await process_meetings(new_meetings)
        else:
            if meetings:
                print(f"  No new meetings (all {len(meetings)} already processed). Next scan in {interval_seconds}s.")
            else:
                print("  No meetings found. Next scan in {}s.".format(interval_seconds))

        await asyncio.sleep(interval_seconds)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Sago Brief Pipeline")
    parser.add_argument("--demo", action="store_true", help="Use fake calendar data (no Google auth)")
    parser.add_argument("--watch", action="store_true", help="Run continuously; scan for new meetings every --interval seconds")
    parser.add_argument("--interval", type=int, default=300, metavar="SECS", help="Seconds between calendar scans in watch mode (default: 300)")
    args = parser.parse_args()

    print()
    print("  Sago Brief Pipeline")
    print("  ===================\n")

    if args.watch:
        asyncio.run(run_watch(demo=args.demo, interval_seconds=args.interval))
    else:
        if args.demo:
            meetings = run_calendar_demo()
        else:
            service = get_calendar_service()
            meetings = scan_upcoming_meetings(service)
        asyncio.run(process_meetings(meetings))


if __name__ == "__main__":
    main()
