"""
Calendar + Zoom integration. The agent decides whether to add a Zoom link
based on context from the email, or honors explicit overrides like
'book in-person', 'book phone call', 'book Zoom'.
"""

from datetime import datetime, timedelta
import base64
import requests

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from gmail_tools import get_gmail_service
import config


def _get_calendar_service():
    """Reuses Gmail's auth flow — both APIs share the same OAuth scopes."""
    gmail_service = get_gmail_service()
    creds = gmail_service._http.credentials
    return build("calendar", "v3", credentials=creds)


# ============================================================
# ZOOM
# ============================================================

def _get_zoom_access_token() -> str:
    """Server-to-Server OAuth: get a fresh access token for Zoom API."""
    auth = base64.b64encode(
        f"{config.ZOOM_CLIENT_ID}:{config.ZOOM_CLIENT_SECRET}".encode()
    ).decode()

    response = requests.post(
        "https://zoom.us/oauth/token",
        params={
            "grant_type": "account_credentials",
            "account_id": config.ZOOM_ACCOUNT_ID,
        },
        headers={"Authorization": f"Basic {auth}"},
    )
    response.raise_for_status()
    return response.json()["access_token"]


def create_zoom_meeting(topic: str, start_time: datetime, duration_minutes: int = 30) -> dict:
    """Create a Zoom meeting. Returns dict with join_url, meeting_id."""
    token = _get_zoom_access_token()
    response = requests.post(
        "https://api.zoom.us/v2/users/me/meetings",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        json={
            "topic": topic,
            "type": 2,  # scheduled
            "start_time": start_time.strftime("%Y-%m-%dT%H:%M:%S"),
            "duration": duration_minutes,
            "timezone": config.TIMEZONE,
            "settings": {
                "join_before_host": True,
                "waiting_room": False,
                "mute_upon_entry": False,
            },
        },
    )
    response.raise_for_status()
    data = response.json()
    return {"join_url": data["join_url"], "meeting_id": data["id"]}


# ============================================================
# Meeting-type inference
# ============================================================

def infer_meeting_type(email_body: str, override: str = None) -> str:
    """
    Returns one of: 'zoom', 'in_person', 'phone'.
    If override is provided ('zoom', 'in_person', 'phone'), it wins.
    Otherwise infers from email keywords.
    """
    if override:
        return override

    body_lower = email_body.lower()

    # Phone-call signals
    phone_signals = [
        "give me a call", "phone call", "call me", "phone catch-up",
        "i'll call you", "ring me", "give you a call",
    ]
    if any(sig in body_lower for sig in phone_signals):
        return "phone"

    # In-person signals
    in_person_signals = [
        "coffee", "lunch", "dinner", "drinks", "let's meet at",
        "stop by", "come to my office", "in-person", "in person",
        "at my place", "at the office", "grab a bite", "meet up at",
    ]
    if any(sig in body_lower for sig in in_person_signals):
        return "in_person"

    # Default to Zoom for ambiguous "let's meet" / "let's chat"
    return "zoom"


# ============================================================
# Calendar event creation
# ============================================================

def create_calendar_event(
    title: str,
    start_time: datetime,
    duration_minutes: int = 30,
    attendee_email: str = None,
    meeting_type: str = "zoom",
    location: str = None,
    description: str = "",
) -> dict:
    """
    Create a Google Calendar event. Returns dict with event_link and meeting info.
    """
    service = _get_calendar_service()
    end_time = start_time + timedelta(minutes=duration_minutes)

    event_body = {
        "summary": title,
        "start": {
            "dateTime": start_time.isoformat(),
            "timeZone": config.TIMEZONE,
        },
        "end": {
            "dateTime": end_time.isoformat(),
            "timeZone": config.TIMEZONE,
        },
        "description": description,
    }

    if attendee_email:
        event_body["attendees"] = [{"email": attendee_email}]

    zoom_info = None
    if meeting_type == "zoom":
        try:
            zoom_info = create_zoom_meeting(title, start_time, duration_minutes)
            event_body["description"] = (
                f"Zoom meeting: {zoom_info['join_url']}\n\n"
                f"Meeting ID: {zoom_info['meeting_id']}\n\n"
                f"{description}"
            ).strip()
            event_body["location"] = zoom_info["join_url"]
        except Exception as e:
            print(f"Zoom create failed, falling back to no-link event: {e}")
            event_body["description"] = (
                f"(Zoom auto-create failed — add link manually)\n\n{description}"
            ).strip()

    elif meeting_type == "in_person":
        if location:
            event_body["location"] = location
        event_body["description"] = (
            f"In-person meeting{' at ' + location if location else ''}.\n\n{description}"
        ).strip()

    elif meeting_type == "phone":
        event_body["description"] = (
            f"Phone call.\n\n{description}"
        ).strip()

    try:
        created = service.events().insert(
            calendarId="primary",
            body=event_body,
            sendUpdates="all" if attendee_email else "none",
        ).execute()
        return {
            "event_link": created.get("htmlLink"),
            "meeting_type": meeting_type,
            "zoom_join_url": zoom_info["join_url"] if zoom_info else None,
        }
    except HttpError as e:
        print(f"Calendar create failed: {e}")
        return {"error": str(e)}
