"""
Run this ONCE on your laptop to do the initial Gmail/Calendar authorization.
A browser will pop open asking you to sign in to Google and approve permissions.
After it succeeds, a `token.json` file is created. You'll upload that to Railway.

Usage:
    python authorize_local.py
"""

from gmail_tools import get_gmail_service

if __name__ == "__main__":
    print("Starting Gmail/Calendar authorization...")
    print("A browser window will open. Sign in with the Google account you want")
    print("the agent to manage, and click Allow on every permission screen.\n")
    service = get_gmail_service()
    profile = service.users().getProfile(userId="me").execute()
    print(f"\n✅ Success! Authorized for: {profile['emailAddress']}")
    print(f"   token.json saved. You'll upload this to Railway later.")
