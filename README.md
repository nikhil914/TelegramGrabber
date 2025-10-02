<div align="center">
  <img src="https://raw.githubusercontent.com/nikhil914/TelegramGrabber/main/assets/banner.png" alt="Telegram Link Extractor Banner" width="800">

  <h1>Telegram Link Extractor (TeleLink)</h1>
  <p><b>A powerful, native Telegram link extraction and analytics tool.</b></p>
  
  [![Python](https://img.shields.io/badge/Python-3.10%2B-blue?style=flat-square&logo=python)](https://www.python.org/)
  [![Telegram API](https://img.shields.io/badge/Telethon-Telegram_API-0088cc?style=flat-square&logo=telegram)](https://core.telegram.org/)
  [![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)](LICENSE)
</div>

<br/>

**TeleLink** (Telegram Grabber) is a full-featured desktop application designed to scrape, extract, manage, and analyze links from your Telegram channels. Built with Python, Streamlit, and Telethon, it offers a beautifully native desktop experience with powerful data filtering and export capabilities.

---

## ✨ Features

*   🔐 **Secure Authentication**: Connect using your personal Telegram account safely. Supports OTP and 2FA. Session persistence means you only log in once.
*   📡 **Automated Scraping**: Extract messages and links from any channel you are a member of. Handles Telegram's rate-limiting automatically.
*   ⚡ **Incremental Mode**: Only fetches *new* messages since your last scrape, saving time and API calls.
*   💬 **Advanced Filtering & Search**: Browse extracted messages and links. Filter by dates, keywords, channels, and domains.
*   📊 **Analytics Dashboard**: Visual statistics showing your most-linked domains, scraping activity over time, and per-channel summaries.
*   💾 **Flexible Exports**: One-click exports of all your scraped data and unique URLs to `CSV` or `JSON`.
*   🖥️ **Native Desktop Feel**: Runs as a standalone desktop window (via `streamlit-desktop-app`), making it feel like a seamless native tool.

---

## 🚀 Quick Setup

### 1. Prerequisites
*   Python 3.10 or higher.
*   A Telegram account (you must be a member of the channels you intend to scrape).

### 2. Get Telegram API Credentials
1.  Go to [my.telegram.org/apps](https://my.telegram.org/apps) and log in.
2.  Click **API development tools**.
3.  Create an application (App title: `TeleLink`, Platform: `Desktop`).
4.  Copy your **`api_id`** and **`api_hash`**. *(Keep these secret!)*

### 3. Installation

Clone the repository and install dependencies:
```bash
git clone https://github.com/nikhil914/TelegramGrabber.git
cd TelegramGrabber/telelink
pip install -r requirements.txt
```

### 4. Configuration
Duplicate the example environment file:
```bash
cp .env.example .env
```
Edit `.env` to include your credentials:
```env
TELEGRAM_API_ID=your_api_id
TELEGRAM_API_HASH=your_api_hash
TELEGRAM_PHONE=+1234567890
```
*(Alternatively, you can enter these credentials securely in the app UI during your first launch).*

### 5. Launch the App
```bash
python main.py
```
This opens the native desktop window.

---

## 📖 Usage Guide

The application is structured into 5 logical tabs:

1.  **🔐 Auth**: Enter your credentials, receive your OTP code, and authenticate. A session file will be created for auto-login on future runs.
2.  **📡 Scrape**: Add channels (e.g., `@channelname` or link). Set date ranges, limits, or enable "Skip already-scraped" before hitting **Start Scraping**.
3.  **💬 Messages**: Browse and search through the full text of all scraped messages. Export filtered views.
4.  **🔗 Links**: View standalone extracted URLs with their metadata. Click to open directly in your browser.
5.  **📊 Stats**: Analyze your data with charts showing your top domains and timeline activity.

> **Note on Rate Limits**: If Telegram throttles your connection (FloodWaitError), TeleLink will display a countdown and automatically resume scraping once the cooldown period ends. Do not close the app!

---

## 🤝 Contributing

Contributions, issues, and feature requests are welcome! Feel free to check the [issues page](https://github.com/nikhil914/TelegramGrabber/issues).

## 📄 License

This project is licensed under the MIT License. See the `LICENSE` file for details.
