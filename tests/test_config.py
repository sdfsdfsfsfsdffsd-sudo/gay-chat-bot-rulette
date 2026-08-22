from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from bot.config import effective_model_settings, load_settings


class ConfigTests(unittest.TestCase):
    def test_sqlite_overrides_win_over_environment(self) -> None:
        env = {
            "TELEGRAM_BOT_TOKEN": "env-token",
            "OPENROUTER_API_KEY": "env-key",
            "ANSWER_TEMPERATURE": "0.7",
        }
        overrides = {
            "TELEGRAM_BOT_TOKEN": "db-token",
            "OPENROUTER_API_KEY": "db-key",
            "ANSWER_TEMPERATURE": "1.05",
        }
        with patch.dict(os.environ, env, clear=True), patch("bot.config.load_dotenv"):
            settings = load_settings(overrides)

        self.assertEqual(settings.telegram_bot_token, "db-token")
        self.assertEqual(settings.openrouter_api_key, "db-key")
        self.assertEqual(settings.answer_params.temperature, 1.05)

    def test_bootstrap_load_can_skip_required_secrets(self) -> None:
        with patch.dict(os.environ, {}, clear=True), patch("bot.config.load_dotenv"):
            settings = load_settings(require_secrets=False)

        self.assertEqual(settings.telegram_bot_token, "")
        self.assertEqual(settings.openrouter_api_key, "")

    def test_horoscope_model_falls_back_to_summary_model(self) -> None:
        env = {
            "TELEGRAM_BOT_TOKEN": "token",
            "OPENROUTER_API_KEY": "key",
            "SUMMARY_MODEL": "deepseek/deepseek-chat",
            "HOROSCOPE_MODEL": "",
        }
        with patch.dict(os.environ, env, clear=True), patch("bot.config.load_dotenv"):
            settings = load_settings()

        self.assertEqual(settings.summary_model, "deepseek/deepseek-chat")
        self.assertEqual(settings.horoscope_model, "deepseek/deepseek-chat")

    def test_effective_model_settings_returns_admin_keys(self) -> None:
        env = {
            "TELEGRAM_BOT_TOKEN": "token",
            "OPENROUTER_API_KEY": "key",
            "SUMMARY_MODEL": "deepseek/deepseek-chat",
            "HOROSCOPE_MODEL": "",
        }
        with patch.dict(os.environ, env, clear=True), patch("bot.config.load_dotenv"):
            settings = load_settings()

        models = effective_model_settings(settings)

        self.assertEqual(models["SUMMARY_MODEL"], "deepseek/deepseek-chat")
        self.assertEqual(models["HOROSCOPE_MODEL"], "deepseek/deepseek-chat")


if __name__ == "__main__":
    unittest.main()
