from __future__ import annotations

import unittest
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from zoneinfo import ZoneInfo

from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from bot.jokes import JokeItem
from bot.scheduler import _forward_or_send_feed_item, configure_scheduler, maybe_send_bully, periodic_day_trigger, send_joke


class RecordingScheduler:
    def __init__(self) -> None:
        self.jobs: list[dict] = []

    def remove_all_jobs(self) -> None:
        self.jobs.clear()

    def add_job(self, function, trigger, *, args, id) -> None:
        self.jobs.append({"function": function, "trigger": trigger, "args": args, "id": id})


class SchedulerTests(unittest.TestCase):
    def test_periodic_day_trigger_supports_daily_interval_and_disabled(self) -> None:
        timezone = ZoneInfo("Europe/Warsaw")
        now = datetime(2026, 8, 22, 19, 0, tzinfo=timezone)

        self.assertIsNone(periodic_day_trigger(0, "18:00", timezone, now=now))
        self.assertIsInstance(periodic_day_trigger(1, "18:00", timezone, now=now), CronTrigger)

        trigger = periodic_day_trigger(3, "18:00", timezone, now=now)
        self.assertIsInstance(trigger, IntervalTrigger)
        self.assertEqual(trigger.interval, timedelta(days=3))
        self.assertEqual(trigger.start_date, datetime(2026, 8, 23, 18, 0, tzinfo=timezone))

        half_day_trigger = periodic_day_trigger(0.5, "18:00", timezone, now=now)
        self.assertIsInstance(half_day_trigger, IntervalTrigger)
        self.assertEqual(half_day_trigger.interval, timedelta(hours=12))

    def test_configure_scheduler_omits_disabled_jobs(self) -> None:
        settings = SimpleNamespace(
            timezone="Europe/Warsaw",
            word_stats_time="23:35",
            horoscope_every_days=0,
            horoscope_time="09:30",
            summary_every_days=1,
            daily_summary_time="18:00",
            joke_a_every_days=0,
            joke_a_time="12:00",
            joke_b_every_days=0,
            joke_b_time="18:00",
            conspiracy_every_days=3,
            conspiracy_time="20:00",
            bully_every_minutes=0,
            alabuga_every_hours=0,
        )
        scheduler = RecordingScheduler()

        configure_scheduler(scheduler, object(), settings, object(), object(), object())

        self.assertEqual(
            {job["id"] for job in scheduler.jobs},
            {"summary", "conspiracy", "word_stats"},
        )

    def test_configure_scheduler_respects_enabled_flags_without_losing_intervals(self) -> None:
        settings = SimpleNamespace(
            timezone="Europe/Warsaw",
            word_stats_time="23:35",
            horoscope_enabled=False,
            horoscope_every_days=1,
            horoscope_time="09:30",
            summary_enabled=True,
            summary_every_days=1,
            daily_summary_time="18:00",
            joke_a_enabled=False,
            joke_a_every_days=1,
            joke_a_time="12:00",
            joke_b_enabled=True,
            joke_b_every_days=1,
            joke_b_time="18:00",
            conspiracy_enabled=False,
            conspiracy_every_days=3,
            conspiracy_time="20:00",
            word_stats_enabled=False,
            auto_bully_enabled=False,
            bully_every_minutes=240,
            alabuga_enabled=False,
            alabuga_every_hours=4,
        )
        scheduler = RecordingScheduler()

        configure_scheduler(scheduler, object(), settings, object(), object(), object())

        self.assertEqual({job["id"] for job in scheduler.jobs}, {"summary", "joke_b"})


class ContextAndJokeTests(unittest.IsolatedAsyncioTestCase):
    async def test_scheduled_joke_does_not_fetch_without_bound_chat(self) -> None:
        with patch("bot.scheduler.fetch_random_joke", new=AsyncMock()) as fetch:
            await send_joke(object(), SimpleNamespace(bot_chat_id=None))
        fetch.assert_not_awaited()

    async def test_scheduled_joke_fetches_from_sources_without_llm(self) -> None:
        class Bot:
            async def send_message(self, chat_id, text, parse_mode=None):
                self.sent = (chat_id, text, parse_mode)

        bot = Bot()
        settings = SimpleNamespace(
            bot_chat_id=123,
            joke_source_urls=["https://example.test/jokes"],
        )
        with patch(
            "bot.scheduler.fetch_random_joke",
            new=AsyncMock(return_value=JokeItem("generated joke", "https://example.test/jokes")),
        ) as fetch:
            await send_joke(bot, settings, "b")

        fetch.assert_awaited_once_with(["https://example.test/jokes"])
        self.assertEqual(bot.sent, (123, "generated joke", "HTML"))

    async def test_auto_bully_uses_static_message_without_llm(self) -> None:
        class Bot:
            async def send_message(self, chat_id, text, parse_mode=None):
                self.sent = (chat_id, text, parse_mode)

        bot = Bot()
        settings = SimpleNamespace(
            bot_chat_id=123,
            bully_target_username="max",
            bully_probability=1,
            bully_message_text="Static {target} / {username}",
        )

        with patch("bot.scheduler.sync_runtime_config", new=AsyncMock()), patch("bot.scheduler.random.random", return_value=0):
            await maybe_send_bully(bot, settings, object(), object())

        self.assertEqual(bot.sent, (123, "Static @max / max", "HTML"))

    async def test_auto_bully_uses_configured_target(self) -> None:
        class Bot:
            async def send_message(self, chat_id, text, parse_mode=None):
                self.sent = (chat_id, text, parse_mode)

        settings = SimpleNamespace(
            bot_chat_id=123,
            bully_target_username="configured",
            bully_probability=1,
            bully_message_text="{target}",
        )

        with patch("bot.scheduler.sync_runtime_config", new=AsyncMock()), patch("bot.scheduler.random.random", return_value=0):
            await maybe_send_bully(bot := Bot(), settings, object(), object())

        self.assertEqual(bot.sent, (123, "@configured", "HTML"))

    async def test_feed_forward_falls_back_to_userbot_after_bot_api_failure(self) -> None:
        class Bot:
            async def forward_message(self, *args, **kwargs):
                raise RuntimeError("bot api cannot access source")

            async def send_message(self, *args, **kwargs):
                raise AssertionError("Text fallback should not run when userbot succeeds")

        item = SimpleNamespace(
            channel_username="alabugapolytech",
            message_id=123,
            text="post",
            url="https://t.me/alabugapolytech/123",
        )

        with patch("bot.scheduler.forward_post_with_userbot", new=AsyncMock(return_value=True)) as userbot_forward:
            await _forward_or_send_feed_item(Bot(), SimpleNamespace(), -1001, item)

        userbot_forward.assert_awaited_once()

    async def test_feed_forward_uses_text_fallback_when_forwards_fail(self) -> None:
        class Bot:
            async def forward_message(self, *args, **kwargs):
                raise RuntimeError("bot api cannot access source")

            async def send_message(self, chat_id, text, parse_mode=None):
                self.sent = (chat_id, text, parse_mode)

        bot = Bot()
        item = SimpleNamespace(
            channel_username="alabugapolytech",
            message_id=123,
            text="post",
            url="https://t.me/alabugapolytech/123",
        )

        with patch("bot.scheduler.forward_post_with_userbot", new=AsyncMock(return_value=False)):
            await _forward_or_send_feed_item(bot, SimpleNamespace(), -1001, item)

        self.assertEqual(bot.sent, (-1001, "Alabuga Polytech:\n\npost\n\nhttps://t.me/alabugapolytech/123", None))


if __name__ == "__main__":
    unittest.main()
