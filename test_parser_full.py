from telelink.html_import import parse_telegram_html
import sys

html_file = r"C:\Users\Nikhil\Downloads\Telegram Desktop\ChatExport_2026-02-22\messages.html"

print(f"Parsing {html_file}...")
results = parse_telegram_html(html_file)

print(f"\nTotal messages found: {len(results)}")

buttons = 0
for msg in results:
    if msg.buttons:
        buttons += len(msg.buttons)

print(f"Total inline buttons parsed: {buttons}")

# Let's see if 1101-1110 was caught
for msg in results:
    for btn in msg.buttons:
        if "1101" in btn["label"] or "110" in btn["label"]:
             print(f"Found match: ID {msg.message_id} -> {btn}")
