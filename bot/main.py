from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher

from bot.config import apply_settings, effective_model_settings, load_settings
from bot.commands import register_bot_commands
from bot.handlers import build_router
from bot.llm import OpenRouterClient
from bot.prompt_loader import load_prompts
from bot.prompts import ANSWER_SYSTEM_PROMPT
from bot.scheduler import build_scheduler, configure_scheduler
from bot.storage import Storage

SETTINGS_SCHEMA_VERSION_KEY = "__SETTINGS_SCHEMA_VERSION"


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
    await register_bot_commands(bot, settings)
    llm = OpenRouterClient(settings)
    dispatcher = Dispatcher()
    scheduler = build_scheduler(bot, settings, storage, llm, prompts)

    def reload_scheduler() -> None:
        configure_scheduler(scheduler, bot, settings, storage, llm, prompts)

    async def reload_command_menu() -> None:
        await register_bot_commands(bot, settings)

    dispatcher.include_router(
        build_router(
            settings,
            storage,
            llm,
            prompts,
            reload_scheduler=reload_scheduler,
            reload_command_menu=reload_command_menu,
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


async def migrate_runtime_settings(storage: Storage, _bootstrap_settings, setting_overrides: dict[str, str]) -> None:
    try:
        schema_version = int(setting_overrides.get(SETTINGS_SCHEMA_VERSION_KEY, "0"))
    except ValueError:
        schema_version = 0

    if schema_version < 2:
        prompt_overrides = await storage.prompt_overrides()
        conspiracy_system = prompt_overrides.get("CONSPIRACY_SYSTEM_PROMPT_TEXT", "").strip()
        if conspiracy_system == ANSWER_SYSTEM_PROMPT.strip():
            await storage.clear_prompt_override("CONSPIRACY_SYSTEM_PROMPT_TEXT")

    if schema_version < 3:
        legacy_mappings = {
            "TARGET_USERNAME": "BULLY_TARGET_USERNAME",
            "ROAST_EVERY_MINUTES": "BULLY_EVERY_MINUTES",
            "ROAST_PROBABILITY": "BULLY_PROBABILITY",
        }
        for old_key, new_key in legacy_mappings.items():
            if new_key not in setting_overrides and setting_overrides.get(old_key, "").strip():
                await storage.set_setting_override(new_key, setting_overrides[old_key])
            await storage.clear_setting_override(old_key)
        for obsolete_key in (
            "RANDOM_IMAGE_ENABLED",
            "RANDOM_IMAGE_EVERY_MINUTES",
            "RANDOM_IMAGE_PROBABILITY",
            "IMAGE_SOURCE_CHANNELS",
            "LOCAL_IMAGE_DIR",
            "ALABUGA_JOBS_URL",
            "JOKE_MODEL",
            "JOKE_TIME",
            "JOKE_EVERY_DAYS",
            "JOKE_TEMPERATURE",
            "JOKE_TOP_P",
            "JOKE_TOP_K",
            "JOKE_PRESENCE_PENALTY",
            "JOKE_FREQUENCY_PENALTY",
            "JOKE_REPETITION_PENALTY",
            "JOKE_MIN_P",
            "JOKE_TOP_A",
            "JOKE_MAX_TOKENS",
            "JOKE_PROMPT_PATH",
            "JOKE_A_PROMPT_PATH",
            "JOKE_B_PROMPT_PATH",
        ):
            await storage.clear_setting_override(obsolete_key)
        for obsolete_prompt in (
            "JOKE_SYSTEM_PROMPT_TEXT",
            "JOKE_PROMPT_TEXT",
            "JOKE_A_PROMPT_TEXT",
            "JOKE_B_PROMPT_TEXT",
        ):
            await storage.clear_prompt_override(obsolete_prompt)
        await storage.set_setting_override(SETTINGS_SCHEMA_VERSION_KEY, "3")
