# TeleLink — Usage Guide

## Tab Overview

TeleLink has 5 tabs, each designed for a specific workflow:

---

## 🔐 Auth — Authentication

**Purpose**: Connect to Telegram using your personal account.

| Element | Action |
|---------|--------|
| API ID / Hash / Phone | Enter your credentials (or load from `.env`) |
| 🔌 Connect & Send OTP | Connect to Telegram and receive a login code |
| ✅ Verify OTP | Submit the 6-digit code from your Telegram app |
| 🔓 Submit 2FA | Enter your two-factor password (if enabled) |
| 🚪 Logout | Delete session and disconnect |

**Session Persistence**: After first login, TeleLink saves a session file. On
subsequent launches, you'll be auto-authenticated — no need to re-enter OTP.

---

## 📡 Scrape — Channel Manager & Scraping

**Purpose**: Add channels and fetch their messages + links.

### Adding Channels
- Type a channel username (`@channelname`) or link (`https://t.me/channelname`)
- Click **➕ Add Channel** — the app validates and shows channel info
- Add multiple channels to scrape them sequentially

### Scrape Options
| Option | Description |
|--------|-------------|
| From / To Date | Date range filter (default: last 90 days) |
| Keyword filter | Telegram server-side search (fast) |
| Message limit | 100 to 50,000 or ALL |
| Extract links only | Skip messages without URLs |
| Skip already-scraped | Incremental mode — only fetches new messages |

### Scraping
- Click **🚀 Start Scraping** to begin
- Live progress: message count + link count update in real time
- Click **⏹ Stop Scraping** to halt gracefully
- After completion: summary table with per-channel stats

### FloodWait Handling
When Telegram rate-limits you, TeleLink shows a countdown:
> ⚠️ Rate limited by Telegram. Resuming in 47s…

**Don't close the app** — it will auto-resume when the wait expires.

---

## 💬 Messages — Browse & Export Messages

**Purpose**: View, search, and filter scraped messages.

- **Search**: Full-text search across message content
- **Channel filter**: View messages from a specific channel
- **Link filter**: Show only messages with/without links
- **Export**: Download filtered results as CSV or JSON

---

## 🔗 Links — Browse & Export Extracted URLs

**Purpose**: View all extracted URLs with metadata.

- **Search**: Filter URLs by keyword
- **Domain filter**: Show links from a specific domain
- **Channel filter**: Filter by source channel
- **Unique only**: Deduplicate URLs across messages
- **Clickable URLs**: Click any link to open in browser
- **Plain text**: Click "📋 Show All URLs" for a copyable text block
- **Export**: Download as CSV or JSON

---

## 📊 Stats — Analytics Dashboard

**Purpose**: Visual analysis of scraped data.

| Section | Shows |
|---------|-------|
| Per-Channel Summary | Table with total messages, links, last scraped time |
| Top 20 Domains | Bar chart of most-linked domains |
| Links Over Time | Timeline of link frequency |
| Source Breakdown | entity_url vs entity_texturl vs regex detection |

---

## Re-running the Scraper (Incremental Mode)

To fetch only **new** messages since your last scrape:

1. Go to **📡 Scrape**
2. Enable **"Skip already-scraped messages"** (on by default)
3. Click **🚀 Start Scraping**

TeleLink queries the database for the latest stored message ID per channel
and passes it to Telegram's API — only new messages are fetched.

---

## Export File Naming

Exports are auto-named: `telelink_{type}_{channel}_{date}.csv`

Example: `telelink_links_@techchannel_2026-02-22.csv`
