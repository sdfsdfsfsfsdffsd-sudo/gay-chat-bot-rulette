from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from bot.storage import Storage


class StorageTests(unittest.IsolatedAsyncioTestCase):
    async def test_recent_participants_prefers_usernames_for_tags(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage = Storage(Path(temp_dir) / "bot.sqlite3")
            await storage.init()
            await storage.save_message(
                chat_id=1,
                user_id=10,
                username="max",
                full_name="Max",
                text="hello",
                created_at=datetime.now(),
            )
            await storage.save_message(
                chat_id=1,
                user_id=11,
                username=None,
                full_name="No Username",
                text="hi",
                created_at=datetime.now(),
            )

            participants = await storage.recent_participants(1)

        self.assertEqual(participants, ["@max", "No Username"])

    async def test_recent_messages_by_participant_filters_target(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage = Storage(Path(temp_dir) / "bot.sqlite3")
            await storage.init()
            await storage.save_message(
                chat_id=1,
                user_id=10,
                username="max",
                full_name="Max",
                text="target message",
                created_at=datetime.now(),
            )
            await storage.save_message(
                chat_id=1,
                user_id=11,
                username="other",
                full_name="Other",
                text="other message",
                created_at=datetime.now(),
            )

            messages = await storage.recent_messages_by_participant(1, "@max")

        self.assertEqual(messages, ["max: target message"])

    async def test_messages_before_excludes_current_question_and_keeps_order(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage = Storage(Path(temp_dir) / "bot.sqlite3")
            await storage.init()
            for index in range(1, 7):
                current_id = await storage.save_message(
                    chat_id=1,
                    user_id=index,
                    username=f"user{index}",
                    full_name=None,
                    text=f"message {index}",
                    created_at=datetime.now(),
                )

            messages = await storage.messages_before(1, current_id, limit=5)

        self.assertEqual(messages, [
            "user1: message 1",
            "user2: message 2",
            "user3: message 3",
            "user4: message 4",
            "user5: message 5",
        ])

    async def test_prompt_overrides_can_be_set_and_cleared(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage = Storage(Path(temp_dir) / "bot.sqlite3")
            await storage.init()

            await storage.set_prompt_override("SUMMARY_PROMPT_TEXT", "admin prompt")
            overrides = await storage.prompt_overrides()
            await storage.clear_prompt_override("SUMMARY_PROMPT_TEXT")
            cleared = await storage.prompt_overrides()

        self.assertEqual(overrides["SUMMARY_PROMPT_TEXT"], "admin prompt")
        self.assertNotIn("SUMMARY_PROMPT_TEXT", cleared)

    async def test_setting_overrides_can_be_set_and_cleared(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage = Storage(Path(temp_dir) / "bot.sqlite3")
            await storage.init()

            await storage.set_setting_override("ANSWER_TEMPERATURE", "1.05")
            overrides = await storage.settings_overrides()
            await storage.clear_setting_override("ANSWER_TEMPERATURE")
            cleared = await storage.settings_overrides()

        self.assertEqual(overrides["ANSWER_TEMPERATURE"], "1.05")
        self.assertNotIn("ANSWER_TEMPERATURE", cleared)

    async def test_last_sent_time_survives_storage_restart(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "bot.sqlite3"
            sent_at = datetime(2026, 8, 25, 18, 30, tzinfo=timezone.utc)
            storage = Storage(path)
            await storage.init()
            await storage.mark_sent("schedule:conspiracy", sent_at=sent_at)

            restored = Storage(path)
            await restored.init()

        self.assertEqual(storage.last_sent_at("schedule:conspiracy"), sent_at)
        self.assertEqual(restored.last_sent_at("schedule:conspiracy"), sent_at)


if __name__ == "__main__":
    unittest.main()
