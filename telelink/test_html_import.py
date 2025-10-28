from html_import import parse_telegram_html

msgs = parse_telegram_html(r"C:\Users\Nikhil\Downloads\Telegram Desktop\ChatExport_2026-02-22\messages.html")
btn_msgs = [m for m in msgs if m.buttons]
total_btns = sum(len(m.buttons) for m in btn_msgs)

print(f"Total messages: {len(msgs)}")
print(f"Messages with buttons: {len(btn_msgs)}")
print(f"Total button links: {total_btns}")
print()

for m in btn_msgs:
    print(f"  {m.message_id}: \"{m.text[:50]}\" -> {len(m.buttons)} buttons")
    for btn in m.buttons:
        print(f"    [{btn['label']:15s}] -> {btn['url']}")
