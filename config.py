"""
========================================================
CONFIG FILE - This is the ONLY file you need to edit.
========================================================
Paste your saved keys/IDs into the spots marked TODO.
Don't share this file with anyone after you fill it in.
"""

import os

# ============================================================
# ANTHROPIC (Claude's brain)
# ============================================================
ANTHROPIC_API_KEY = os.environ.get(
    "ANTHROPIC_API_KEY",
    "TODO_paste_anthropic_key_here"
)
CLAUDE_MODEL = "claude-sonnet-4-5"

# ============================================================
# TWILIO (texting)
# ============================================================
TWILIO_ACCOUNT_SID = os.environ.get(
    "TWILIO_ACCOUNT_SID", "TODO_paste_account_sid_here"
)
TWILIO_AUTH_TOKEN = os.environ.get(
    "TWILIO_AUTH_TOKEN", "TODO_paste_auth_token_here"
)
TWILIO_PHONE_NUMBER = os.environ.get(
    "TWILIO_PHONE_NUMBER", "+1XXXXXXXXXX"
)
YOUR_PHONE_NUMBER = os.environ.get(
    "YOUR_PHONE_NUMBER", "+1XXXXXXXXXX"
)

# ============================================================
# GOOGLE (Gmail + Calendar)
# Put credentials.json in the project folder.
# token.json will be created automatically on first run.
# ============================================================
import json as _json

GOOGLE_CREDENTIALS_FILE = "credentials.json"
GOOGLE_TOKEN_FILE = "token.json"

_creds_json = os.environ.get("CREDENTIALS_JSON")
if _creds_json:
    with open("credentials.json", "w") as f:
        f.write(_creds_json)

_token_json = os.environ.get("TOKEN_JSON")
if _token_json:
    with open("token.json", "w") as f:
        f.write(_token_json)
# ============================================================
# ZOOM
# ============================================================
ZOOM_ACCOUNT_ID = os.environ.get(
    "ZOOM_ACCOUNT_ID", "TODO_paste_zoom_account_id"
)
ZOOM_CLIENT_ID = os.environ.get(
    "ZOOM_CLIENT_ID", "TODO_paste_zoom_client_id"
)
ZOOM_CLIENT_SECRET = os.environ.get(
    "ZOOM_CLIENT_SECRET", "TODO_paste_zoom_client_secret"
)

# ============================================================
# SCHEDULE
# ============================================================
TIMEZONE = "America/Indiana/Indianapolis"
CHECK_INTERVAL_HOURS = 2
ACTIVE_HOURS_START = 7   # 7 AM
ACTIVE_HOURS_END = 19    # 7 PM

# ============================================================
# VIPs - emails from these people are HIGH PRIORITY,
# never auto-archived, always shown in digest.
# Match is by NAME (case-insensitive) or by email address.
# To add more later, just add lines to this list.
# ============================================================
VIP_NAMES = [
    "Aasif Bade",
    "Naomi Bade",
    "Nicole English",
    "John Gause",
]

# Optional: if any VIP uses a specific email address you want
# to also match (e.g. work address that might not include their name)
VIP_EMAILS = [
    # "aasif.bade@example.com",
    # "nicole.english@workplace.com",
]

# ============================================================
# AUTO-ARCHIVE BEHAVIOR
# These categories get auto-archived (removed from inbox) and
# labeled. You can find them anytime in Gmail's All Mail.
# ============================================================
AUTO_ARCHIVE_CATEGORIES = ["newsletter", "promotional", "fluff"]

# Categories that STAY in inbox and appear in your digest text
SHOW_IN_DIGEST_CATEGORIES = ["vip", "human", "financial_legal", "kids_family"]

# How many hours back to look on each run
LOOKBACK_HOURS = 2

# Cap so a single text doesn't get crazy long
MAX_EMAILS_PER_DIGEST = 15
