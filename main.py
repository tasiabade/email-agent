"""
The web server. This runs continuously on Railway.

Two responsibilities:
  1. Run a scheduler that fires run_digest() every 2 hours, 7am-7pm ET
  2. Receive inbound text replies via Twilio webhook at /sms

Public URL on Railway will be something like:
  https://email-agent-production.up.railway.app
And Twilio will POST to https://your-url/sms whenever you text the agent.
"""

import os
from datetime import datetime
from zoneinfo import ZoneInfo

from flask import Flask, request, Response
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

import config
from agent import run_digest, handle_reply

app = Flask(__name__)


# ============================================================
# Twilio inbound webhook
# ============================================================

@app.route("/sms", methods=["POST"])
def sms_webhook():
    """Twilio POSTs here when you text the agent."""
    from_number = request.form.get("From", "")
    body = request.form.get("Body", "").strip()

    # Security: only respond to YOUR phone
    if from_number != config.YOUR_PHONE_NUMBER:
        print(f"Ignoring text from unauthorized number: {from_number}")
        return Response("<Response></Response>", mimetype="text/xml")

    print(f"Inbound from {from_number}: {body}")
    try:
        handle_reply(body)
    except Exception as e:
        print(f"Reply handler error: {e}")
        from sms_tools import send_text
        send_text(f"⚠️ Agent error: {str(e)[:200]}")

    # Twilio just wants an empty TwiML response
    return Response("<Response></Response>", mimetype="text/xml")


@app.route("/", methods=["GET"])
def health():
    """Quick check that the server is alive."""
    return {
        "status": "ok",
        "now": datetime.now(ZoneInfo(config.TIMEZONE)).isoformat(),
        "active_window": (
            f"{config.ACTIVE_HOURS_START}:00 - {config.ACTIVE_HOURS_END}:00 "
            f"{config.TIMEZONE}"
        ),
    }


@app.route("/run-now", methods=["GET", "POST"])
def run_now_endpoint():
    """Manual trigger for testing — visit in browser to force a digest."""
    try:
        result = run_digest()
        return {"status": result}
    except Exception as e:
        return {"status": "error", "message": str(e)}, 500


# ============================================================
# Scheduler
# ============================================================

def _scheduled_run():
    """Wrapper called by APScheduler. Only runs in active hours."""
    now = datetime.now(ZoneInfo(config.TIMEZONE))
    hour = now.hour
    if config.ACTIVE_HOURS_START <= hour < config.ACTIVE_HOURS_END:
        try:
            run_digest()
        except Exception as e:
            print(f"Scheduled digest failed: {e}")
            from sms_tools import send_text
            try:
                send_text(f"⚠️ Digest run failed: {str(e)[:200]}")
            except Exception:
                pass
    else:
        print(f"Skipping run: {hour} outside active window.")


def start_scheduler():
    """Set up the every-2-hours job."""
    scheduler = BackgroundScheduler(timezone=config.TIMEZONE)

    # Run at 7am, 9am, 11am, 1pm, 3pm, 5pm, 7pm
    hours = list(range(
        config.ACTIVE_HOURS_START,
        config.ACTIVE_HOURS_END + 1,
        config.CHECK_INTERVAL_HOURS,
    ))
    hour_str = ",".join(str(h) for h in hours)

    scheduler.add_job(
        _scheduled_run,
        trigger=CronTrigger(hour=hour_str, minute=0, timezone=config.TIMEZONE),
        id="digest_job",
        replace_existing=True,
    )
    scheduler.start()
    print(f"Scheduler started. Will run at hours: {hour_str} {config.TIMEZONE}")


# ============================================================
# Entry point
# ============================================================

# Start scheduler when Flask app initializes (works under gunicorn too)
start_scheduler()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
