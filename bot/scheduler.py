from __future__ import annotations

import random
from datetime import datetime, timedelta

from aiogram import Bot
from aiogram.types import FSInputFile
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from zoneinfo import ZoneInfo

from bot.config import Settings
from bot.llm import OpenRouterClient
from bot.prompt_loader import PromptSet
from bot.sources import (
    fetch_latest_unsent_telegram_item,
    random_channel_image_url,
    random_local_image,
)
from bot.storage import Storage
from bot.telegram_format import normalize_telegram_html
from bot.word_stats import build_daily_word_stats


def _hour_min(value: str) -> tuple[int, int]:
    hour, minute = value.split(":", 1)
    return int(hour), int(minute)


def periodic_day_trigger(every_days: int, time_value: str, tz: ZoneInfo, *, now: datetime | None = None):
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


async def _send_text(bot: Bot, chat_id: int | None, text: str, *, parse_mode: str | None = None) -> None:
    if chat_id is None:
        return
    try:
        await bot.send_message(chat_id, text[:4000], parse_mode=parse_mode)
    except Exception:
        await bot.send_message(chat_id, text[:4000])


def _participants_block(participants: list[str]) -> str:
    if not participants:
        return "Участники: список пуст, сделай общий формат без персональных тегов."
    return "Участники для тегирования:\n" + "\n".join(f"- {participant}" for participant in participants)


async def send_horoscope(bot: Bot, settings: Settings, storage: Storage, llm: OpenRouterClient, prompts: PromptSet) -> None:
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
    await _send_text(bot, settings.bot_chat_id, text, parse_mode="HTML")


async def send_summary(bot: Bot, settings: Settings, storage: Storage, llm: OpenRouterClient, prompts: PromptSet) -> None:
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


async def send_joke(bot: Bot, settings: Settings, llm: OpenRouterClient, prompts: PromptSet) -> None:
    if settings.bot_chat_id is None:
        return
    text = await llm.generate_with_params(
        prompts.joke,
        system_prompt=prompts.joke_system,
        model=settings.joke_model,
        params=settings.joke_params,
        max_tokens=500,
    )
    await _send_text(bot, settings.bot_chat_id, normalize_telegram_html(text), parse_mode="HTML")


async def maybe_send_random_image(bot: Bot, settings: Settings) -> None:
    if settings.bot_chat_id is None or random.random() > settings.random_image_probability:
        return
    local = random_local_image(settings.local_image_dir)
    if local and random.random() < 0.65:
        await bot.send_photo(settings.bot_chat_id, FSInputFile(local))
        return
    remote = await random_channel_image_url(settings.image_source_channels)
    if remote:
        await bot.send_photo(settings.bot_chat_id, remote)


async def maybe_send_roast(bot: Bot, settings: Settings, storage: Storage, llm: OpenRouterClient, prompts: PromptSet) -> None:
    if settings.bot_chat_id is None or not settings.target_username:
        return
    if random.random() > settings.roast_probability:
        return
    target = f"@{settings.target_username}"
    context_hours = settings.roast_context_days * 24
    target_messages = await storage.recent_messages_by_participant(settings.bot_chat_id, target, hours=context_hours, limit=80)
    general_context = await storage.recent_messages(settings.bot_chat_id, hours=context_hours, limit=120)
    target_block = "\n".join(target_messages) if target_messages else "Сообщений именно этого участника за период не найдено."
    general_block = "\n".join(general_context[-120:]) if general_context else "Общий контекст пуст."
    prompt = (
        prompts.roast.format(target=target, username=settings.target_username)
        + "\n\nЦель roast:\n"
        + target
        + "\n\nСообщения цели за последнее время:\n"
        + target_block
        + f"\n\nОбщий контекст чата за {settings.roast_context_days} дн.:\n"
        + general_block
    )
    text = await llm.generate_with_params(
        prompt,
        system_prompt=prompts.roast_system,
        model=settings.roast_model,
        params=settings.roast_params,
        max_tokens=550,
    )
    await _send_text(bot, settings.bot_chat_id, normalize_telegram_html(text), parse_mode="HTML")


async def send_conspiracy(bot: Bot, settings: Settings, storage: Storage, llm: OpenRouterClient, prompts: PromptSet) -> None:
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
    await _send_text(bot, settings.bot_chat_id, f"Алабуга Политех:\n\n{item.text}\n\n{item.url}")
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
        ("horoscope", send_horoscope, settings.horoscope_every_days, settings.horoscope_time, [bot, settings, storage, llm, prompts]),
        ("summary", send_summary, settings.summary_every_days, settings.daily_summary_time, [bot, settings, storage, llm, prompts]),
        ("joke", send_joke, settings.joke_every_days, settings.joke_time, [bot, settings, llm, prompts]),
        ("conspiracy", send_conspiracy, settings.conspiracy_every_days, settings.conspiracy_time, [bot, settings, storage, llm, prompts]),
    )
    for job_id, function, every_days, time_value, args in day_jobs:
        trigger = periodic_day_trigger(every_days, time_value, tz)
        if trigger is not None:
            scheduler.add_job(function, trigger, args=args, id=job_id)

    scheduler.add_job(send_word_stats, CronTrigger(hour=word_stats_hour, minute=word_stats_minute, timezone=tz), args=[bot, settings, storage], id="word_stats")
    if settings.random_image_every_minutes > 0:
        scheduler.add_job(maybe_send_random_image, IntervalTrigger(minutes=settings.random_image_every_minutes, timezone=tz), args=[bot, settings], id="random_image")
    if settings.roast_every_minutes > 0:
        scheduler.add_job(maybe_send_roast, IntervalTrigger(minutes=settings.roast_every_minutes, timezone=tz), args=[bot, settings, storage, llm, prompts], id="roast")
    if settings.alabuga_every_hours > 0:
        scheduler.add_job(send_alabuga_news, IntervalTrigger(hours=settings.alabuga_every_hours, timezone=tz), args=[bot, settings, storage], id="alabuga")


def build_scheduler(bot: Bot, settings: Settings, storage: Storage, llm: OpenRouterClient, prompts: PromptSet) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone=ZoneInfo(settings.timezone))
    configure_scheduler(scheduler, bot, settings, storage, llm, prompts)
    return scheduler
