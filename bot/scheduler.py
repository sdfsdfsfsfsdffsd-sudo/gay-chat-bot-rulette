from __future__ import annotations

import random
import logging
from datetime import datetime, timedelta

from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from zoneinfo import ZoneInfo

from bot.bully import render_bully_message
from bot.config import Settings
from bot.horoscope import split_horoscope_by_participant
from bot.jokes import fetch_random_joke, format_joke_html
from bot.llm import OpenRouterClient
from bot.prompt_loader import PromptSet
from bot.runtime_config import sync_runtime_config
from bot.sources import (
    fetch_latest_unsent_telegram_item,
)
from bot.storage import Storage
from bot.telegram_format import normalize_telegram_html
from bot.userbot import forward_post_with_userbot
from bot.word_stats import build_daily_word_stats


logger = logging.getLogger(__name__)


def _hour_min(value: str) -> tuple[int, int]:
    hour, minute = value.split(":", 1)
    return int(hour), int(minute)


def periodic_day_trigger(every_days: float, time_value: str, tz: ZoneInfo, *, now: datetime | None = None):
    if every_days <= 0:
        return None
    hour, minute = _hour_min(time_value)
    if every_days == 1:
        return CronTrigger(hour=hour, minute=minute, timezone=tz)

    current = now.astimezone(tz) if now else datetime.now(tz)
    first_run = current.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if first_run <= current:
        first_run += timedelta(days=1)
    return IntervalTrigger(days=every_days, start_date=first_run, timezone=tz)


def _enabled(settings: Settings, name: str) -> bool:
    return bool(getattr(settings, name, True))


async def _send_text(bot: Bot, chat_id: int | None, text: str, *, parse_mode: str | None = None) -> None:
    if chat_id is None:
        return
    try:
        await bot.send_message(chat_id, text[:4000], parse_mode=parse_mode)
    except Exception:
        await bot.send_message(chat_id, text[:4000])


async def _forward_or_send_feed_item(bot: Bot, settings: Settings, chat_id: int | None, item) -> None:
    if chat_id is None:
        return
    if item.channel_username and item.message_id:
        try:
            await bot.forward_message(chat_id, f"@{item.channel_username}", item.message_id)
            return
        except Exception as error:
            logger.warning("Could not forward Telegram post %s/%s: %s", item.channel_username, item.message_id, error)
        if await forward_post_with_userbot(settings, chat_id, item.channel_username, item.message_id):
            return
    await _send_text(bot, chat_id, f"Alabuga Polytech:\n\n{item.text}\n\n{item.url}")


def _participants_block(participants: list[str]) -> str:
    if not participants:
        return "Участники: список пуст, сделай общий формат без персональных тегов."
    return "Участники для тегирования:\n" + "\n".join(f"- {participant}" for participant in participants)


async def send_horoscope(bot: Bot, settings: Settings, storage: Storage, llm: OpenRouterClient, prompts: PromptSet) -> None:
    await sync_runtime_config(settings, prompts, storage)
    if settings.bot_chat_id is None:
        return
    context_hours = settings.horoscope_context_days * 24
    participants = await storage.recent_participants(settings.bot_chat_id, hours=context_hours)
    context = "\n".join(await storage.recent_messages(settings.bot_chat_id, hours=context_hours, limit=700))
    text = await llm.generate_with_params(
        f"{prompts.horoscope}\n\n{_participants_block(participants)}\n\nКонтекст чата за последнее время:\n{context}",
        system_prompt=prompts.horoscope_system,
        model=settings.horoscope_model,
        params=settings.horoscope_params,
        max_tokens=1400,
    )
    for message_text in split_horoscope_by_participant(text, participants):
        await _send_text(bot, settings.bot_chat_id, message_text, parse_mode="HTML")


async def send_summary(bot: Bot, settings: Settings, storage: Storage, llm: OpenRouterClient, prompts: PromptSet) -> None:
    await sync_runtime_config(settings, prompts, storage)
    if settings.bot_chat_id is None:
        return
    lines = await storage.recent_messages(settings.bot_chat_id, hours=settings.summary_context_hours)
    if not lines:
        await _send_text(bot, settings.bot_chat_id, "<b>SVOдка за день</b>\n\n🫥 Сегодня чат мастерски изображал тишину.", parse_mode="HTML")
        return
    participants = await storage.recent_participants(settings.bot_chat_id, hours=settings.summary_context_hours)
    prompt = f"{_participants_block(participants)}\n\nСообщения за день:\n" + "\n".join(lines[-500:])
    text = await llm.generate_with_params(
        f"{prompts.summary}\n\n{prompt}",
        system_prompt=prompts.summary_system,
        model=settings.summary_model,
        params=settings.summary_params,
        max_tokens=1600,
    )
    await _send_text(bot, settings.bot_chat_id, text, parse_mode="HTML")


async def send_joke(
    bot: Bot,
    settings: Settings,
    joke_type: str = "a",
) -> None:
    if settings.bot_chat_id is None:
        return
    joke = await fetch_random_joke(settings.joke_source_urls)
    if joke is None:
        await _send_text(bot, settings.bot_chat_id, "Не смог найти анекдот: источники не ответили или пустые.")
        return
    await _send_text(bot, settings.bot_chat_id, format_joke_html(joke), parse_mode="HTML")


async def maybe_send_bully(bot: Bot, settings: Settings, storage: Storage, prompts: PromptSet) -> None:
    await sync_runtime_config(settings, prompts, storage)
    target_username = settings.bully_target_username
    if settings.bot_chat_id is None or not target_username:
        return
    if random.random() > settings.bully_probability:
        return
    target = f"@{target_username}"
    text = render_bully_message(settings.bully_message_text, target)
    await _send_text(bot, settings.bot_chat_id, normalize_telegram_html(text), parse_mode="HTML")


async def send_conspiracy(bot: Bot, settings: Settings, storage: Storage, llm: OpenRouterClient, prompts: PromptSet) -> None:
    await sync_runtime_config(settings, prompts, storage)
    if settings.bot_chat_id is None:
        return
    context_hours = settings.conspiracy_context_days * 24
    lines = await storage.recent_messages(settings.bot_chat_id, hours=context_hours, limit=700)
    participants = await storage.recent_participants(settings.bot_chat_id, hours=context_hours)
    prompt = f"{_participants_block(participants)}\n\n{prompts.conspiracy}\n\nКонтекст:\n" + "\n".join(lines[-700:])
    text = await llm.generate_with_params(
        prompt,
        system_prompt=prompts.conspiracy_system,
        model=settings.conspiracy_model,
        params=settings.conspiracy_params,
        max_tokens=900,
    )
    await _send_text(bot, settings.bot_chat_id, text)


async def send_alabuga_news(bot: Bot, settings: Settings, storage: Storage) -> None:
    if settings.bot_chat_id is None:
        return
    item = await fetch_latest_unsent_telegram_item(settings.alabuga_channel_url, storage.was_sent)
    if not item:
        return
    await _forward_or_send_feed_item(bot, settings, settings.bot_chat_id, item)
    await storage.mark_sent(item.key)


async def send_word_stats(bot: Bot, settings: Settings, storage: Storage) -> None:
    if settings.bot_chat_id is None or not settings.tracked_words:
        return
    text = await build_daily_word_stats(storage, settings.bot_chat_id, settings.tracked_words)
    await _send_text(bot, settings.bot_chat_id, text)


def configure_scheduler(
    scheduler: AsyncIOScheduler,
    bot: Bot,
    settings: Settings,
    storage: Storage,
    llm: OpenRouterClient,
    prompts: PromptSet,
) -> None:
    scheduler.remove_all_jobs()
    tz = ZoneInfo(settings.timezone)
    word_stats_hour, word_stats_minute = _hour_min(settings.word_stats_time)

    day_jobs = (
        ("horoscope", "horoscope_enabled", send_horoscope, settings.horoscope_every_days, settings.horoscope_time, [bot, settings, storage, llm, prompts]),
        ("summary", "summary_enabled", send_summary, settings.summary_every_days, settings.daily_summary_time, [bot, settings, storage, llm, prompts]),
        ("joke_a", "joke_a_enabled", send_joke, settings.joke_a_every_days, settings.joke_a_time, [bot, settings, "a"]),
        ("joke_b", "joke_b_enabled", send_joke, settings.joke_b_every_days, settings.joke_b_time, [bot, settings, "b"]),
        ("conspiracy", "conspiracy_enabled", send_conspiracy, settings.conspiracy_every_days, settings.conspiracy_time, [bot, settings, storage, llm, prompts]),
    )
    for job_id, enabled_field, function, every_days, time_value, args in day_jobs:
        if not _enabled(settings, enabled_field):
            continue
        trigger = periodic_day_trigger(every_days, time_value, tz)
        if trigger is not None:
            scheduler.add_job(function, trigger, args=args, id=job_id)

    if _enabled(settings, "word_stats_enabled"):
        scheduler.add_job(send_word_stats, CronTrigger(hour=word_stats_hour, minute=word_stats_minute, timezone=tz), args=[bot, settings, storage], id="word_stats")
    if _enabled(settings, "auto_bully_enabled") and settings.bully_every_minutes > 0:
        scheduler.add_job(maybe_send_bully, IntervalTrigger(minutes=settings.bully_every_minutes, timezone=tz), args=[bot, settings, storage, prompts], id="bully")
    if _enabled(settings, "alabuga_enabled") and settings.alabuga_every_hours > 0:
        scheduler.add_job(send_alabuga_news, IntervalTrigger(hours=settings.alabuga_every_hours, timezone=tz), args=[bot, settings, storage], id="alabuga")


def build_scheduler(bot: Bot, settings: Settings, storage: Storage, llm: OpenRouterClient, prompts: PromptSet) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone=ZoneInfo(settings.timezone))
    configure_scheduler(scheduler, bot, settings, storage, llm, prompts)
    return scheduler
