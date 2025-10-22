"""
Test script: Extract ALL bot-button links from exported Telegram HTML.
Uses regex to directly grab <a href="..."> inside bot_button divs.
"""
import re
from pathlib import Path


def extract_button_links(html_path: str) -> list[dict]:
    """Parse the HTML and return all messages with their button links."""
    html = Path(html_path).read_text(encoding="utf-8")

    # Split into message blocks
    msg_pattern = re.compile(
        r'<div class="message default clearfix" id="(message\d+)">(.*?)</div>\s*</div>\s*(?=<div class="message|$)',
        re.DOTALL,
    )
    # Extract message text
    text_pattern = re.compile(r'<div class="text">\s*(.*?)\s*</div>', re.DOTALL)
    # Extract bot button links: <a ...href="URL">...<div>LABEL</div>...</a>
    button_pattern = re.compile(
        r'<div class="bot_button">\s*<a[^>]*href="([^"]+)"[^>]*>.*?<div>\s*(.*?)\s*</div>',
        re.DOTALL,
    )

    results = []
    for match in msg_pattern.finditer(html):
        msg_id = match.group(1)
        block = match.group(2)

        # Get message text (strip HTML tags)
        text_match = text_pattern.search(block)
        raw_text = text_match.group(1) if text_match else ""
        clean_text = re.sub(r'<[^>]+>', '', raw_text).strip()

        # Get all button links
        buttons = []
        for btn in button_pattern.finditer(block):
            url = btn.group(1)
            label = re.sub(r'<[^>]+>', '', btn.group(2)).strip()
            buttons.append({"label": label, "url": url})

        if buttons:
            results.append({
                "message_id": msg_id,
                "text": clean_text,
                "buttons": buttons,
            })

    return results


def main():
    html_path = r"C:\Users\Nikhil\Downloads\Telegram Desktop\ChatExport_2026-02-22\messages.html"
    results = extract_button_links(html_path)

    total_buttons = 0
    for msg in results:
        print(f"\n{'='*70}")
        print(f"📄 {msg['message_id']}  |  \"{msg['text']}\"")
        print(f"   {len(msg['buttons'])} buttons:")
        for btn in msg["buttons"]:
            print(f"     [{btn['label']:15s}] → {btn['url']}")
            total_buttons += 1

    print(f"\n{'='*70}")
    print(f"✅ Total messages with buttons: {len(results)}")
    print(f"✅ Total button links extracted: {total_buttons}")


if __name__ == "__main__":
    main()
