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
  python pipeline.py           # live calendar scan
  python pipeline.py --demo    # demo mode (no Google auth needed)
"""

import sys
import asyncio
import re
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
    """Process all detected meetings through the Brief pipeline."""
    if not meetings:
        print("No meetings to process.")
        return

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


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    print()
    print("  Sago Brief Pipeline")
    print("  ===================\n")

    if "--demo" in sys.argv:
        meetings = run_calendar_demo()
    else:
        service = get_calendar_service()
        meetings = scan_upcoming_meetings(service)

    asyncio.run(process_meetings(meetings))


if __name__ == "__main__":
    main()
