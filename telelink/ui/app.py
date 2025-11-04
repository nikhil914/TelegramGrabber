"""
TeleLink — Complete Streamlit UI (5 tabs)

Tabs: 🔐 Auth │ 📡 Scrape │ 💬 Messages │ 🔗 Links │ 📊 Stats
"""
from __future__ import annotations

import sys, os, asyncio, time, re
from pathlib import Path
from datetime import datetime, timedelta, timezone

import streamlit as st
import pandas as pd
from dotenv import load_dotenv

# Add parent dir to path so we can import sibling modules
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import DB_PATH, SESSION_NAME, APP_TITLE, BATCH_SIZE, wait_time
import db as database
from link_extractor import extract_links
from html_import import parse_telegram_html
from telegram_client import (
    TelethonWrapper,
    TwoFARequired,
    NotMemberError,
    InvalidChannelError,
    AccountError,
    InvalidOTPError,
)

# ── Page Config ───────────────────────────────────────────────────────
st.set_page_config(
    layout="wide",
    page_title="TeleLink",
    page_icon="🔗",
    initial_sidebar_state="collapsed",
)

# ── Load .env ─────────────────────────────────────────────────────────
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

# ── DB Connection (cached at process level) ───────────────────────────

@st.cache_resource
def get_conn():
    return database.init_db(DB_PATH)


# ── Telethon Manager (Queue-like Bridge) ──────────────────────────────
#    Streamlit wipes global module variables on every user action.
#    By wrapping the entire Manager in @st.cache_resource, we ensure
#    the background thread, event loop, and TelegramClient survive
#    all reruns and act as a unified queue for all async requests.

import threading
import concurrent.futures

class TelethonManager:
    def __init__(self):
        self._loop: asyncio.AbstractEventLoop = asyncio.new_event_loop()
        def _run():
            asyncio.set_event_loop(self._loop)
            self._loop.run_forever()
        self._thread: threading.Thread = threading.Thread(target=_run, daemon=True)
        self._thread.start()

        self._client: TelethonWrapper | None = None
        self._api_id: int | None = None
        self._api_hash: str | None = None

    def run_async(self, coro):
        """Submit a coroutine to the background queue and wait for the result."""
        if not self._loop or self._loop.is_closed():
            raise RuntimeError("Background event loop is not running.")
        future = asyncio.run_coroutine_threadsafe(coro, self._loop)
        return future.result(timeout=300)

    def get_client(self, api_id: int, api_hash: str) -> TelethonWrapper:
        """Get the singleton client, creating it ON the background thread if missing."""
        if self._client and self._api_id == api_id and self._api_hash == api_hash:
            return self._client
        
        # New credentials or first run — clean up any old instance
        if self._client:
            self.disconnect_and_clear()

        self._api_id = api_id
        self._api_hash = api_hash

        # Clean up stale SQLite journal files (safe to do from main thread)
        for ext in ("-journal", "-wal", "-shm"):
            p = Path(str(SESSION_NAME) + ext)
            try:
                if p.exists(): p.unlink()
            except OSError:
                pass

        # Create the client ON the background event loop thread
        async def _create():
            return TelethonWrapper(api_id, api_hash, SESSION_NAME, loop=self._loop)

        self._client = self.run_async(_create())
        return self._client

    def disconnect_and_clear(self):
        """Safely disconnect the client and clear it (used for logout)."""
        if self._client:
            try:
                self.run_async(self._client.disconnect())
            except Exception:
                pass
        self._client = None
        self._api_id = None
        self._api_hash = None


@st.cache_resource
def get_telethon_manager() -> TelethonManager:
    """Streamlit singleton: survives all page reruns and tabs."""
    return TelethonManager()

# Helper aliases for easier refactoring
def _get_or_create_client(api_id: int, api_hash: str) -> TelethonWrapper:
    return get_telethon_manager().get_client(api_id, api_hash)

def run_async(coro):
    return get_telethon_manager().run_async(coro)

def _clear_client_cache():
    get_telethon_manager().disconnect_and_clear()



# ── Session State Defaults ────────────────────────────────────────────

_defaults = {
    "authenticated": False,
    "phone": "",
    "phone_code_hash": "",
    "otp_sent": False,
    "need_2fa": False,
    "auth_status": "❌ Not Connected",
    "channels": [],       # list of channel info dicts
    "scraping": False,
}
for k, v in _defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v


# ── Detect saved session (no auto-connect) ────────────────────────────
_session_path = Path(SESSION_NAME)
_session_file_exists = _session_path.exists() or Path(str(_session_path) + ".session").exists()


# ── Helper: mask sensitive strings ────────────────────────────────────

def _mask(val: str, show: int = 6) -> str:
    if len(val) <= show:
        return val
    return val[:show] + "•" * (len(val) - show)


# ══════════════════════════════════════════════════════════════════════
# CUSTOM CSS
# ══════════════════════════════════════════════════════════════════════

st.markdown("""
<style>
    /* Main background & font */
    .stApp {
        background: linear-gradient(135deg, #0f0c29 0%, #1a1a2e 40%, #16213e 100%);
        color: #e0e0e0;
        font-family: 'Inter', 'Segoe UI', sans-serif;
    }

    /* Header gradient text */
    .app-title {
        background: linear-gradient(90deg, #00d2ff, #7b2ff7, #ff6b6b);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-size: 2.2rem;
        font-weight: 800;
        letter-spacing: -0.5px;
        margin-bottom: 0.2rem;
    }
    .app-subtitle {
        color: #888;
        font-size: 0.95rem;
        margin-bottom: 1.5rem;
    }

    /* Tabs styling */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        background: rgba(255,255,255,0.03);
        border-radius: 12px;
        padding: 6px;
    }
    .stTabs [data-baseweb="tab"] {
        border-radius: 10px;
        padding: 10px 20px;
        font-weight: 600;
        transition: all 0.2s ease;
    }
    .stTabs [aria-selected="true"] {
        background: linear-gradient(135deg, #7b2ff7, #00d2ff) !important;
        color: white !important;
        box-shadow: 0 4px 15px rgba(123, 47, 247, 0.3);
    }

    /* Metric cards */
    [data-testid="stMetric"] {
        background: rgba(255,255,255,0.04);
        border: 1px solid rgba(255,255,255,0.08);
        border-radius: 14px;
        padding: 18px 20px;
        transition: transform 0.2s ease, border-color 0.2s ease;
    }
    [data-testid="stMetric"]:hover {
        transform: translateY(-2px);
        border-color: rgba(123, 47, 247, 0.4);
    }
    [data-testid="stMetricValue"] {
        font-size: 1.6rem !important;
        font-weight: 700 !important;
        background: linear-gradient(90deg, #00d2ff, #7b2ff7);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }

    /* Buttons */
    .stButton > button {
        border-radius: 10px;
        font-weight: 600;
        border: 1px solid rgba(255,255,255,0.1);
        transition: all 0.25s ease;
    }
    .stButton > button:hover {
        transform: translateY(-1px);
        box-shadow: 0 6px 20px rgba(123, 47, 247, 0.25);
    }
    .stButton > button[kind="primary"] {
        background: linear-gradient(135deg, #7b2ff7, #00d2ff) !important;
        color: white !important;
    }

    /* DataFrames */
    .stDataFrame {
        border-radius: 12px;
        overflow: hidden;
    }

    /* Expander */
    .streamlit-expanderHeader {
        border-radius: 10px;
        font-weight: 600;
    }

    /* Download buttons */
    .stDownloadButton > button {
        border-radius: 10px;
        font-weight: 600;
    }

    /* Cards for info panels */
    .info-card {
        background: rgba(255,255,255,0.04);
        border: 1px solid rgba(255,255,255,0.08);
        border-radius: 14px;
        padding: 20px;
        margin: 8px 0;
    }
</style>
""", unsafe_allow_html=True)


# ── Title ─────────────────────────────────────────────────────────────
st.markdown('<div class="app-title">🔗 TeleLink</div>', unsafe_allow_html=True)
st.markdown('<div class="app-subtitle">Telegram Channel Message & Link Extractor</div>', unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════
# TABS
# ══════════════════════════════════════════════════════════════════════

tab_auth, tab_scrape, tab_messages, tab_links, tab_stats, tab_opener = st.tabs(
    ["🔐 Auth", "📡 Scrape", "💬 Messages", "🔗 Links", "📊 Stats", "🚀 Opener"]
)


# ══════════════════════════════════════════════════════════════════════
# TAB 1 — AUTH
# ══════════════════════════════════════════════════════════════════════

with tab_auth:
    col_form, col_status = st.columns([3, 2], gap="large")

    with col_form:
        st.subheader("🔐 Telegram Authentication")

        api_id = st.text_input(
            "Telegram API ID",
            value=os.environ.get("TELEGRAM_API_ID", ""),
            type="password",
            key="api_id_input",
        )
        api_hash = st.text_input(
            "Telegram API Hash",
            value=os.environ.get("TELEGRAM_API_HASH", ""),
            type="password",
            key="api_hash_input",
        )
        phone = st.text_input(
            "Phone Number (with country code)",
            value=os.environ.get("TELEGRAM_PHONE", ""),
            placeholder="+971501234567",
            key="phone_input",
        )

        # ── Restore from saved session ─────────────────────────
        # Auto-login if .env credentials match a valid .session on disk
        _api_id_env = os.environ.get("TELEGRAM_API_ID", "")
        _api_hash_env = os.environ.get("TELEGRAM_API_HASH", "")
        
        if not st.session_state["authenticated"] and _session_file_exists and _api_id_env and _api_hash_env:
            # We don't need a button, we can just quietly verify in the background
            try:
                client = _get_or_create_client(int(_api_id_env), _api_hash_env)
                run_async(client.connect())
                if run_async(client.is_authorized()):
                    st.session_state["authenticated"] = True
                    st.session_state["auth_status"] = "✅ Connected"
                    # Rerun to switch tabs
                    st.rerun()
            except Exception:
                pass # Fall back to the manual form below
        
        if not st.session_state["authenticated"] and _session_file_exists and api_id and api_hash:
            st.info("📁 A saved session file was found. You can restore your login without OTP.")
            if st.button("🔄 Restore Session", type="primary", key="btn_restore"):
                try:
                    client = _get_or_create_client(int(api_id), api_hash)
                    run_async(client.connect())
                    if run_async(client.is_authorized()):
                        st.session_state["authenticated"] = True
                        st.session_state["phone"] = phone
                        st.session_state["auth_status"] = "✅ Connected"
                        st.success("✅ Session restored successfully!")
                        from dotenv import set_key
                        env_path = Path(__file__).resolve().parent.parent / ".env"
                        set_key(env_path, "TELEGRAM_API_ID", str(api_id))
                        set_key(env_path, "TELEGRAM_API_HASH", api_hash)
                        if phone: set_key(env_path, "TELEGRAM_PHONE", phone)
                        st.rerun()
                    else:
                        st.warning("⚠️ Session file exists but is no longer valid. Please login with OTP.")
                except Exception as exc:
                    st.error(f"❌ Restore failed: {exc}")

        # ── Connect & Send OTP ─────────────────────────────────
        if not st.session_state["otp_sent"] and not st.session_state["authenticated"]:
            if st.button("🔌 Connect & Send OTP", type="primary", key="btn_connect"):
                if not api_id or not api_hash or not phone:
                    st.error("Please fill in all three fields.")
                else:
                    try:
                        client = _get_or_create_client(
                            int(api_id), api_hash
                        )
                        run_async(client.connect())

                        # Check if already authorised (session exists)
                        if run_async(client.is_authorized()):
                            st.session_state["authenticated"] = True
                            st.session_state["phone"] = phone
                            st.session_state["auth_status"] = "✅ Connected"
                            st.success("✅ Already authenticated via saved session!")
                            st.rerun()
                        else:
                            pch = run_async(client.send_code(phone))
                            st.session_state["phone_code_hash"] = pch
                            st.session_state["phone"] = phone
                            st.session_state["otp_sent"] = True
                            st.success("📲 OTP sent to your Telegram app!")
                            st.rerun()
                    except AccountError:
                        st.error("❌ Account is deactivated or banned.")
                    except Exception as exc:
                        st.error(f"❌ Connection failed: {exc}")

        # ── OTP Verification ───────────────────────────────────
        if st.session_state["otp_sent"] and not st.session_state["authenticated"]:
            if not st.session_state["need_2fa"]:
                otp_code = st.text_input(
                    "Enter OTP from Telegram", max_chars=6, key="otp_input"
                )
                if st.button("✅ Verify OTP", key="btn_verify"):
                    try:
                        client = _get_or_create_client(int(api_id), api_hash)
                        run_async(client.sign_in(
                            st.session_state["phone"],
                            otp_code,
                            st.session_state["phone_code_hash"],
                        ))
                        st.session_state["authenticated"] = True
                        st.session_state["auth_status"] = "✅ Connected"
                        
                        # Save to .env permanently
                        from dotenv import set_key
                        env_path = Path(__file__).resolve().parent.parent / ".env"
                        set_key(env_path, "TELEGRAM_API_ID", str(api_id))
                        set_key(env_path, "TELEGRAM_API_HASH", api_hash)
                        if st.session_state.get("phone"):
                            set_key(env_path, "TELEGRAM_PHONE", st.session_state["phone"])
                        
                        st.success("✅ Authenticated successfully!")
                        st.rerun()
                    except TwoFARequired:
                        st.session_state["need_2fa"] = True
                        st.warning("🔒 Two-factor authentication required.")
                        st.rerun()
                    except InvalidOTPError:
                        st.error("❌ Invalid OTP code. Please try again.")
                    except Exception as exc:
                        st.error(f"❌ Sign-in failed: {exc}")

            # ── 2FA ────────────────────────────────────────────
            if st.session_state["need_2fa"]:
                twofa_pw = st.text_input(
                    "Two-Factor Auth Password", type="password", key="2fa_input"
                )
                if st.button("🔓 Submit 2FA", key="btn_2fa"):
                    try:
                        client = _get_or_create_client(int(api_id), api_hash)
                        run_async(client.sign_in_2fa(twofa_pw))
                        st.session_state["authenticated"] = True
                        st.session_state["need_2fa"] = False
                        st.session_state["auth_status"] = "✅ Connected"
                        
                        # Save to .env permanently
                        from dotenv import set_key
                        env_path = Path(__file__).resolve().parent.parent / ".env"
                        set_key(env_path, "TELEGRAM_API_ID", str(api_id))
                        set_key(env_path, "TELEGRAM_API_HASH", api_hash)
                        if st.session_state.get("phone"):
                            set_key(env_path, "TELEGRAM_PHONE", st.session_state["phone"])
                            
                        st.success("✅ Authenticated with 2FA!")
                        st.rerun()
                    except Exception as exc:
                        st.error(f"❌ 2FA failed: {exc}")

        # ── Authenticated state ────────────────────────────────
        if st.session_state["authenticated"]:
            st.success(f"✅ Authenticated as **{st.session_state['phone']}**")
            if st.button("🚪 Logout", key="btn_logout"):
                try:
                    _api_id_l = os.environ.get("TELEGRAM_API_ID", "")
                    _api_hash_l = os.environ.get("TELEGRAM_API_HASH", "")
                    if _api_id_l and _api_hash_l:
                        c = _get_or_create_client(int(_api_id_l), _api_hash_l)
                        run_async(c.disconnect())
                except Exception:
                    pass
                # Clear the cached client so a new one can be created
                _clear_client_cache()
                # Remove session file
                session_path = Path(SESSION_NAME)
                for ext in ("", ".session"):
                    p = Path(str(session_path) + ext) if ext else session_path
                    if p.exists():
                        p.unlink()
                # Reset state
                for k in list(_defaults.keys()):
                    st.session_state[k] = _defaults[k]
                st.rerun()

    with col_status:
        st.subheader("📊 Status")
        st.metric("Connection", st.session_state["auth_status"])

        session_path = Path(SESSION_NAME)
        session_exists = session_path.exists() or Path(str(session_path) + ".session").exists()
        if session_exists:
            st.info(f"📁 Session file: `{SESSION_NAME}`")

        st.markdown("---")
        st.markdown("#### 📖 How to Get API Credentials")
        st.markdown("""
1. Go to **[my.telegram.org/apps](https://my.telegram.org/apps)**
2. Log in with your phone number
3. Click **"Create Application"**
4. Copy **api_id** (number) and **api_hash** (string)
5. Paste them into the form on the left
        """)
        st.warning("🔒 Your credentials are stored **locally** in `.env` only — never sent to any server.")


# ══════════════════════════════════════════════════════════════════════
# TAB 2 — SCRAPE
# ══════════════════════════════════════════════════════════════════════

with tab_scrape:

    # ── HTML Import (works without auth) ──────────────────────
    with st.expander("📥 Import from Telegram Desktop HTML Export", expanded=False):
        st.caption(
            "Paste the path to an exported `messages.html` file from Telegram Desktop. "
            "This extracts messages and **inline button links** without needing API auth."
        )
        html_path = st.text_input(
            "HTML file path",
            placeholder=r"C:\Users\...\ChatExport_2026-02-22\messages.html",
            key="html_import_path",
        )
        if st.button("📥 Import", key="btn_html_import") and html_path:
            html_path = html_path.strip().strip('"')
            if not Path(html_path).exists():
                st.error(f"❌ File not found: {html_path}")
            else:
                try:
                    conn = get_conn()
                    parsed = parse_telegram_html(html_path)
                    total_msgs = 0
                    total_links = 0

                    # Derive a channel name from the HTML page title or folder
                    channel_name = Path(html_path).parent.name or "html_import"

                    from link_extractor import LinkRecord, _extract_domain

                    for msg in parsed:
                        # Save message
                        msg_dict = {
                            "message_id": msg.message_id,
                            "text": msg.text,
                            "date": msg.date,
                            "sender_id": 0,
                            "has_link": bool(msg.buttons or msg.text_links),
                            "channel_name": channel_name,
                            "forward_from": None,
                        }
                        database.save_messages(conn, [msg_dict])
                        total_msgs += 1

                        # Save button links as LinkRecord objects
                        for btn in msg.buttons:
                            lr = LinkRecord(
                                url=btn["url"],
                                domain=_extract_domain(btn["url"]),
                                anchor_text=btn["label"],
                                source="button",
                                message_id=msg.message_id,
                                message_date=msg.date,
                                channel_name=channel_name,
                                forward_from=None,
                            )
                            database.save_links(conn, [lr])
                            total_links += 1

                        # Save text links as LinkRecord objects
                        for url in msg.text_links:
                            lr = LinkRecord(
                                url=url,
                                domain=_extract_domain(url),
                                anchor_text=None,
                                source="html_text",
                                message_id=msg.message_id,
                                message_date=msg.date,
                                channel_name=channel_name,
                                forward_from=None,
                            )
                            database.save_links(conn, [lr])
                            total_links += 1

                    st.success(
                        f"✅ Imported **{total_msgs}** messages and **{total_links}** links "
                        f"from `{channel_name}`"
                    )
                    st.balloons()
                except Exception as exc:
                    st.error(f"❌ Import failed: {exc}")

    st.divider()

    if not st.session_state["authenticated"]:
        st.warning("⚠️ Please authenticate in the **🔐 Auth** tab first to scrape live channels.")
    else:
        conn = get_conn()
        _sid = os.environ.get("TELEGRAM_API_ID", "") or st.session_state.get("api_id_input", "")
        _shash = os.environ.get("TELEGRAM_API_HASH", "") or st.session_state.get("api_hash_input", "")
        if not _sid or not _shash:
            st.error("⚠️ API credentials not found. Please set them in the **🔐 Auth** tab or `.env` file.")
            st.stop()
        client: TelethonWrapper = _get_or_create_client(int(_sid), _shash)
        # Ensure connected (idempotent — no-op if already connected)
        run_async(client.connect())

        st.subheader("📡 Channel Manager")

        # ── Add Channel ────────────────────────────────────────
        add_col1, add_col2 = st.columns([4, 1])
        with add_col1:
            channel_input = st.text_input(
                "Channel username or invite link",
                placeholder="@channelname or https://t.me/channelname",
                key="channel_input",
            )
        with add_col2:
            st.markdown("<br>", unsafe_allow_html=True)
            add_clicked = st.button("➕ Add Channel", key="btn_add_channel")

        if add_clicked and channel_input:
            # Check for duplicates
            existing_names = [c["channel_name"] for c in st.session_state["channels"]]
            try:
                info = run_async(client.get_channel_info(channel_input))
                if info["channel_name"] in existing_names:
                    st.warning(f"Channel **{info['display_name']}** is already in the list.")
                else:
                    st.session_state["channels"].append(info)
                    database.upsert_channel(conn, info)
                    st.success(
                        f"✅ Added **{info['display_name']}** "
                        f"({info['member_count']:,} members)"
                    )
                    st.rerun()
            except NotMemberError:
                st.error("❌ You are not a member of this channel.")
            except InvalidChannelError:
                st.error("❌ Invalid channel username or link.")
            except Exception as exc:
                st.error(f"❌ Failed: {exc}")

        # ── Channel List ───────────────────────────────────────
        if st.session_state["channels"]:
            st.markdown("#### Added Channels")
            for i, ch in enumerate(st.session_state["channels"]):
                ch_col1, ch_col2, ch_col3, ch_col4 = st.columns([3, 1, 1, 1])
                with ch_col1:
                    st.markdown(
                        f"**{ch.get('display_name', '')}** "
                        f"(`@{ch.get('username', ch.get('channel_name', ''))}`)"
                    )
                with ch_col2:
                    st.caption(f"👥 {ch.get('member_count', 0):,}")
                with ch_col3:
                    if st.button("❌ Remove", key=f"rm_{i}"):
                        st.session_state["channels"].pop(i)
                        st.rerun()
                with ch_col4:
                    if st.button("🗑 Clear Data", key=f"clr_{i}"):
                        database.clear_channel(conn, ch["channel_name"])
                        st.success(f"Cleared data for {ch['display_name']}")
                        st.rerun()
        else:
            st.info("No channels added yet. Add one above to start scraping.")

        st.markdown("---")

        # ── Scrape Options ─────────────────────────────────────
        with st.expander("⚙️ Scrape Options", expanded=False):
            opt_col1, opt_col2 = st.columns(2)
            with opt_col1:
                from_date = st.date_input(
                    "From Date",
                    value=datetime(2015, 1, 1),
                    key="from_date",
                )
                keyword_filter = st.text_input(
                    "Keyword filter (optional)", key="keyword_filter"
                )
                links_only = st.toggle(
                    "Extract links only (skip messages without URLs)",
                    value=False,
                    key="links_only",
                )
            with opt_col2:
                to_date = st.date_input("To Date", value=datetime.now(), key="to_date")
                limit_options = [100, 500, 1000, 5000, 10000, 50000, "ALL"]
                msg_limit = st.select_slider(
                    "Message limit", options=limit_options, value="ALL", key="msg_limit"
                )
                skip_scraped = st.toggle(
                    "Skip already-scraped messages (faster re-runs)",
                    value=True,
                    key="skip_scraped",
                )

        # ── Start / Stop Scraping ──────────────────────────────
        scrape_col1, scrape_col2 = st.columns([1, 1])
        with scrape_col1:
            start_clicked = st.button(
                "🚀 Start Scraping", type="primary", key="btn_start_scrape",
                disabled=not st.session_state["channels"],
            )
        with scrape_col2:
            stop_clicked = st.button("⏹ Stop Scraping", key="btn_stop_scrape")

        if stop_clicked:
            st.session_state["scraping"] = False

        if start_clicked and st.session_state["channels"]:
            st.session_state["scraping"] = True
            limit_val = None if msg_limit == "ALL" else int(msg_limit)
            from_dt = datetime(from_date.year, from_date.month, from_date.day, tzinfo=timezone.utc)
            to_dt = datetime(to_date.year, to_date.month, to_date.day, 23, 59, 59, tzinfo=timezone.utc)
            kw = keyword_filter.strip() if keyword_filter else None

            results_summary = []

            for ch in st.session_state["channels"]:
                if not st.session_state["scraping"]:
                    break
                ch_name = ch["channel_name"]
                st.markdown(f"#### Scraping **{ch.get('display_name', ch_name)}**…")
                progress_bar = st.progress(0, text="Starting…")
                status_text = st.empty()
                start_time = time.time()

                # Incremental scraping (REC-02)
                min_id = 0
                if skip_scraped:
                    min_id = database.get_last_message_id(conn, ch_name)

                # Mutable state dict — used instead of nonlocal (Streamlit runs at module level)
                state = {"fetched": 0, "links": 0, "msgs": [], "link_recs": []}

                # Create stop event
                stop_event = asyncio.Event()

                # Thread-safe state for UI updates
                bg_progress = {"count": 0, "msg": "Starting..."}

                def progress_cb(count, msg):
                    # Only update memory. DO NOT call st.x() from this background thread!
                    bg_progress["count"] = count
                    bg_progress["msg"] = msg

                async def _do_scrape():
                    async for msg_dict in client.fetch_messages(
                        ch_name,
                        limit=limit_val,
                        from_date=from_dt,
                        to_date=to_dt,
                        keyword=kw,
                        progress_callback=progress_cb,
                        stop_event=stop_event,
                        min_id=min_id,
                    ):
                        if stop_event.is_set():
                            break

                        raw = msg_dict.pop("raw_message", None)

                        # Extract links
                        links = extract_links(msg_dict, raw)
                        if links_only and not links:
                            continue

                        state["msgs"].append(msg_dict)
                        state["link_recs"].extend(links)
                        state["links"] += len(links)
                        state["fetched"] += 1

                        # Flush batch periodically
                        if len(state["msgs"]) >= BATCH_SIZE:
                            database.save_messages(conn, state["msgs"])
                            database.save_links(conn, state["link_recs"])
                            state["msgs"].clear()
                            state["link_recs"].clear()

                try:
                    import time
                    # Submit to background
                    future = get_telethon_manager()._loop.create_task(_do_scrape())
                    asyncio.run_coroutine_threadsafe(asyncio.wait([future]), get_telethon_manager()._loop)
                    
                    # Monitor safely from Streamlit thread
                    while not future.done():
                        # Read background state
                        c = bg_progress["count"]
                        m = bg_progress["msg"]
                        
                        # Update UI
                        state["fetched"] = c
                        status_text.markdown(f"📨 **{c:,}** messages fetched — **{state['links']:,}** links found so far")
                        if limit_val:
                            progress_bar.progress(min(c / limit_val, 1.0), text=m)
                            
                        # Keep Streamlit responsive
                        if not st.session_state["scraping"]:
                            # User clicked Stop in UI
                            get_telethon_manager().run_async(asyncio.sleep(0)) # kick loop
                            stop_event.set()
                            break
                            
                        time.sleep(0.5)

                    # Gather any exceptions
                    future.result()

                except Exception as exc:
                    import traceback
                    err_str = traceback.format_exc()
                    st.error(f"❌ Error scraping {ch_name}:\n```python\n{err_str}\n```")

                # Flush remaining
                if state["msgs"]:
                    database.save_messages(conn, state["msgs"])
                if state["link_recs"]:
                    database.save_links(conn, state["link_recs"])

                elapsed = time.time() - start_time
                progress_bar.progress(1.0, text="✅ Done")

                # Update channel stats
                database.upsert_channel(conn, {
                    "channel_name": ch_name,
                    "display_name": ch.get("display_name", ""),
                    "member_count": ch.get("member_count", 0),
                    "last_scraped": datetime.now().isoformat(),
                    "message_count": state["fetched"],
                    "link_count": state["links"],
                })

                results_summary.append({
                    "Channel": ch.get("display_name", ch_name),
                    "Messages": state["fetched"],
                    "Links": state["links"],
                    "Time (s)": round(elapsed, 1),
                })

            st.session_state["scraping"] = False

            if results_summary:
                st.balloons()
                st.markdown("### ✅ Scraping Complete")
                st.dataframe(
                    pd.DataFrame(results_summary), use_container_width=True
                )


# ══════════════════════════════════════════════════════════════════════
# TAB 3 — MESSAGES
# ══════════════════════════════════════════════════════════════════════

with tab_messages:
    conn = get_conn()
    channel_list = database.get_channel_list(conn)

    col1, col2, col3 = st.columns(3)
    with col1:
        search_msg = st.text_input("🔍 Search message text", key="msg_search")
    with col2:
        filter_channel = st.selectbox(
            "Filter by channel", ["All"] + channel_list, key="msg_channel"
        )
    with col3:
        link_filter = st.selectbox(
            "Filter", ["All", "With links only", "No links"], key="msg_link_filter"
        )

    has_link_val = None
    if link_filter == "With links only":
        has_link_val = True
    elif link_filter == "No links":
        has_link_val = False

    df_msgs = database.get_messages(
        conn,
        channel=filter_channel if filter_channel != "All" else None,
        keyword=search_msg if search_msg else None,
        has_link=has_link_val,
    )

    if df_msgs.empty:
        st.info("No messages found. Scrape a channel first in the **📡 Scrape** tab.")
    else:
        # Prepare display columns
        display_df = df_msgs[["message_date", "channel_name", "message_text", "has_link", "message_id"]].copy()
        display_df.columns = ["Date", "Channel", "Message", "Has Link", "Msg ID"]
        display_df["Message"] = display_df["Message"].apply(
            lambda x: (str(x)[:80] + "…") if x and len(str(x)) > 80 else x
        )
        display_df["Has Link"] = display_df["Has Link"].apply(lambda x: "✅" if x else "")

        st.dataframe(display_df, use_container_width=True, height=500)

        # Metrics
        total = len(df_msgs)
        with_links = int(df_msgs["has_link"].sum())
        pct = round(with_links / total * 100, 1) if total else 0

        m1, m2, m3 = st.columns(3)
        m1.metric("Total Messages", f"{total:,}")
        m2.metric("Messages with Links", f"{with_links:,}")
        m3.metric("% with Links", f"{pct}%")

        # Exports
        exp1, exp2 = st.columns(2)
        with exp1:
            csv_data = df_msgs.to_csv(index=False).encode("utf-8")
            ch_label = filter_channel if filter_channel != "All" else "all"
            st.download_button(
                "⬇ Download CSV",
                data=csv_data,
                file_name=f"telelink_messages_{ch_label}_{datetime.now().strftime('%Y-%m-%d')}.csv",
                mime="text/csv",
                key="msg_csv_dl",
            )
        with exp2:
            json_data = df_msgs.to_json(orient="records", indent=2)
            st.download_button(
                "⬇ Download JSON",
                data=json_data,
                file_name=f"telelink_messages_{ch_label}_{datetime.now().strftime('%Y-%m-%d')}.json",
                mime="application/json",
                key="msg_json_dl",
            )


# ══════════════════════════════════════════════════════════════════════
# TAB 4 — LINKS
# ══════════════════════════════════════════════════════════════════════

with tab_links:
    conn = get_conn()
    channel_list = database.get_channel_list(conn)
    domain_list = database.get_domain_list(conn)

    f1, f2, f3, f4 = st.columns(4)
    with f1:
        search_url = st.text_input("🔍 Search URLs", key="link_search")
    with f2:
        domain_filter = st.selectbox("Domain", ["All"] + domain_list, key="link_domain")
    with f3:
        channel_filter = st.selectbox(
            "Channel", ["All"] + channel_list, key="link_channel"
        )
    with f4:
        unique_only = st.toggle("Unique URLs only", value=True, key="link_unique")

    df_links = database.get_links(
        conn,
        channel=channel_filter if channel_filter != "All" else None,
        domain=domain_filter if domain_filter != "All" else None,
        unique_only=unique_only,
        search=search_url if search_url else None,
    )

    if df_links.empty:
        st.info("No links found. Scrape a channel first in the **📡 Scrape** tab.")
    else:
        # Metrics
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Total Links", f"{len(df_links):,}")
        m2.metric("Unique URLs", f"{df_links['url'].nunique():,}")
        m3.metric("Unique Domains", f"{df_links['domain'].nunique():,}")
        m4.metric("Channels Covered", f"{df_links['channel_name'].nunique():,}")

        # Display table — make URLs clickable
        display_links = df_links[["url", "domain", "anchor_text", "channel_name", "message_date", "source"]].copy()
        display_links.columns = ["URL", "Domain", "Anchor Text", "Channel", "Date", "Source"]
        display_links["Anchor Text"] = display_links["Anchor Text"].fillna("")
        display_links["Source"] = display_links["Source"].fillna("")

        # Render as clickable HTML
        def _make_clickable(url):
            short = (str(url)[:60] + "…") if len(str(url)) > 60 else str(url)
            return f'<a href="{url}" target="_blank" style="color:#00d2ff;">{short}</a>'

        html_df = display_links.copy()
        html_df["URL"] = html_df["URL"].apply(_make_clickable)
        st.markdown(
            html_df.to_html(escape=False, index=False),
            unsafe_allow_html=True,
        )

        # Exports
        exp1, exp2, exp3 = st.columns(3)
        ch_label = channel_filter if channel_filter != "All" else "all"
        
        with exp1:
            st.markdown("**(1) Grouped Links (URL, Domain, Anchor)**")
            import io
            import csv
            
            out1 = io.StringIO()
            w1 = csv.writer(out1)
            
            if not df_links.empty:
                # Fetch message texts
                msg_ids = tuple(df_links["message_id"].dropna().unique().astype(int).tolist())
                msg_dict = {}
                if msg_ids:
                    placeholders = ",".join("?" * len(msg_ids))
                    try:
                        df_msgs = pd.read_sql_query(
                            f"SELECT message_id, message_text FROM messages WHERE message_id IN ({placeholders})",
                            conn, params=msg_ids,
                        )
                        msg_dict = dict(zip(df_msgs.message_id, df_msgs.message_text))
                    except Exception:
                        pass
                
                for msg_id, group in df_links.groupby("message_id"):
                    text = msg_dict.get(msg_id, f"Message ID: {msg_id}")
                    w1.writerow([f"Message: {text}"])
                    w1.writerow(["URL", "Domain", "Anchor Text"])
                    for _, row in group.iterrows():
                        w1.writerow([
                            row.get("url", ""), 
                            row.get("domain", ""), 
                            row.get("anchor_text", "")
                        ])
                    w1.writerow([]) # Blank row
                    
            st.download_button(
                "⬇ Export Detailed CSV",
                data=out1.getvalue().encode("utf-8"),
                file_name=f"telelink_detailed_{ch_label}_{datetime.now().strftime('%Y-%m-%d')}.csv",
                mime="text/csv",
                key="csv_dl_1",
            )

        with exp2:
            st.markdown("**(2) Simple Grouped (URL Only)**")
            out2 = io.StringIO()
            w2 = csv.writer(out2)
            
            if not df_links.empty:
                for msg_id, group in df_links.groupby("message_id"):
                    text = msg_dict.get(msg_id, f"Message ID: {msg_id}")
                    w2.writerow([f"Message: {text}"])
                    for _, row in group.iterrows():
                        w2.writerow([row.get("url", ""), ""])
                    w2.writerow([])
                    
            st.download_button(
                "⬇ Export Simple CSV",
                data=out2.getvalue().encode("utf-8"),
                file_name=f"telelink_simple_{ch_label}_{datetime.now().strftime('%Y-%m-%d')}.csv",
                mime="text/csv",
                key="csv_dl_2",
            )
        with exp2:
            json_data = df_links.to_json(orient="records", indent=2)
            st.download_button(
                "⬇ Export JSON",
                data=json_data,
                file_name=f"telelink_links_{ch_label}_{datetime.now().strftime('%Y-%m-%d')}.json",
                mime="application/json",
                key="link_json_dl",
            )
        with exp3:
            if st.button("📋 Show All URLs as Plain Text", key="btn_plain_urls"):
                all_urls = "\n".join(df_links["url"].tolist())
                st.code(all_urls, language=None)


# ══════════════════════════════════════════════════════════════════════
# TAB 5 — STATS
# ══════════════════════════════════════════════════════════════════════

with tab_stats:
    conn = get_conn()

    # Section 1 — Per-Channel Summary
    st.subheader("📊 Per-Channel Summary")
    stats_df = database.get_channel_stats(conn)
    if stats_df.empty:
        st.info("No channel data yet. Scrape some channels first!")
    else:
        st.dataframe(stats_df, use_container_width=True)

    st.markdown("---")

    # Need links data for charts
    all_links = database.get_links(conn)

    if not all_links.empty:
        # Section 2 — Top 20 Domains
        st.subheader("🌐 Top 20 Domains")
        domain_counts = (
            all_links.groupby("domain")
            .size()
            .sort_values(ascending=False)
            .head(20)
        )
        st.bar_chart(domain_counts)

        st.markdown("---")

        # Section 3 — Links Over Time
        st.subheader("📈 Links Over Time")
        if "message_date" in all_links.columns:
            links_by_date = (
                all_links["message_date"]
                .str[:10]
                .value_counts()
                .sort_index()
            )
            st.line_chart(links_by_date)

        st.markdown("---")

        # Section 4 — Link Source Breakdown
        st.subheader("🔍 Link Source Breakdown")
        source_counts = all_links["source"].value_counts()
        st.bar_chart(source_counts)
    else:
        st.info("No link data available to chart. Scrape some channels first!")


# ══════════════════════════════════════════════════════════════════════
# TAB 6 — OPENER
# ══════════════════════════════════════════════════════════════════════

with tab_opener:
    st.subheader("🚀 Batch Link Opener")
    st.markdown("Upload a **Simple CSV** file to automatically open the links one-by-one in your default browser.")
    st.info("💡 **Note:** Python will strictly wait the number of seconds you configure below before opening the next tab. It does not literally 'detect' the web redirect finish, so assign enough time for your browser to load!")
    
    if "opener_state" not in st.session_state:
        st.session_state["opener_state"] = {"running": False, "stop": False, "index": 0, "total": 0}
        
    col_up, col_conf = st.columns([2, 1])
    
    with col_up:
        uploaded_file = st.file_uploader("Upload Simple CSV File", type=["csv"], key="opener_uploader")
        
    with col_conf:
        wait_time = st.slider(
            "Wait Time (seconds)",
            min_value=1,
            max_value=60,
            value=wait_time,
            help="Seconds to wait between opening tabs."
        )
        
    state = st.session_state["opener_state"]
        
    if uploaded_file is not None:
        try:
            content = uploaded_file.getvalue().decode("utf-8")
            urls_to_open = []
            for line in content.splitlines():
                line = line.strip().strip(",")
                if line.startswith("http://") or line.startswith("https://"):
                    urls_to_open.append(line)
                    
            if not urls_to_open:
                st.warning("No URLs found in the uploaded file.")
            else:
                st.success(f"📁 Found **{len(urls_to_open)}** URLs ready to open.")
                
                # Controls
                c1, c2, c3 = st.columns([1, 1, 3])
                with c1:
                    start_disabled = state["running"]
                    if st.button("🚀 Start Opening", type="primary", disabled=start_disabled):
                        state["running"] = True
                        state["stop"] = False
                        state["index"] = 0
                        state["total"] = len(urls_to_open)
                        
                        def opener_worker(urls, wait, st_ref):
                            import webbrowser
                            for u in urls:
                                if st_ref["stop"]:
                                    break
                                webbrowser.open_new_tab(u)
                                st_ref["index"] += 1
                                # Wait chunked to allow quick stoppage
                                for _ in range(wait * 10):
                                    if st_ref["stop"]: break
                                    time.sleep(0.1)
                            st_ref["running"] = False
                            
                        threading.Thread(target=opener_worker, args=(urls_to_open, wait_time, state), daemon=True).start()
                        st.rerun()
                        
                with c2:
                    stop_disabled = not state["running"]
                    if st.button("🛑 Stop", disabled=stop_disabled):
                        state["stop"] = True
                        st.rerun()
                
                # Status
                if state["running"]:
                    st.warning(f"⏳ **Running:** Opening links... ({state['index']} / {state['total']} opened)")
                    st.progress(state["index"] / state["total"] if state["total"] > 0 else 0.0)
                elif state["index"] > 0 and state["index"] == state["total"]:
                    st.success("✅ Finished opening all links!")
                elif state["index"] > 0 and state["stop"]:
                    st.error(f"🛑 Stopped at link {state['index']}.")
                    
        except Exception as e:
            st.error(f"Error parsing file: {e}")
