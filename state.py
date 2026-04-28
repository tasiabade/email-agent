"""
Tiny persistence layer. Stores the last digest's email list so when you
text back 'delete 3', the agent knows which email '#3' refers to.

Uses a simple JSON file. On Railway, this lives in /tmp which is fine
for our needs — losing the mapping just means the next 'delete' command
won't work until the next digest fires.
"""

import json
import os
from datetime import datetime

STATE_FILE = "/tmp/agent_state.json" if os.path.exists("/tmp") else "agent_state.json"


def save_digest_state(digest_emails: list):
    """Save the numbered list of emails from the last digest."""
    state = {
        "last_digest_at": datetime.utcnow().isoformat(),
        "emails": digest_emails,
    }
    try:
        with open(STATE_FILE, "w") as f:
            json.dump(state, f)
    except Exception as e:
        print(f"State save failed: {e}")


def load_digest_state() -> dict:
    """Load the last digest. Returns empty if none."""
    if not os.path.exists(STATE_FILE):
        return {"emails": [], "last_digest_at": None}
    try:
        with open(STATE_FILE) as f:
            return json.load(f)
    except Exception:
        return {"emails": [], "last_digest_at": None}


def get_email_by_number(number: int) -> dict:
    """Return the email dict for the given number from the last digest, or None."""
    state = load_digest_state()
    emails = state.get("emails", [])
    if 1 <= number <= len(emails):
        return emails[number - 1]
    return None
