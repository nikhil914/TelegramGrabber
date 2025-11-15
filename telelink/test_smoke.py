"""Quick smoke test for db.py and link_extractor.py"""
import sys
sys.path.insert(0, '.')

from db import (
    init_db, save_messages, save_links, get_messages, get_links,
    get_channel_stats, upsert_channel, clear_channel, get_domain_list,
    get_last_message_id,
)
from link_extractor import extract_links, LinkRecord

# ── DB Tests ──────────────────────────────────────────────────────
conn = init_db(":memory:")
print("[OK] init_db")

save_messages(conn, [{
    "message_id": 1,
    "channel_name": "test_ch",
    "sender_id": 100,
    "text": "Hello https://example.com",
    "date": "2026-01-01",
    "has_link": True,
}])
print("[OK] save_messages")

# ── Link Extractor Tests ─────────────────────────────────────────
links = extract_links({
    "message_id": 1,
    "text": "Check https://github.com/repo and https://youtube.com/watch?v=123",
    "date": "2026-01-01",
    "channel_name": "test_ch",
})
assert len(links) == 2, f"Expected 2 links, got {len(links)}"
assert links[0].domain == "github.com"
assert links[1].domain == "youtube.com"
assert links[0].source == "regex"
print(f"[OK] extract_links — found {len(links)} links")

# Dedup test
links_dup = extract_links({
    "message_id": 2,
    "text": "https://example.com https://example.com",
    "date": "2026-01-01",
    "channel_name": "test_ch",
})
assert len(links_dup) == 1, f"Dedup failed: got {len(links_dup)}"
print("[OK] deduplication")

save_links(conn, links)
print("[OK] save_links")

df = get_messages(conn)
assert len(df) == 1
print(f"[OK] get_messages — {len(df)} rows")

df2 = get_links(conn)
assert len(df2) == 2
print(f"[OK] get_links — {len(df2)} rows")

domains = get_domain_list(conn)
assert "github.com" in domains
print(f"[OK] get_domain_list — {domains}")

upsert_channel(conn, {
    "channel_name": "test_ch",
    "display_name": "Test Channel",
    "member_count": 500,
})
stats = get_channel_stats(conn)
assert len(stats) == 1
print(f"[OK] upsert_channel + get_channel_stats")

last_id = get_last_message_id(conn, "test_ch")
assert last_id == 1
print(f"[OK] get_last_message_id = {last_id}")

clear_channel(conn, "test_ch")
assert len(get_messages(conn)) == 0
print("[OK] clear_channel")

print("\n✅ ALL TESTS PASSED")
