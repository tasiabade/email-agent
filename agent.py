"""
The orchestrator. Two main entry points:
  1. run_digest() — called every 2 hours by the scheduler
  2. handle_reply(text) — called by the webhook when you text back

Both delegate to the modules in this folder.
"""

from datetime import datetime
from zoneinfo import ZoneInfo

import config
import gmail_tools
import calendar_tools
import sms_tools
import brain
import state


# ============================================================
# DIGEST RUN (called by scheduler)
# ============================================================

def run_digest() -> str:
    """
    1. Pull recent emails
    2. Categorize them
    3. Auto-archive newsletters/promotional/fluff
    4. Build digest text and send it
    """
    print(f"[{datetime.now()}] Running digest...")

    emails = gmail_tools.list_recent_emails(hours_back=config.LOOKBACK_HOURS)
    if not emails:
        sms_tools.send_text("📭 No new emails since last check.")
        state.save_digest_state([])
        return "no_emails"

    print(f"  Found {len(emails)} emails. Categorizing...")
    classifications = brain.categorize_emails(
        emails, config.VIP_NAMES, config.VIP_EMAILS
    )

    # Index lookup: email_id -> category
    cat_by_id = {c["id"]: c["category"] for c in classifications}

    # Auto-archive fluff
    archived_count = 0
    for email in emails:
        cat = cat_by_id.get(email["id"], "human")
        if cat in config.AUTO_ARCHIVE_CATEGORIES:
            label_name = {
                "newsletter": "newsletters",
                "promotional": "promotional",
                "fluff": "fluff",
            }.get(cat, cat)
            ok = gmail_tools.archive_with_label(email["id"], label_name)
            if ok:
                archived_count += 1

    # Build digest of stuff that stayed
    digest_emails = [
        {
            "id": e["id"],
            "thread_id": e["thread_id"],
            "from_name": e["from_name"] or e["from_email"],
            "from_email": e["from_email"],
            "subject": e["subject"],
            "category": cat_by_id.get(e["id"], "human"),
            "snippet": e["snippet"][:120],
        }
        for e in emails
        if cat_by_id.get(e["id"], "human") in config.SHOW_IN_DIGEST_CATEGORIES
    ]

    # Order: VIP first, then other categories
    priority = {"vip": 0, "human": 1, "financial_legal": 2, "kids_family": 3}
    digest_emails.sort(key=lambda x: priority.get(x["category"], 99))

    # Cap length
    if len(digest_emails) > config.MAX_EMAILS_PER_DIGEST:
        overflow = len(digest_emails) - config.MAX_EMAILS_PER_DIGEST
        digest_emails = digest_emails[:config.MAX_EMAILS_PER_DIGEST]
    else:
        overflow = 0

    # Save numbered list so 'delete 3' works
    state.save_digest_state(digest_emails)

    # Build text
    text = _format_digest(digest_emails, archived_count, overflow)
    sms_tools.send_text(text)
    print(f"  Sent digest. Archived {archived_count}, kept {len(digest_emails)}.")
    return "ok"


def _format_digest(digest_emails: list, archived_count: int, overflow: int) -> str:
    """Build the SMS body."""
    now = datetime.now(ZoneInfo(config.TIMEZONE))
    lines = [f"📧 {now.strftime('%-I%p')} digest"]

    if not digest_emails:
        lines.append("\n✅ All clear — nothing needs your attention.")
        if archived_count:
            lines.append(f"🗑 {archived_count} fluff emails auto-archived.")
        return "\n".join(lines)

    # Group by category
    sections = {
        "vip": ("🔥 HIGH PRIORITY", []),
        "human": ("👤 HUMAN", []),
        "financial_legal": ("💰 FINANCIAL & LEGAL", []),
        "kids_family": ("👨‍👩‍👧 KIDS & FAMILY", []),
    }
    for i, e in enumerate(digest_emails, 1):
        sections[e["category"]][1].append(
            f"{i}. {e['from_name']} — \"{e['subject'][:60]}\""
        )

    for header, items in sections.values():
        if items:
            lines.append("")
            lines.append(header)
            lines.extend(items)

    if archived_count:
        lines.append("")
        lines.append(f"🗑 {archived_count} fluff archived")

    if overflow:
        lines.append(f"+ {overflow} more not shown")

    lines.append("")
    lines.append("Reply: delete N | draft N: notes | book N day/time")
    return "\n".join(lines)


# ============================================================
# REPLY HANDLER (called by Twilio webhook)
# ============================================================

def handle_reply(text: str) -> str:
    """Parse user text, execute the command, send a confirmation."""
    print(f"Inbound: {text}")

    parsed = brain.parse_reply(text)
    cmd = parsed.get("command", "UNKNOWN")
    print(f"  Parsed as: {cmd}")

    if cmd == "DELETE":
        return _handle_delete(parsed)
    if cmd == "DRAFT":
        return _handle_draft(parsed)
    if cmd == "BOOK":
        return _handle_book(parsed)
    if cmd == "CHECK_NOW":
        run_digest()
        return "ok"
    if cmd == "HELP":
        sms_tools.send_text(
            "Commands:\n"
            "• delete 1, 3, 5\n"
            "• draft reply to 2: my notes\n"
            "• book meeting with sender of 4 Tuesday 3pm\n"
            "• book Zoom/in-person/phone call with sender of 4 ...\n"
            "• what's new"
        )
        return "ok"

    sms_tools.send_text(
        "Didn't understand that. Reply 'help' for commands."
    )
    return "unknown"


def _handle_delete(parsed: dict) -> str:
    nums = parsed.get("email_numbers", [])
    if not nums:
        sms_tools.send_text("Couldn't tell which emails to delete.")
        return "fail"

    deleted = []
    failed = []
    for n in nums:
        em = state.get_email_by_number(n)
        if not em:
            failed.append(n)
            continue
        if gmail_tools.delete_email(em["id"]):
            deleted.append(n)
        else:
            failed.append(n)

    msg_parts = []
    if deleted:
        msg_parts.append(f"🗑 Deleted: {', '.join(str(n) for n in deleted)}")
    if failed:
        msg_parts.append(f"⚠️ Failed: {', '.join(str(n) for n in failed)}")
    sms_tools.send_text(" | ".join(msg_parts) or "Nothing happened")
    return "ok"


def _handle_draft(parsed: dict) -> str:
    nums = parsed.get("email_numbers", [])
    notes = parsed.get("draft_notes") or ""
    if not nums or not notes:
        sms_tools.send_text("Need both email number and draft notes.")
        return "fail"

    n = nums[0]
    em = state.get_email_by_number(n)
    if not em:
        sms_tools.send_text(f"Couldn't find email #{n} from last digest.")
        return "fail"

    # Pull full email for context
    full = gmail_tools.get_full_email(em["id"])

    # Have Claude write a polished draft from notes
    draft_prompt = (
        f"Original email from {full['from']}:\n"
        f"Subject: {full['subject']}\n\n"
        f"{full['body'][:3000]}\n\n"
        f"---\n"
        f"Tasia wants to reply with this gist: \"{notes}\"\n\n"
        f"Write a polite, professional reply in Tasia's voice. Be warm but concise. "
        f"Do NOT include subject line or 'Dear X' / 'From, Tasia'. "
        f"Just the body of the reply. Sign off with 'Tasia'."
    )
    response = brain.client.messages.create(
        model=config.CLAUDE_MODEL,
        max_tokens=600,
        messages=[{"role": "user", "content": draft_prompt}],
    )
    body = response.content[0].text.strip()

    ok = gmail_tools.create_draft_reply(
        thread_id=em["thread_id"],
        to_address=em["from_email"],
        subject=em["subject"],
        body=body,
    )
    if ok:
        sms_tools.send_text(
            f"✏️ Draft saved for #{n} ({em['from_name']}). Review in Gmail Drafts."
        )
        return "ok"
    sms_tools.send_text(f"⚠️ Draft failed for #{n}.")
    return "fail"


def _handle_book(parsed: dict) -> str:
    nums = parsed.get("email_numbers", [])
    when = parsed.get("meeting_when")
    override = parsed.get("meeting_type_override")
    location = parsed.get("meeting_location")
    duration = parsed.get("meeting_duration_minutes") or 30

    if not nums or not when:
        sms_tools.send_text("Need email number and meeting time.")
        return "fail"

    n = nums[0]
    em = state.get_email_by_number(n)
    if not em:
        sms_tools.send_text(f"Couldn't find email #{n}.")
        return "fail"

    # Parse time
    now = datetime.now(ZoneInfo(config.TIMEZONE))
    iso = brain.parse_meeting_time(when, now)
    try:
        start_dt = datetime.fromisoformat(iso).replace(tzinfo=ZoneInfo(config.TIMEZONE))
    except Exception as e:
        sms_tools.send_text(f"⚠️ Couldn't parse time '{when}'.")
        return "fail"

    # Decide meeting type
    full = gmail_tools.get_full_email(em["id"])
    meeting_type = calendar_tools.infer_meeting_type(
        full["body"], override=override
    )

    title = f"Meeting with {em['from_name'] or em['from_email']}"
    result = calendar_tools.create_calendar_event(
        title=title,
        start_time=start_dt,
        duration_minutes=duration,
        attendee_email=em["from_email"],
        meeting_type=meeting_type,
        location=location,
        description=f"Re: {em['subject']}",
    )

    if "error" in result:
        sms_tools.send_text(f"⚠️ Calendar create failed: {result['error']}")
        return "fail"

    type_label = {"zoom": "Zoom", "in_person": "in-person", "phone": "phone"}[meeting_type]
    when_str = start_dt.strftime("%a %b %-d, %-I:%M%p")
    msg = f"📅 Booked {type_label} with {em['from_name']} for {when_str}"
    if meeting_type == "zoom" and result.get("zoom_join_url"):
        msg += f"\nZoom: {result['zoom_join_url']}"
    sms_tools.send_text(msg)
    return "ok"
