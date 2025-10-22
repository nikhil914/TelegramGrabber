"""
TeleLink — URL Extraction Engine

Runs five extraction methods on every message and deduplicates:
  1. MessageEntityTextUrl  (hyperlinked text → hidden URL)
  2. MessageEntityUrl      (plain-text URL in message body)
  3. Regex fallback        (catches anything the entity parser missed)
  4. Inline keyboard buttons (KeyboardButtonUrl in reply_markup)
  5. Webpage preview embeds (MessageMediaWebPage in media)
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from urllib.parse import urlparse
from typing import List, Optional

# Telethon entity types (imported lazily so tests can mock them)
try:
    from telethon.tl.types import (
        MessageEntityTextUrl,
        MessageEntityUrl,
        KeyboardButtonUrl,
        MessageMediaWebPage,
    )
except ImportError:
    MessageEntityTextUrl = None  # type: ignore[assignment, misc]
    MessageEntityUrl = None      # type: ignore[assignment, misc]
    KeyboardButtonUrl = None     # type: ignore[assignment, misc]
    MessageMediaWebPage = None   # type: ignore[assignment, misc]

# ── Data Model ────────────────────────────────────────────────────────

@dataclass
class LinkRecord:
    url: str
    domain: str
    anchor_text: Optional[str] = None
    source: str = ""             # "entity_texturl" | "entity_url" | "regex" | "button" | "webpage_preview"
    message_id: int = 0
    message_date: Optional[datetime] = None
    channel_name: str = ""
    forward_from: Optional[str] = None


# ── Regex ─────────────────────────────────────────────────────────────

URL_REGEX = re.compile(
    r'https?://[^\s<>"{}|\\^`\[\]\'()]+',
    re.IGNORECASE,
)


def _extract_domain(url: str) -> str:
    """Return domain without 'www.' prefix."""
    try:
        netloc = urlparse(url).netloc
        return netloc.replace("www.", "") if netloc else ""
    except Exception:
        return ""


def _dedup_key(message_id: int, url: str) -> tuple:
    return (message_id, url.strip("/").lower())


# ── Public API ────────────────────────────────────────────────────────

def extract_links(
    message_dict: dict,
    raw_message=None,
) -> List[LinkRecord]:
    """
    Extract URLs from a Telegram message using five methods.

    Parameters
    ----------
    message_dict : dict
        Must contain at least: message_id, text, date, channel_name.
        Optionally: forward_from.
    raw_message : telethon.tl.types.Message | None
        The original Telethon message object (for entity/button/media access).

    Returns
    -------
    List[LinkRecord]
        Deduplicated list of extracted URLs.
    """
    msg_id = message_dict.get("message_id", 0)
    text = message_dict.get("text", "") or ""
    date = message_dict.get("date")
    channel = message_dict.get("channel_name", "")
    forward_from = message_dict.get("forward_from")

    seen_keys: set[tuple] = set()
    results: list[LinkRecord] = []

    def _add(url: str, source: str, anchor: str | None = None):
        key = _dedup_key(msg_id, url)
        if key in seen_keys:
            return
        seen_keys.add(key)
        results.append(LinkRecord(
            url=url,
            domain=_extract_domain(url),
            anchor_text=anchor,
            source=source,
            message_id=msg_id,
            message_date=date,
            channel_name=channel,
            forward_from=forward_from,
        ))

    # ── METHOD 1: MessageEntityTextUrl (hidden URL behind anchor text) ──
    entities = []
    if raw_message is not None:
        entities = getattr(raw_message, "entities", None) or []

    if MessageEntityTextUrl is not None:
        for ent in entities:
            if isinstance(ent, MessageEntityTextUrl):
                anchor = text[ent.offset : ent.offset + ent.length]
                _add(ent.url, "entity_texturl", anchor)

    # ── METHOD 2: MessageEntityUrl (plain-text URL) ─────────────────────
    if MessageEntityUrl is not None:
        for ent in entities:
            if isinstance(ent, MessageEntityUrl):
                url = text[ent.offset : ent.offset + ent.length]
                _add(url, "entity_url")

    # ── METHOD 3: Regex fallback ────────────────────────────────────────
    for url in URL_REGEX.findall(text):
        _add(url, "regex")

    # ── METHOD 4: Inline keyboard buttons ───────────────────────────────
    #    These are the "boxes" / bot buttons visible below messages.
    #    They contain URLs that are NOT in the message text at all.
    if raw_message is not None:
        markup = getattr(raw_message, "reply_markup", None)
        if markup is not None:
            for row in getattr(markup, "rows", []):
                for button in getattr(row, "buttons", []):
                    btn_url = getattr(button, "url", None)
                    if btn_url:
                        btn_label = getattr(button, "text", "")
                        _add(btn_url, "button", btn_label)

    # ── METHOD 5: Webpage preview / embed (MessageMediaWebPage) ─────────
    #    When a message has a link preview card, the URL is in msg.media.
    if raw_message is not None and MessageMediaWebPage is not None:
        media = getattr(raw_message, "media", None)
        if media is not None and isinstance(media, MessageMediaWebPage):
            webpage = getattr(media, "webpage", None)
            if webpage is not None:
                wp_url = getattr(webpage, "url", None)
                if wp_url:
                    _add(wp_url, "webpage_preview")

    return results
