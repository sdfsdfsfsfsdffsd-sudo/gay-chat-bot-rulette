from __future__ import annotations

import unittest
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from zoneinfo import ZoneInfo

from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from bot.handlers import build_roast_prompt
from bot.scheduler import configure_scheduler, periodic_day_trigger, send_joke


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
    async def test_roast_uses_configured_window_for_target_and_chat(self) -> None:
        calls: list[tuple[str, int]] = []

        class Storage:
            async def recent_messages_by_participant(self, chat_id, target, *, hours, limit):
                calls.append(("target", hours))
                return ["max: target message"]

            async def recent_messages(self, chat_id, *, hours, limit):
                calls.append(("chat", hours))
                return ["other: context"]

        prompt = await build_roast_prompt(
            Storage(),
            1,
            SimpleNamespace(roast="Roast {target}"),
            "@max",
            3,
        )

        self.assertEqual(calls, [("target", 72), ("chat", 72)])
        self.assertIn("max: target message", prompt)
        self.assertIn("other: context", prompt)

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
                SimpleNamespace(joke="prompt", joke_system="system"),
            )


if __name__ == "__main__":
    unittest.main()
