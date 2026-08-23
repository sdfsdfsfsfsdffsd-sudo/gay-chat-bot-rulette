from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher

from bot.config import apply_settings, effective_model_settings, load_settings
from bot.handlers import build_router
from bot.llm import OpenRouterClient
from bot.prompt_loader import load_prompts
from bot.prompts import ANSWER_SYSTEM_PROMPT
from bot.scheduler import build_scheduler, configure_scheduler
from bot.storage import Storage

SETTINGS_SCHEMA_VERSION_KEY = "__SETTINGS_SCHEMA_VERSION"
LEGACY_JOKE_MODEL = "openai/gpt-4.1-nano"


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    settings = load_settings(require_secrets=False)
    storage = Storage(settings.database_path)
    await storage.init()
    setting_overrides = await storage.settings_overrides()
    await migrate_runtime_settings(storage, settings, setting_overrides)
    setting_overrides = await storage.settings_overrides()
    apply_settings(settings, load_settings(setting_overrides))
    await seed_missing_model_settings(storage, settings, setting_overrides)
    apply_settings(settings, load_settings(await storage.settings_overrides()))
    prompts = load_prompts(settings, await storage.prompt_overrides())

    bot = Bot(settings.telegram_bot_token)
    llm = OpenRouterClient(settings)
    dispatcher = Dispatcher()
    scheduler = build_scheduler(bot, settings, storage, llm, prompts)

    def reload_scheduler() -> None:
        configure_scheduler(scheduler, bot, settings, storage, llm, prompts)

    dispatcher.include_router(
        build_router(
            settings,
            storage,
            llm,
            prompts,
            reload_scheduler=reload_scheduler,
        )
    )

    scheduler.start()
    logging.info("Bot started. Bound chat: %s", settings.bot_chat_id)
    try:
        await dispatcher.start_polling(bot)
    finally:
        scheduler.shutdown(wait=False)
        await llm.close()
        await bot.session.close()


def run() -> None:
    asyncio.run(main())


async def seed_missing_model_settings(storage: Storage, settings, setting_overrides: dict[str, str]) -> None:
    for key, value in effective_model_settings(settings).items():
        if key not in setting_overrides:
            await storage.set_setting_override(key, value)


async def migrate_runtime_settings(storage: Storage, bootstrap_settings, setting_overrides: dict[str, str]) -> None:
    try:
        schema_version = int(setting_overrides.get(SETTINGS_SCHEMA_VERSION_KEY, "0"))
    except ValueError:
        schema_version = 0

    if schema_version < 1:
        if (
            setting_overrides.get("JOKE_MODEL") == LEGACY_JOKE_MODEL
            and bootstrap_settings.joke_model != LEGACY_JOKE_MODEL
        ):
            await storage.set_setting_override("JOKE_MODEL", bootstrap_settings.joke_model)
    if schema_version < 2:
        prompt_overrides = await storage.prompt_overrides()
        conspiracy_system = prompt_overrides.get("CONSPIRACY_SYSTEM_PROMPT_TEXT", "").strip()
        if conspiracy_system == ANSWER_SYSTEM_PROMPT.strip():
            await storage.clear_prompt_override("CONSPIRACY_SYSTEM_PROMPT_TEXT")

    if schema_version < 2:
        await storage.set_setting_override(SETTINGS_SCHEMA_VERSION_KEY, "2")
