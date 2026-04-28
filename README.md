# Tasia's Email Agent — Setup Guide

## What this does

Every 2 hours from 7am–7pm Eastern, this agent:

1. Reads new emails in your Gmail inbox
2. Categorizes each (VIP, human, financial, kids/family, newsletter, promotional, fluff)
3. Auto-archives newsletters, promotional, and fluff (with Gmail labels)
4. Texts you a digest of what's left
5. You can reply to delete, draft replies, or book meetings — including auto Zoom links when appropriate

VIPs (always shown, never archived): Aasif Bade, Naomi Bade, Nicole English, John Gause.

---

## What you'll need on hand

The five values from your Notes file:
- `ANTHROPIC_API_KEY` (starts with `sk-ant-`)
- `TWILIO_ACCOUNT_SID` (starts with `AC`)
- `TWILIO_AUTH_TOKEN`
- `TWILIO_PHONE_NUMBER` (starts with `+1`)
- `YOUR_PHONE_NUMBER` (your personal cell, starts with `+1`)
- `ZOOM_ACCOUNT_ID`
- `ZOOM_CLIENT_ID`
- `ZOOM_CLIENT_SECRET`

Plus the `credentials.json` file in your `email-agent` folder on Desktop.

---

## Deployment — six steps

### Step 1: Install Python on your laptop (if not already)

On Mac, open Terminal (Spotlight → "Terminal") and type:

    python3 --version

If you see something like `Python 3.10.x` or higher, skip ahead. If you see "command not found," install Python from python.org/downloads.

### Step 2: Set up the project folder

1. Download the `email-agent` zip from this chat
2. Unzip it
3. Move every file from the unzipped folder INTO your existing `email-agent` folder on Desktop (the one that has `credentials.json`)
4. Open Terminal and navigate to it:

       cd ~/Desktop/email-agent

### Step 3: Authorize Gmail/Calendar

Run these commands in Terminal:

    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
    python3 authorize_local.py

A browser window will open. Sign in with your Google account, click "Continue" past the "unverified app" warning (your app is unverified because you didn't pay Google to verify it — that's fine for personal use), and click "Allow" on every permission screen.

When it succeeds, you'll see "✅ Authorized for: your-email@gmail.com" and a `token.json` file will appear in your folder.

### Step 4: Push code to GitHub

1. Go to **github.com** → click "+" → "New repository"
2. Name it `email-agent`, mark it **Private**, click "Create"
3. GitHub shows you commands. Use these in Terminal (still in the email-agent folder):

       git init
       git add .
       git commit -m "Initial commit"
       git branch -M main
       git remote add origin https://github.com/YOUR_USERNAME/email-agent.git
       git push -u origin main

(The `.gitignore` ensures your secrets are NOT uploaded.)

### Step 5: Deploy to Railway

1. Go to **railway.com**, click **"+ New Project"**
2. Choose **"Deploy from GitHub repo"**
3. Pick your `email-agent` repo
4. Once it starts building, click on your service and go to **"Variables"** tab
5. Add each environment variable using the values from your Notes file:

   - `ANTHROPIC_API_KEY`
   - `TWILIO_ACCOUNT_SID`
   - `TWILIO_AUTH_TOKEN`
   - `TWILIO_PHONE_NUMBER`
   - `YOUR_PHONE_NUMBER`
   - `ZOOM_ACCOUNT_ID`
   - `ZOOM_CLIENT_ID`
   - `ZOOM_CLIENT_SECRET`

6. **Upload `credentials.json` and `token.json`** as files. Railway lets you do this via the "Volumes" or "Files" feature, OR you can paste them as multi-line env vars (we'll handle whichever Railway shows you).

7. Railway will redeploy automatically. After ~2 minutes, click **"Settings"** → **"Networking"** → **"Generate Domain"**. You'll get a public URL like `https://email-agent-production.up.railway.app`.

### Step 6: Connect Twilio webhook

1. Go to Twilio console → Phone Numbers → Manage → click your number
2. Scroll to **"Messaging Configuration"**
3. Set **"A message comes in"** to: **Webhook**
4. URL: `https://YOUR-RAILWAY-URL.up.railway.app/sms`
5. Method: **HTTP POST**
6. Save

### Step 7: Test it

1. Visit `https://YOUR-RAILWAY-URL.up.railway.app/run-now` in your browser
2. You should get a text within 30 seconds
3. Reply "help" to confirm two-way works

---

## How to use the agent

Reply to digest texts with:

| Command | What it does |
|---|---|
| `delete 1, 3, 5` | Trash those numbered emails |
| `draft reply to 2: tell them I'm busy this week` | Creates a Gmail draft you can review |
| `book meeting with sender of 4 Tuesday 3pm` | Calendar event + auto-detected meeting type |
| `book Zoom with sender of 4 Tuesday 3pm` | Forces Zoom link |
| `book in-person with sender of 4 Tuesday 3pm at Starbucks Carmel` | No Zoom, location filled in |
| `book phone call with sender of 4 Tuesday 3pm` | No Zoom, marked as phone |
| `what's new` | Force a digest right now |
| `help` | Show this list |

Drafts always land in Gmail Drafts — they are NEVER auto-sent. Review and send manually.

---

## Costs

- Anthropic API: ~$5–10/month
- Twilio: ~$5/month (number + texts)
- Railway: ~$5/month
- **Total: ~$15–20/month**, no caps

---

## Troubleshooting

**"I'm not getting texts"**
- Visit `/run-now` URL in browser. If you see `{"status": "ok"}`, the agent ran. Check Twilio's logs (Console → Monitor → Logs) for delivery status.

**"Authorization expired"**
- Re-run `python3 authorize_local.py` locally, replace `token.json` on Railway.

**"Wrong things archived"**
- Open Gmail → look in `newsletters` / `promotional` / `fluff` labels for misclassified items. Reply to them or move them back to inbox; the agent will leave them alone next time as long as they're in inbox.

**"It's making mistakes consistently"**
- Edit `brain.py` → `CATEGORIZE_SYSTEM_PROMPT` to add specific rules. E.g., "emails from school@carmelclay.k12.in.us are always kids_family."
