from __future__ import annotations

from bot.config import Settings, apply_settings, load_settings
from bot.prompt_loader import PromptSet, apply_prompts, load_prompts
from bot.storage import Storage


async def sync_runtime_config(settings: Settings, prompts: PromptSet, storage: Storage) -> None:
    setting_overrides = await storage.settings_overrides()
    apply_settings(settings, load_settings(setting_overrides))
    prompt_overrides = await storage.prompt_overrides()
    apply_prompts(prompts, load_prompts(settings, prompt_overrides))
