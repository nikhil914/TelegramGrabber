"""
TeleLink — HTML Import Module

Extracts messages and button links from Telegram Desktop's exported HTML files.
This provides a fallback when the Telegram API can't be used (private channels,
auth issues, etc.)
"""
from __future__ import annotations

import re
from pathlib import Path
from dataclasses import dataclass
from typing import List


@dataclass
class HTMLMessage:
    message_id: int
    text: str
    date: str
    buttons: list[dict]   # [{"label": "1-20", "url": "https://..."}]
    text_links: list[str] # URLs found in the text body


def parse_telegram_html(html_path: str) -> List[HTMLMessage]:
    """
    Parse a Telegram Desktop export HTML file.
    Returns list of HTMLMessage objects with text, buttons, and links.
    """
    html = Path(html_path).read_text(encoding="utf-8")

    # Split into individual message blocks
    # Each message ends right before the next message or end of history
    msg_blocks = re.split(
        r'(?=<div class="message (?:default|service) clearfix(?: joined)?")',
        html,
    )

    # Extract date from message div
    date_pattern = re.compile(
        r'title="(\d{2}\.\d{2}\.\d{4} \d{2}:\d{2}:\d{2}[^"]*)"'
    )

    # Message text
    text_pattern = re.compile(
        r'<div class="text">\s*(.*?)\s*</div>',
        re.DOTALL,
    )

    # Bot button links
    button_pattern = re.compile(
        r'<div class="bot_button">\s*<a[^>]*href="([^"]+)"[^>]*>.*?<div>\s*(.*?)\s*</div>',
        re.DOTALL,
    )

    # Message ID
    id_pattern = re.compile(r'id="message(\d+)"')

    # URL regex
    url_re = re.compile(r'https?://[^\s<>"\']+', re.IGNORECASE)

    # Inline <a href="..."> links in message text
    text_link_pattern = re.compile(r'<a[^>]*href="([^"]+)"[^>]*>')

    results: list[HTMLMessage] = []

    for block in msg_blocks:
        if 'class="message default clearfix"' not in block and 'class="message default clearfix joined"' not in block:
            continue

        # Get message ID
        id_match = id_pattern.search(block)
        if not id_match:
            continue
        msg_id = int(id_match.group(1))

        # Get date
        date_match = date_pattern.search(block)
        date_str = date_match.group(1) if date_match else ""

        # Get text (strip HTML tags)
        text_match = text_pattern.search(block)
        raw_text = text_match.group(1) if text_match else ""
        clean_text = re.sub(r'<[^>]+>', ' ', raw_text).strip()
        clean_text = re.sub(r'\s+', ' ', clean_text)

        # Get text-body links (from <a href> and plain URLs)
        text_links: list[str] = []
        if text_match:
            for link_match in text_link_pattern.finditer(raw_text):
                href = link_match.group(1)
                if href.startswith("http"):
                    text_links.append(href)
            for url_match in url_re.finditer(clean_text):
                url = url_match.group(0)
                if url not in text_links:
                    text_links.append(url)

        # Get button links
        buttons: list[dict] = []
        # Only look at bot_buttons_table section
        table_match = re.search(
            r'<table class="bot_buttons_table">(.*?)</table>',
            block,
            re.DOTALL,
        )
        if table_match:
            table_html = table_match.group(1)
            for btn_match in button_pattern.finditer(table_html):
                url = btn_match.group(1)
                label = re.sub(r'<[^>]+>', '', btn_match.group(2)).strip()
                buttons.append({"label": label, "url": url})

        # Only include messages that have links or buttons
        if buttons or text_links or clean_text:
            results.append(HTMLMessage(
                message_id=msg_id,
                text=clean_text,
                date=date_str,
                buttons=buttons,
                text_links=text_links,
            ))

    return results
