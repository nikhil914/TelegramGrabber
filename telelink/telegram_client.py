"""
TeleLink — Telegram MTProto Client Wrapper (Telethon)

Provides a fully async wrapper around Telethon with:
  - OTP / 2FA auth flow
  - Channel info retrieval
  - Message fetching with progress, date-range, keyword, and stop support
  - FloodWait handling with countdown callback
  - Exponential-backoff retries for connection errors
  - Incremental scraping via min_id
"""
from __future__ import annotations
import re as _re

import asyncio
import time
from datetime import datetime, timezone
from typing import AsyncGenerator, Callable, Optional

from telethon import TelegramClient
from telethon.errors import (
    FloodWaitError,
    SessionPasswordNeededError,
    ChannelPrivateError,
    UsernameInvalidError,
    UserDeactivatedError,
    PhoneCodeInvalidError,
)
from telethon.tl.types import MessageFwdHeader

from config import MAX_RETRIES, RETRY_DELAYS, BATCH_SIZE


# ── Custom Exceptions ─────────────────────────────────────────────────

class TwoFARequired(Exception):
    """Raised when 2-factor auth password is needed."""


class NotMemberError(Exception):
    def __init__(self, channel: str):
        super().__init__(f"Not a member of channel: {channel}")
        self.channel = channel


class InvalidChannelError(Exception):
    def __init__(self, channel: str):
        super().__init__(f"Invalid channel identifier: {channel}")
        self.channel = channel


class AccountError(Exception):
    """Raised when the Telegram account is deactivated / banned."""


class InvalidOTPError(Exception):
    """Raised when the OTP code is incorrect."""


# ── Wrapper ───────────────────────────────────────────────────────────

class TelethonWrapper:
    """High-level async wrapper around TelegramClient."""

    def __init__(self, api_id: int, api_hash: str, session_name: str, loop: asyncio.AbstractEventLoop | None = None):
        self.api_id = api_id
        self.api_hash = api_hash
        self.session_name = session_name
        self.client = TelegramClient(session_name, api_id, api_hash, loop=loop)
        self._phone_code_hash: str | None = None

    # ── Connection ────────────────────────────────────────────────────

    async def connect(self) -> bool:
        """Connect to Telegram servers (does NOT authenticate)."""
        for attempt in range(MAX_RETRIES):
            try:
                await self.client.connect()
                return True
            except (ConnectionError, OSError):
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(RETRY_DELAYS[attempt])
                else:
                    raise
        return False

    async def disconnect(self):
        await self.client.disconnect()

    async def is_authorized(self) -> bool:
        return await self.client.is_user_authorized()

    # ── Authentication ────────────────────────────────────────────────

    async def send_code(self, phone: str) -> str:
        """Send OTP to phone. Returns phone_code_hash."""
        try:
            result = await self.client.send_code_request(phone)
            self._phone_code_hash = result.phone_code_hash
            return result.phone_code_hash
        except UserDeactivatedError:
            raise AccountError()

    async def sign_in(
        self, phone: str, code: str, phone_code_hash: str
    ) -> bool:
        """Verify OTP code. May raise TwoFARequired."""
        try:
            await self.client.sign_in(
                phone=phone, code=code, phone_code_hash=phone_code_hash
            )
            return True
        except SessionPasswordNeededError:
            raise TwoFARequired()
        except PhoneCodeInvalidError:
            raise InvalidOTPError()

    async def sign_in_2fa(self, password: str) -> bool:
        """Submit 2-factor auth password."""
        await self.client.sign_in(password=password)
        return True

    # ── Identifier parsing ─────────────────────────────────────────────

    @staticmethod
    def _parse_identifier(identifier: str) -> str | int:
        """
        Normalise channel identifiers. Handles:
          - web.telegram.org URLs  (https://web.telegram.org/k/#-2179184691)
          - t.me links             (https://t.me/channelname)
          - @usernames             (@channelname)
          - raw numeric IDs        (-1002179184691)
        """
        identifier = identifier.strip()

        # web.telegram.org URL → extract numeric ID from hash fragment
        if "web.telegram.org" in identifier:
            m = _re.search(r'#(-?\d+)', identifier)
            if m:
                raw_id = int(m.group(1))
                # Web client uses plain negative IDs for channels;
                # Telethon needs the -100 prefix format.
                if raw_id < 0 and not str(raw_id).startswith("-100"):
                    return int(f"-100{abs(raw_id)}")
                return raw_id

        # Pure numeric string (possibly with minus sign)
        if identifier.lstrip("-").isdigit():
            return int(identifier)

        return identifier

    # ── Channel helpers ───────────────────────────────────────────────

    async def get_channel_info(self, identifier: str) -> dict:
        """Fetch channel metadata. Returns dict with name, id, etc."""
        resolved = self._parse_identifier(identifier)
        try:
            entity = await self.client.get_entity(resolved)
            full = await self.client.get_entity(entity)
            return {
                "name": getattr(entity, "username", None) or str(entity.id),
                "channel_name": getattr(entity, "username", None) or str(entity.id),
                "id": entity.id,
                "username": getattr(entity, "username", None),
                "member_count": getattr(full, "participants_count", 0) or 0,
                "display_name": getattr(entity, "title", "") or getattr(entity, "username", ""),
                "description": "",  # full chat info requires extra call
            }
        except ChannelPrivateError:
            raise NotMemberError(identifier)
        except (UsernameInvalidError, ValueError):
            raise InvalidChannelError(identifier)

    # ── Message Fetching ──────────────────────────────────────────────

    async def fetch_messages(
        self,
        identifier: str,
        limit: int | None = None,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
        keyword: str | None = None,
        progress_callback: Callable | None = None,
        stop_event: asyncio.Event | None = None,
        min_id: int = 0,
    ) -> AsyncGenerator[dict, None]:
        """
        Yield message dicts from a channel.

        Parameters
        ----------
        identifier : str
            Channel username, invite link, or numeric ID.
        limit : int | None
            Max messages to fetch (None = all).
        from_date, to_date : datetime | None
            Date range filter (UTC).
        keyword : str | None
            Telegram server-side search filter (REC-10).
        progress_callback : callable | None
            fn(fetched: int, msg: str) called periodically.
        stop_event : asyncio.Event | None
            Set externally to gracefully stop fetching.
        min_id : int
            Only fetch messages with id > min_id (incremental, REC-02).
        """
        resolved = self._parse_identifier(identifier)
        entity = await self.client.get_entity(resolved)

        # Build iter_messages kwargs
        iter_kwargs: dict = {
            "entity": entity,
            "limit": limit,
            "min_id": min_id,
        }
        if keyword:
            iter_kwargs["search"] = keyword  # REC-10
        if to_date:
            # offset_date returns messages BEFORE this date
            if to_date.tzinfo is None:
                to_date = to_date.replace(tzinfo=timezone.utc)
            iter_kwargs["offset_date"] = to_date

        fetched = 0
        try:
            async for msg in self.client.iter_messages(**iter_kwargs):
                # Stop signal
                if stop_event and stop_event.is_set():
                    break

                # Date range — skip messages outside from_date
                if from_date and msg.date:
                    msg_date = msg.date.replace(tzinfo=timezone.utc) if msg.date.tzinfo is None else msg.date
                    from_dt = from_date.replace(tzinfo=timezone.utc) if from_date.tzinfo is None else from_date
                    if msg_date < from_dt:
                        break  # messages are in reverse-chrono order

                # Determine forward source (REC-09)
                forward_from = None
                if msg.fwd_from and isinstance(msg.fwd_from, MessageFwdHeader):
                    if msg.fwd_from.from_name:
                        forward_from = msg.fwd_from.from_name
                    elif msg.fwd_from.from_id:
                        forward_from = str(msg.fwd_from.from_id)

                # Check if message has any link entities, buttons, or media
                has_link = False
                if msg.entities:
                    from telethon.tl.types import MessageEntityTextUrl, MessageEntityUrl
                    for ent in msg.entities:
                        if isinstance(ent, (MessageEntityTextUrl, MessageEntityUrl)):
                            has_link = True
                            break
                # Check inline keyboard buttons
                if not has_link and msg.reply_markup:
                    for row in getattr(msg.reply_markup, "rows", []):
                        for btn in getattr(row, "buttons", []):
                            if getattr(btn, "url", None):
                                has_link = True
                                break
                        if has_link:
                            break
                # Check webpage preview
                if not has_link and msg.media:
                    from telethon.tl.types import MessageMediaWebPage
                    if isinstance(msg.media, MessageMediaWebPage):
                        has_link = True
                # Regex fallback on text
                if not has_link and msg.message:
                    import re
                    has_link = bool(re.search(r'https?://', msg.message))

                channel_name = getattr(entity, "username", None) or str(entity.id)

                yield {
                    "message_id": msg.id,
                    "text": msg.message or "",
                    "date": msg.date.isoformat() if msg.date else "",
                    "sender_id": msg.sender_id,
                    "has_link": has_link,
                    "channel_name": channel_name,
                    "forward_from": forward_from,
                    "raw_message": msg,
                }

                fetched += 1
                if progress_callback and fetched % BATCH_SIZE == 0:
                    progress_callback(fetched, f"📨 Fetched {fetched:,} messages…")

        except FloodWaitError as e:
            # REC-03 — show countdown in progress_callback
            wait = e.seconds
            if progress_callback:
                for remaining in range(wait, 0, -1):
                    progress_callback(
                        fetched,
                        f"⚠️ Rate limited by Telegram. Resuming in {remaining}s…",
                    )
                    await asyncio.sleep(1)
            else:
                await asyncio.sleep(wait)
            # Resume by recursively continuing (Telethon handles offset internally)
            # The caller should re-invoke if more messages are needed.

        except (ConnectionError, OSError) as exc:
            for attempt in range(MAX_RETRIES):
                try:
                    await self.client.connect()
                    break
                except (ConnectionError, OSError):
                    if attempt < MAX_RETRIES - 1:
                        await asyncio.sleep(RETRY_DELAYS[attempt])
                    else:
                        raise exc

        # Final progress update
        if progress_callback:
            progress_callback(fetched, f"✅ Done — {fetched:,} messages fetched")
