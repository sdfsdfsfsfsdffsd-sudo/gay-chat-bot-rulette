from __future__ import annotations

import unittest
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from zoneinfo import ZoneInfo

from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from bot.jokes import JokeItem
from bot.scheduler import (
    _forward_or_send_feed_item,
    configure_scheduler,
    maybe_send_bully,
    periodic_day_trigger,
    send_alabuga_news,
    send_joke,
)


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
        self.assertEqual(trigger.start_date, datetime(2026, 8, 25, 18, 0, tzinfo=timezone))

        restored = periodic_day_trigger(
            3,
            "18:00",
            timezone,
            now=now,
            last_run=datetime(2026, 8, 21, 18, 0, tzinfo=timezone),
        )
        self.assertEqual(restored.start_date, datetime(2026, 8, 24, 18, 0, tzinfo=timezone))

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

    def test_configure_scheduler_restores_conspiracy_cycle_from_last_send(self) -> None:
        timezone = ZoneInfo("Europe/Warsaw")
        last_sent = datetime.now(timezone).replace(hour=20, minute=0, second=0, microsecond=0)
        settings = SimpleNamespace(
            timezone="Europe/Warsaw",
            word_stats_time="23:35",
            horoscope_enabled=False,
            horoscope_every_days=1,
            horoscope_time="09:30",
            summary_enabled=False,
            summary_every_days=1,
            daily_summary_time="18:00",
            joke_a_enabled=False,
            joke_a_every_days=1,
            joke_a_time="12:00",
            joke_b_enabled=False,
            joke_b_every_days=1,
            joke_b_time="18:00",
            conspiracy_enabled=True,
            conspiracy_every_days=3,
            conspiracy_time="20:00",
            word_stats_enabled=False,
            auto_bully_enabled=False,
            bully_every_minutes=240,
            alabuga_enabled=False,
            alabuga_every_hours=4,
        )
        storage = SimpleNamespace(
            last_sent_at=lambda key: last_sent if key == "schedule:conspiracy" else None,
        )
        scheduler = RecordingScheduler()

        configure_scheduler(scheduler, object(), settings, storage, object(), object())

        conspiracy = next(job for job in scheduler.jobs if job["id"] == "conspiracy")
        self.assertEqual(conspiracy["trigger"].start_date, last_sent + timedelta(days=3))


class ContextAndJokeTests(unittest.IsolatedAsyncioTestCase):
    async def test_scheduled_joke_does_not_fetch_without_bound_chat(self) -> None:
        with patch("bot.scheduler.fetch_random_joke", new=AsyncMock()) as fetch:
            await send_joke(object(), SimpleNamespace(bot_chat_id=None), object())
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
        storage = SimpleNamespace(mark_sent=AsyncMock())
        with patch(
            "bot.scheduler.fetch_random_joke",
            new=AsyncMock(return_value=JokeItem("generated joke", "https://example.test/jokes")),
        ) as fetch:
            await send_joke(bot, settings, storage, "b")

        fetch.assert_awaited_once_with(["https://example.test/jokes"])
        storage.mark_sent.assert_awaited_once_with("schedule:joke_b")
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

    async def test_feed_forward_uses_text_fallback_when_bot_api_forward_fails(self) -> None:
        class Bot:
            async def forward_message(self, *args, **kwargs):
                raise RuntimeError("bot api cannot access source")

            async def send_message(self, chat_id, text, parse_mode=None, **kwargs):
                self.sent = (chat_id, text, parse_mode, kwargs)

        bot = Bot()
        item = SimpleNamespace(
            channel_username="alabugapolytech",
            message_id=123,
            text="post",
            url="https://t.me/alabugapolytech/123",
        )

        await _forward_or_send_feed_item(bot, SimpleNamespace(), -1001, item)

        self.assertEqual(bot.sent[0:3], (-1001, "post", "HTML"))
        self.assertTrue(bot.sent[3]["link_preview_options"].is_disabled)

    async def test_scheduled_alabuga_uses_weighted_random_unsent_selection(self) -> None:
        item = SimpleNamespace(key="tg:channel/7")
        storage = SimpleNamespace(was_sent=AsyncMock(), mark_sent=AsyncMock())
        settings = SimpleNamespace(bot_chat_id=-1001, alabuga_channel_url="https://t.me/s/channel")

        with patch(
            "bot.scheduler.fetch_random_unsent_telegram_item",
            new=AsyncMock(return_value=item),
        ) as fetch, patch("bot.scheduler._forward_or_send_feed_item", new=AsyncMock()) as deliver:
            await send_alabuga_news(object(), settings, storage)

        fetch.assert_awaited_once_with(
            settings.alabuga_channel_url,
            storage.was_sent,
            limit=30,
            video_note_weight=1.1,
        )
        deliver.assert_awaited_once()
        storage.mark_sent.assert_awaited_once_with(item.key)


if __name__ == "__main__":
    unittest.main()
