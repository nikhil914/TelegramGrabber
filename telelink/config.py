"""
TeleLink — Configuration Constants
"""
from pathlib import Path
import os

# Database
DB_PATH = Path(os.environ.get("TELELINK_DB_PATH", "./telelink.db"))

# Telethon session
SESSION_NAME = os.environ.get("TELELINK_SESSION", "./telelink.session")

# App window
APP_TITLE = "TeleLink — Telegram Link Extractor"
APP_WIDTH = 1280
APP_HEIGHT = 860

# Retry / rate-limit settings
MAX_RETRIES = 3
RETRY_DELAYS = [1, 2, 4]  # Exponential backoff in seconds

# Telegram iteration batch size
BATCH_SIZE = 100  # Messages per Telethon iteration

#Link opener wait_time
wait_time = 18

