# TeleLink — Setup Guide

## Prerequisites
- **Python 3.10+** installed
- A **Telegram account** (personal, not a bot)
- You must be a **member** of the channel(s) you want to scrape

---

## Step 1 — Get Telegram API Credentials

1. Open **[https://my.telegram.org/apps](https://my.telegram.org/apps)** in your browser
2. Log in with your Telegram phone number
3. Click **"API development tools"**
4. Fill in the form:
   - **App title**: `TeleLink` (or anything you like)
   - **Short name**: `telelink`
   - **Platform**: `Desktop`
5. Click **"Create application"**
6. Copy two values:
   - **api_id** — a number (e.g. `12345678`)
   - **api_hash** — a string (e.g. `0123456789abcdef0123456789abcdef`)

> ⚠️ **Never share** your `api_id` and `api_hash` with anyone.

---

## Step 2 — Install Dependencies

```bash
cd telelink
pip install -r requirements.txt
```

---

## Step 3 — Configure Credentials

```bash
# Copy the template
cp .env.example .env

# Edit .env and fill in your values:
TELEGRAM_API_ID=12345678
TELEGRAM_API_HASH=0123456789abcdef0123456789abcdef
TELEGRAM_PHONE=+971501234567
```

Or you can enter them directly in the app's **Auth** tab at launch time.

---

## Step 4 — Launch TeleLink

```bash
python main.py
```

This opens a native desktop window. If the desktop wrapper isn't available,
it will fall back to launching Streamlit in your browser.

---

## First Launch

1. The app opens on the **🔐 Auth** tab
2. Your `.env` credentials are pre-filled (if configured)
3. Click **"🔌 Connect & Send OTP"**
4. Enter the OTP code from your Telegram app
5. If you have 2FA enabled, enter your password
6. Navigate to **📡 Scrape** to start extracting links!

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `ModuleNotFoundError` | Run `pip install -r requirements.txt` again |
| OTP not received | Check Telegram app → "Saved Messages" or SMS |
| FloodWaitError | Normal for large channels — the app auto-waits and shows countdown |
| Session expired | Delete `*.session` files and re-authenticate |
