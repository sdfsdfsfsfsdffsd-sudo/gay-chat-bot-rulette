from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from bot.config import load_settings
from bot.prompt_loader import load_prompts
from bot.runtime_config import sync_runtime_config
from bot.scheduler import send_conspiracy
from bot.storage import Storage


class RuntimeConfigTests(unittest.IsolatedAsyncioTestCase):
    async def test_sqlite_model_and_system_prompt_replace_live_values(self) -> None:
        env = {
            "TELEGRAM_BOT_TOKEN": "token",
            "OPENROUTER_API_KEY": "key",
            "CONSPIRACY_MODEL": "old/model",
        }
        with tempfile.TemporaryDirectory() as temp_dir, patch.dict(os.environ, env, clear=True), patch(
            "bot.config.load_dotenv"
        ):
            settings = load_settings()
            prompts = load_prompts(settings)
            storage = Storage(Path(temp_dir) / "bot.sqlite3")
            await storage.init()
            await storage.set_setting_override("CONSPIRACY_MODEL", "new/model")
            await storage.set_prompt_override(
                "CONSPIRACY_SYSTEM_PROMPT_TEXT",
                "new conspiracy system prompt",
            )

            await sync_runtime_config(settings, prompts, storage)

        self.assertEqual(settings.conspiracy_model, "new/model")
        self.assertEqual(prompts.conspiracy_system, "new conspiracy system prompt")

    async def test_conspiracy_request_uses_latest_sqlite_model_and_system_prompt(self) -> None:
        env = {
            "TELEGRAM_BOT_TOKEN": "token",
            "OPENROUTER_API_KEY": "key",
            "BOT_CHAT_ID": "123",
            "CONSPIRACY_MODEL": "old/model",
        }

        class Llm:
            kwargs: dict | None = None

            async def generate_with_params(self, prompt, **kwargs):
                self.kwargs = kwargs
                return "result"

        class Bot:
            async def send_message(self, *args, **kwargs):
                return None

        with tempfile.TemporaryDirectory() as temp_dir, patch.dict(os.environ, env, clear=True), patch(
            "bot.config.load_dotenv"
        ):
            settings = load_settings()
            prompts = load_prompts(settings)
            storage = Storage(Path(temp_dir) / "bot.sqlite3")
            await storage.init()
            await storage.set_setting_override("CONSPIRACY_MODEL", "new/model")
            await storage.set_prompt_override(
                "CONSPIRACY_SYSTEM_PROMPT_TEXT",
                "new conspiracy system prompt",
            )
            llm = Llm()

            await send_conspiracy(Bot(), settings, storage, llm, prompts)

        assert llm.kwargs is not None
        self.assertEqual(llm.kwargs["model"], "new/model")
        self.assertEqual(llm.kwargs["system_prompt"], "new conspiracy system prompt")


if __name__ == "__main__":
    unittest.main()
