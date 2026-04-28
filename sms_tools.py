"""
Twilio SMS: send digest texts and parse inbound replies.
"""

from twilio.rest import Client
import config


def get_twilio_client():
    return Client(config.TWILIO_ACCOUNT_SID, config.TWILIO_AUTH_TOKEN)


def send_text(message: str) -> bool:
    """Send a text to your phone. Auto-splits if >1500 chars."""
    client = get_twilio_client()
    chunks = _split_for_sms(message, max_len=1500)
    try:
        for chunk in chunks:
            client.messages.create(
                body=chunk,
                from_=config.TWILIO_PHONE_NUMBER,
                to=config.YOUR_PHONE_NUMBER,
            )
        return True
    except Exception as e:
        print(f"SMS send failed: {e}")
        return False


def _split_for_sms(text: str, max_len: int = 1500) -> list:
    """Break long text into chunks at line breaks where possible."""
    if len(text) <= max_len:
        return [text]
    chunks = []
    current = ""
    for line in text.split("\n"):
        if len(current) + len(line) + 1 > max_len:
            chunks.append(current.rstrip())
            current = line + "\n"
        else:
            current += line + "\n"
    if current:
        chunks.append(current.rstrip())
    return chunks
