"""
Gmail operations. Uses Google's official API.
First run pops a browser asking you to log in. After that, token.json
is saved and reused — no more login prompts.
"""

import base64
import os
from datetime import datetime, timedelta, timezone
from email.mime.text import MIMEText

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

import config

SCOPES = [
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/gmail.compose",
    "https://www.googleapis.com/auth/gmail.labels",
    "https://www.googleapis.com/auth/calendar.events",
]


def get_gmail_service():
    """Authenticate and return a Gmail API service. Handles refresh."""
    creds = None
    if os.path.exists(config.GOOGLE_TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(
            config.GOOGLE_TOKEN_FILE, SCOPES
        )

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                config.GOOGLE_CREDENTIALS_FILE, SCOPES
            )
            creds = flow.run_local_server(port=0)
        with open(config.GOOGLE_TOKEN_FILE, "w") as f:
            f.write(creds.to_json())

    return build("gmail", "v1", credentials=creds)


def _get_or_create_label(service, label_name: str) -> str:
    """Return label ID, creating the label if it doesn't exist."""
    labels = service.users().labels().list(userId="me").execute().get("labels", [])
    for label in labels:
        if label["name"].lower() == label_name.lower():
            return label["id"]

    new_label = {
        "name": label_name,
        "labelListVisibility": "labelShow",
        "messageListVisibility": "show",
    }
    created = service.users().labels().create(userId="me", body=new_label).execute()
    return created["id"]


def list_recent_emails(hours_back: int = None) -> list:
    """
    Return summaries of all unread inbox emails from the past `hours_back` hours.
    Each summary has: id, thread_id, from_name, from_email, subject, snippet, date.
    """
    if hours_back is None:
        hours_back = config.LOOKBACK_HOURS

    service = get_gmail_service()
    after_ts = int(
        (datetime.now(timezone.utc) - timedelta(hours=hours_back)).timestamp()
    )
    query = f"in:inbox after:{after_ts}"

    result = service.users().messages().list(
        userId="me", q=query, maxResults=50
    ).execute()
    messages = result.get("messages", [])

    summaries = []
    for msg in messages:
        full = service.users().messages().get(
            userId="me",
            id=msg["id"],
            format="metadata",
            metadataHeaders=["From", "Subject", "Date"],
        ).execute()

        headers = {h["name"]: h["value"] for h in full["payload"]["headers"]}
        from_raw = headers.get("From", "")
        from_name, from_email = _parse_from(from_raw)

        summaries.append({
            "id": msg["id"],
            "thread_id": full["threadId"],
            "from_name": from_name,
            "from_email": from_email,
            "from_raw": from_raw,
            "subject": headers.get("Subject", "(no subject)"),
            "snippet": full.get("snippet", ""),
            "date": headers.get("Date", ""),
        })
    return summaries


def _parse_from(from_field: str) -> tuple:
    """Split 'Jane Doe <jane@x.com>' into ('Jane Doe', 'jane@x.com')."""
    if "<" in from_field and ">" in from_field:
        name = from_field.split("<")[0].strip().strip('"')
        email = from_field.split("<")[1].split(">")[0].strip()
        return name, email
    return "", from_field.strip()


def get_full_email(message_id: str) -> dict:
    """Fetch full email body for drafting replies."""
    service = get_gmail_service()
    msg = service.users().messages().get(
        userId="me", id=message_id, format="full"
    ).execute()

    body = _extract_body(msg["payload"])
    headers = {h["name"]: h["value"] for h in msg["payload"]["headers"]}
    return {
        "id": message_id,
        "thread_id": msg["threadId"],
        "from": headers.get("From", ""),
        "to": headers.get("To", ""),
        "subject": headers.get("Subject", ""),
        "body": body,
    }


def _extract_body(payload) -> str:
    """Pull plaintext body out of a Gmail payload."""
    if "parts" in payload:
        for part in payload["parts"]:
            if part.get("mimeType") == "text/plain":
                data = part.get("body", {}).get("data", "")
                if data:
                    return base64.urlsafe_b64decode(data).decode("utf-8", errors="ignore")
            if "parts" in part:
                nested = _extract_body(part)
                if nested:
                    return nested
    elif payload.get("body", {}).get("data"):
        return base64.urlsafe_b64decode(
            payload["body"]["data"]
        ).decode("utf-8", errors="ignore")
    return ""


def archive_with_label(message_id: str, label_name: str) -> bool:
    """Add the label and remove from inbox."""
    service = get_gmail_service()
    label_id = _get_or_create_label(service, label_name)
    try:
        service.users().messages().modify(
            userId="me",
            id=message_id,
            body={"addLabelIds": [label_id], "removeLabelIds": ["INBOX"]},
        ).execute()
        return True
    except HttpError as e:
        print(f"Archive error on {message_id}: {e}")
        return False


def delete_email(message_id: str) -> bool:
    """Move email to trash. (Not permanent — recoverable for 30 days.)"""
    service = get_gmail_service()
    try:
        service.users().messages().trash(userId="me", id=message_id).execute()
        return True
    except HttpError as e:
        print(f"Delete error on {message_id}: {e}")
        return False


def create_draft_reply(thread_id: str, to_address: str, subject: str, body: str) -> bool:
    """Create a draft reply on the given thread."""
    service = get_gmail_service()

    if not subject.lower().startswith("re:"):
        subject = f"Re: {subject}"

    message = MIMEText(body)
    message["to"] = to_address
    message["subject"] = subject
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()

    try:
        service.users().drafts().create(
            userId="me",
            body={"message": {"raw": raw, "threadId": thread_id}},
        ).execute()
        return True
    except HttpError as e:
        print(f"Draft error: {e}")
        return False
