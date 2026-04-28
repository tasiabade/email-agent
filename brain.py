"""
Claude-powered logic: categorize emails and parse inbound text commands.
"""

import json
from anthropic import Anthropic
import config

client = Anthropic(api_key=config.ANTHROPIC_API_KEY)


# ============================================================
# EMAIL CATEGORIZATION
# ============================================================

CATEGORIZE_SYSTEM_PROMPT = """You are a strict email triage assistant for Tasia Bade.

Your job: classify each email into exactly ONE category.

Categories:
- "vip" — from one of: Aasif Bade, Naomi Bade, Nicole English, John Gause (match by name OR email if it's clearly them)
- "human" — a real person writing personally, not automated. Includes business contacts, friends, colleagues, clients.
- "financial_legal" — banks, credit cards, IRS, taxes, contracts, legal notices, fraud alerts, bills due, official statements, insurance.
- "kids_family" — schools, doctors' offices, family members not on VIP list, sports teams, kids' activities, summer camps, daycare.
- "newsletter" — recurring digests, weekly roundups, content publications.
- "promotional" — marketing emails, sales, discounts, "we miss you," product launches.
- "fluff" — social media notifications (LinkedIn, FB, IG), receipts for routine purchases, shipping updates, app notifications, surveys, automated alerts not requiring action.

Be aggressive on "fluff" — when in doubt between fluff and promotional, pick fluff.
Be conservative on "human" — only if truly looks like a person writing.

Return ONLY a JSON array, one object per email, in the same order. No prose.
Each object: {"id": "<email_id>", "category": "<category>", "reason": "<10 words max>"}
"""


def categorize_emails(emails: list, vip_names: list, vip_emails: list) -> list:
    """
    Send the email list to Claude, get back categories.
    Returns: list of dicts {id, category, reason} aligned with input order.
    """
    if not emails:
        return []

    # Pre-tag VIPs deterministically (don't waste a Claude call on these)
    vip_names_lower = [n.lower() for n in vip_names]
    vip_emails_lower = [e.lower() for e in vip_emails]

    pre_tagged = {}
    to_classify = []
    for e in emails:
        name_match = any(
            v in (e.get("from_name") or "").lower() for v in vip_names_lower
        )
        email_match = (e.get("from_email") or "").lower() in vip_emails_lower
        if name_match or email_match:
            pre_tagged[e["id"]] = {
                "id": e["id"], "category": "vip", "reason": "VIP match"
            }
        else:
            to_classify.append(e)

    classified = {}
    if to_classify:
        compact = [
            {
                "id": e["id"],
                "from": e.get("from_raw", ""),
                "subject": e.get("subject", ""),
                "snippet": (e.get("snippet", "") or "")[:200],
            }
            for e in to_classify
        ]
        prompt = f"Classify these {len(compact)} emails:\n\n{json.dumps(compact, indent=2)}"

        response = client.messages.create(
            model=config.CLAUDE_MODEL,
            max_tokens=2000,
            system=CATEGORIZE_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )
        text = response.content[0].text.strip()
        # Strip code fences if present
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
            text = text.strip()
        try:
            results = json.loads(text)
            for r in results:
                classified[r["id"]] = r
        except json.JSONDecodeError as e:
            print(f"Categorize parse failed: {e}\nRaw: {text}")
            for e_obj in to_classify:
                classified[e_obj["id"]] = {
                    "id": e_obj["id"], "category": "human", "reason": "parse error fallback"
                }

    # Combine pre-tagged + classified, preserving original order
    out = []
    for e in emails:
        if e["id"] in pre_tagged:
            out.append(pre_tagged[e["id"]])
        else:
            out.append(classified.get(
                e["id"],
                {"id": e["id"], "category": "human", "reason": "unclassified"}
            ))
    return out


# ============================================================
# REPLY PARSING (you texting commands back to the agent)
# ============================================================

PARSE_REPLY_SYSTEM_PROMPT = """You parse Tasia's text replies to her email-agent.

She might send messages like:
- "delete 1, 3, 5" or "delete 1 3 5" or "trash 2" → DELETE command
- "draft reply to 2: tell them I'm busy this week" → DRAFT command
- "book meeting with sender of 4 Tuesday 3pm" → BOOK command (zoom default)
- "book Zoom with sender of 4 Tuesday 3pm" → BOOK with zoom override
- "book in-person with sender of 4 Tuesday 3pm at Starbucks Carmel" → BOOK with in_person
- "book phone call with sender of 4 Tuesday 3pm" → BOOK with phone
- "what's new" or "check now" → CHECK_NOW command
- "help" → HELP command
- Anything unclear → UNKNOWN

Return ONLY a JSON object:
{
  "command": "DELETE" | "DRAFT" | "BOOK" | "CHECK_NOW" | "HELP" | "UNKNOWN",
  "email_numbers": [list of ints, for DELETE/DRAFT/BOOK],
  "draft_notes": "string or null",
  "meeting_type_override": "zoom" | "in_person" | "phone" | null,
  "meeting_when": "raw natural-language time string from user, e.g. 'Tuesday 3pm' (null if not BOOK)",
  "meeting_location": "string or null",
  "meeting_duration_minutes": 30
}
"""


def parse_reply(text: str) -> dict:
    """Parse an inbound text into a structured command."""
    response = client.messages.create(
        model=config.CLAUDE_MODEL,
        max_tokens=500,
        system=PARSE_REPLY_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": text}],
    )
    raw = response.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"command": "UNKNOWN"}


# ============================================================
# MEETING-TIME PARSING
# ============================================================

def parse_meeting_time(natural_language: str, current_dt) -> str:
    """
    Convert 'Tuesday 3pm' → ISO datetime string. current_dt is timezone-aware.
    Returns ISO string or None.
    """
    prompt = (
        f"Today is {current_dt.strftime('%A, %B %d, %Y at %I:%M %p %Z')}.\n"
        f"Convert this scheduling request into the next matching ISO 8601 "
        f"datetime in {config.TIMEZONE} timezone: \"{natural_language}\"\n\n"
        f"If the day is in the past for this week, use NEXT week.\n"
        f"Return ONLY the ISO datetime string, nothing else. "
        f"Example format: 2026-05-05T15:00:00"
    )
    response = client.messages.create(
        model=config.CLAUDE_MODEL,
        max_tokens=100,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text.strip()
