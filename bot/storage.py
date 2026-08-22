from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import aiosqlite


class Storage:
    def __init__(self, path: Path) -> None:
        self.path = path

    async def init(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        async with aiosqlite.connect(self.path) as db:
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chat_id INTEGER NOT NULL,
                    user_id INTEGER,
                    username TEXT,
                    full_name TEXT,
                    text TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS sent_items (
                    key TEXT PRIMARY KEY,
                    sent_at TEXT NOT NULL
                )
                """
            )
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS admin_prompt_overrides (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS admin_settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            await db.commit()

    async def save_message(
        self,
        *,
        chat_id: int,
        user_id: int | None,
        username: str | None,
        full_name: str | None,
        text: str,
        created_at: datetime,
    ) -> None:
        async with aiosqlite.connect(self.path) as db:
            await db.execute(
                """
                INSERT INTO messages(chat_id, user_id, username, full_name, text, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (chat_id, user_id, username, full_name, text, created_at.isoformat()),
            )
            await db.commit()

    async def recent_messages(self, chat_id: int, *, hours: int = 24, limit: int = 500) -> list[str]:
        since = (datetime.now() - timedelta(hours=hours)).isoformat()
        async with aiosqlite.connect(self.path) as db:
            cursor = await db.execute(
                """
                SELECT COALESCE(username, full_name, 'user'), text
                FROM messages
                WHERE chat_id = ? AND created_at >= ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (chat_id, since, limit),
            )
            rows = await cursor.fetchall()
        return [f"{name}: {text}" for name, text in reversed(rows)]

    async def recent_message_rows(self, chat_id: int, *, hours: int = 24, limit: int = 5000) -> list[dict[str, str]]:
        since = (datetime.now() - timedelta(hours=hours)).isoformat()
        async with aiosqlite.connect(self.path) as db:
            cursor = await db.execute(
                """
                SELECT COALESCE(username, full_name, 'user') AS display_name, text
                FROM messages
                WHERE chat_id = ? AND created_at >= ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (chat_id, since, limit),
            )
            rows = await cursor.fetchall()
        return [{"display_name": name, "text": text} for name, text in reversed(rows)]

    async def recent_participants(self, chat_id: int, *, hours: int = 24, limit: int = 100) -> list[str]:
        since = (datetime.now() - timedelta(hours=hours)).isoformat()
        async with aiosqlite.connect(self.path) as db:
            cursor = await db.execute(
                """
                SELECT username, full_name, MAX(id) AS last_id
                FROM messages
                WHERE chat_id = ? AND created_at >= ?
                GROUP BY COALESCE(username, full_name, user_id)
                ORDER BY last_id DESC
                LIMIT ?
                """,
                (chat_id, since, limit),
            )
            rows = await cursor.fetchall()
        participants: list[str] = []
        for username, full_name, _ in rows:
            if username:
                participants.append(f"@{username}")
            elif full_name:
                participants.append(full_name)
        return list(reversed(participants))

    async def recent_messages_by_participant(
        self,
        chat_id: int,
        participant: str,
        *,
        hours: int = 168,
        limit: int = 80,
    ) -> list[str]:
        since = (datetime.now() - timedelta(hours=hours)).isoformat()
        normalized = participant.strip().lstrip("@").lower()
        async with aiosqlite.connect(self.path) as db:
            cursor = await db.execute(
                """
                SELECT COALESCE(username, full_name, 'user'), text
                FROM messages
                WHERE chat_id = ?
                  AND created_at >= ?
                  AND (
                    LOWER(COALESCE(username, '')) = ?
                    OR LOWER(COALESCE(full_name, '')) = ?
                    OR LOWER(COALESCE(username, full_name, 'user')) = ?
                  )
                ORDER BY id DESC
                LIMIT ?
                """,
                (chat_id, since, normalized, normalized, normalized, limit),
            )
            rows = await cursor.fetchall()
        return [f"{name}: {text}" for name, text in reversed(rows)]

    async def was_sent(self, key: str) -> bool:
        async with aiosqlite.connect(self.path) as db:
            cursor = await db.execute("SELECT 1 FROM sent_items WHERE key = ?", (key,))
            row = await cursor.fetchone()
        return row is not None

    async def mark_sent(self, key: str) -> None:
        async with aiosqlite.connect(self.path) as db:
            await db.execute(
                "INSERT OR REPLACE INTO sent_items(key, sent_at) VALUES (?, ?)",
                (key, datetime.now().isoformat()),
            )
            await db.commit()

    async def prompt_overrides(self) -> dict[str, str]:
        async with aiosqlite.connect(self.path) as db:
            cursor = await db.execute("SELECT key, value FROM admin_prompt_overrides")
            rows = await cursor.fetchall()
        return {key: value for key, value in rows}

    async def set_prompt_override(self, key: str, value: str) -> None:
        async with aiosqlite.connect(self.path) as db:
            await db.execute(
                """
                INSERT OR REPLACE INTO admin_prompt_overrides(key, value, updated_at)
                VALUES (?, ?, ?)
                """,
                (key, value, datetime.now().isoformat()),
            )
            await db.commit()

    async def clear_prompt_override(self, key: str) -> None:
        async with aiosqlite.connect(self.path) as db:
            await db.execute("DELETE FROM admin_prompt_overrides WHERE key = ?", (key,))
            await db.commit()

    async def settings_overrides(self) -> dict[str, str]:
        async with aiosqlite.connect(self.path) as db:
            cursor = await db.execute("SELECT key, value FROM admin_settings")
            rows = await cursor.fetchall()
        return {key: value for key, value in rows}

    async def set_setting_override(self, key: str, value: str) -> None:
        async with aiosqlite.connect(self.path) as db:
            await db.execute(
                """
                INSERT OR REPLACE INTO admin_settings(key, value, updated_at)
                VALUES (?, ?, ?)
                """,
                (key, value, datetime.now().isoformat()),
            )
            await db.commit()

    async def clear_setting_override(self, key: str) -> None:
        async with aiosqlite.connect(self.path) as db:
            await db.execute("DELETE FROM admin_settings WHERE key = ?", (key,))
            await db.commit()
