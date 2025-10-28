import re
html_file = r"C:\Users\Nikhil\Downloads\Telegram Desktop\ChatExport_2026-02-22\messages.html"
with open(html_file, 'r', encoding='utf-8') as f:
    html = f.read()

print("Searching for 'Ep 1101-1200'...")
idx = html.find('Ep 1101-1200')
if idx != -1:
    context = html[idx-300:idx+100]
    print("HTML around the missing message:")
    print("-" * 40)
    print(context)
    print("-" * 40)
    
    # Try the split manually on this chunk to see why it fails
    msg_blocks = re.split(
        r'(?=<div class="message (?:default|service) clearfix(?: joined)?")',
        context,
    )
    print(f"Number of blocks found in context: {len(msg_blocks)}")
    
