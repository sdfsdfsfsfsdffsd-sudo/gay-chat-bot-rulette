from __future__ import annotations

import unittest
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from zoneinfo import ZoneInfo

from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from bot.scheduler import _forward_or_send_feed_item, configure_scheduler, maybe_send_roast, periodic_day_trigger, send_joke


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
            joke_every_days=0,
            joke_time="19:00",
            joke_a_every_days=0,
            joke_a_time="12:00",
            joke_b_every_days=0,
            joke_b_time="18:00",
            conspiracy_every_days=3,
            conspiracy_time="20:00",
            random_image_every_minutes=0,
            roast_every_minutes=0,
            alabuga_every_hours=0,
        )
        scheduler = RecordingScheduler()

        configure_scheduler(scheduler, object(), settings, object(), object(), object())

        self.assertEqual(
            {job["id"] for job in scheduler.jobs},
            {"summary", "conspiracy", "word_stats"},
        )


class ContextAndJokeTests(unittest.IsolatedAsyncioTestCase):
    async def test_scheduled_joke_does_not_call_llm_without_bound_chat(self) -> None:
        class Llm:
            async def generate_with_params(self, *args, **kwargs):
                raise AssertionError("LLM must not be called without BOT_CHAT_ID")

        with patch("bot.scheduler.sync_runtime_config", new=AsyncMock()):
            await send_joke(
                object(),
                SimpleNamespace(bot_chat_id=None),
                object(),
                Llm(),
                SimpleNamespace(joke="prompt", joke_a="prompt a", joke_b="prompt b", joke_system="system"),
            )

    async def test_scheduled_joke_type_b_uses_b_prompt(self) -> None:
        class Bot:
            async def send_message(self, chat_id, text, parse_mode=None):
                self.sent = (chat_id, text, parse_mode)

        class Llm:
            async def generate_with_params(self, prompt, **kwargs):
                self.prompt = prompt
                return "generated joke"

        bot = Bot()
        llm = Llm()
        settings = SimpleNamespace(
            bot_chat_id=123,
            joke_model="model",
            joke_params=SimpleNamespace(),
        )
        prompts = SimpleNamespace(joke_a="prompt a", joke_b="prompt b", joke_system="")

        with patch("bot.scheduler.sync_runtime_config", new=AsyncMock()):
            await send_joke(bot, settings, object(), llm, prompts, "b")

        self.assertEqual(llm.prompt, "prompt b")
        self.assertEqual(bot.sent, (123, "generated joke", "HTML"))

    async def test_auto_roast_uses_static_bully_message_without_llm(self) -> None:
        class Bot:
            async def send_message(self, chat_id, text, parse_mode=None):
                self.sent = (chat_id, text, parse_mode)

        class Llm:
            async def generate_with_params(self, *args, **kwargs):
                raise AssertionError("Bully must not call LLM")

        bot = Bot()
        settings = SimpleNamespace(
            bot_chat_id=123,
            bully_target_username=None,
            target_username="max",
            roast_probability=1,
            bully_message_text="Static {target} / {username}",
        )

        with patch("bot.scheduler.sync_runtime_config", new=AsyncMock()), patch("bot.scheduler.random.random", return_value=0):
            await maybe_send_roast(bot, settings, object(), Llm(), object())

        self.assertEqual(bot.sent, (123, "Static @max / max", "HTML"))

    async def test_auto_roast_prefers_configured_bully_target(self) -> None:
        class Bot:
            async def send_message(self, chat_id, text, parse_mode=None):
                self.sent = (chat_id, text, parse_mode)

        settings = SimpleNamespace(
            bot_chat_id=123,
            bully_target_username="configured",
            target_username="legacy",
            roast_probability=1,
            bully_message_text="{target}",
        )

        with patch("bot.scheduler.sync_runtime_config", new=AsyncMock()), patch("bot.scheduler.random.random", return_value=0):
            await maybe_send_roast(bot := Bot(), settings, object(), object(), object())

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
