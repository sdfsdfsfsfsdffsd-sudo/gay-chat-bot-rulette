from __future__ import annotations

import os
import unittest
from pathlib import Path
from unittest.mock import patch

from bot.config import effective_model_settings, load_settings, validate_setting_override


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

    def test_railway_volume_is_used_for_default_storage_paths(self) -> None:
        env = {
            "TELEGRAM_BOT_TOKEN": "token",
            "OPENROUTER_API_KEY": "key",
            "RAILWAY_VOLUME_MOUNT_PATH": "/app/data",
        }
        with patch.dict(os.environ, env, clear=True), patch("bot.config.load_dotenv"):
            settings = load_settings()

        self.assertEqual(settings.database_path, Path("/app/data/bot.sqlite3"))
        self.assertEqual(settings.local_image_dir, Path("/app/data/images"))

    def test_explicit_storage_paths_override_railway_volume(self) -> None:
        env = {
            "TELEGRAM_BOT_TOKEN": "token",
            "OPENROUTER_API_KEY": "key",
            "RAILWAY_VOLUME_MOUNT_PATH": "/app/data",
            "DATABASE_PATH": "/custom/db.sqlite3",
            "LOCAL_IMAGE_DIR": "/custom/images",
        }
        with patch.dict(os.environ, env, clear=True), patch("bot.config.load_dotenv"):
            settings = load_settings()

        self.assertEqual(settings.database_path, Path("/custom/db.sqlite3"))
        self.assertEqual(settings.local_image_dir, Path("/custom/images"))

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

    def test_joke_model_falls_back_to_uncensored_default_model(self) -> None:
        env = {
            "TELEGRAM_BOT_TOKEN": "token",
            "OPENROUTER_API_KEY": "key",
            "OPENROUTER_DEFAULT_MODEL": "cognitivecomputations/dolphin-mistral-24b-venice-edition",
            "JOKE_MODEL": "",
        }
        with patch.dict(os.environ, env, clear=True), patch("bot.config.load_dotenv"):
            settings = load_settings()

        self.assertEqual(
            settings.joke_model,
            "cognitivecomputations/dolphin-mistral-24b-venice-edition",
        )

    def test_schedule_and_context_settings_can_be_overridden(self) -> None:
        overrides = {
            "TELEGRAM_BOT_TOKEN": "token",
            "OPENROUTER_API_KEY": "key",
            "SUMMARY_EVERY_DAYS": "2",
            "JOKE_A_EVERY_DAYS": "3",
            "JOKE_B_EVERY_DAYS": "0.5",
            "JOKE_A_TIME": "12:30",
            "JOKE_B_TIME": "19:45",
            "CONSPIRACY_TIME": "21:15",
            "ALABUGA_EVERY_HOURS": "12",
            "SUMMARY_CONTEXT_HOURS": "36",
            "HOROSCOPE_CONTEXT_DAYS": "5",
            "CONSPIRACY_CONTEXT_DAYS": "4",
            "ANSWER_WEB_SEARCH_ENABLED": "false",
        }
        with patch.dict(os.environ, {}, clear=True), patch("bot.config.load_dotenv"):
            settings = load_settings(overrides)

        self.assertEqual(settings.summary_every_days, 2)
        self.assertEqual(settings.joke_a_every_days, 3)
        self.assertEqual(settings.joke_b_every_days, 0.5)
        self.assertEqual(settings.joke_a_time, "12:30")
        self.assertEqual(settings.joke_b_time, "19:45")
        self.assertEqual(settings.conspiracy_time, "21:15")
        self.assertEqual(settings.alabuga_every_hours, 12)
        self.assertEqual(settings.summary_context_hours, 36)
        self.assertEqual(settings.horoscope_context_days, 5)
        self.assertEqual(settings.conspiracy_context_days, 4)
        self.assertFalse(settings.answer_web_search_enabled)

    def test_fractional_day_schedule_is_supported(self) -> None:
        overrides = {
            "TELEGRAM_BOT_TOKEN": "token",
            "OPENROUTER_API_KEY": "key",
            "JOKE_EVERY_DAYS": "0.5",
        }
        with patch.dict(os.environ, {}, clear=True), patch("bot.config.load_dotenv"):
            settings = load_settings(overrides)

        self.assertEqual(settings.joke_every_days, 0.5)

    def test_invalid_persisted_numbers_do_not_prevent_startup(self) -> None:
        overrides = {
            "TELEGRAM_BOT_TOKEN": "token",
            "OPENROUTER_API_KEY": "key",
            "JOKE_EVERY_DAYS": "not-a-number",
            "JOKE_TEMPERATURE": "also-invalid",
            "JOKE_TOP_K": "0.5",
            "JOKE_TIME": "99:70",
        }
        with patch.dict(os.environ, {}, clear=True), patch("bot.config.load_dotenv"):
            settings = load_settings(overrides)

        self.assertEqual(settings.joke_every_days, 1.0)
        self.assertEqual(settings.joke_params.temperature, 1.0)
        self.assertIsNone(settings.joke_params.top_k)
        self.assertEqual(settings.joke_time, "18:00")

    def test_admin_setting_validation_accepts_half_day_and_rejects_bad_time(self) -> None:
        validate_setting_override("JOKE_EVERY_DAYS", "0.5")
        validate_setting_override("JOKE_A_EVERY_DAYS", "0.5")
        validate_setting_override("JOKE_B_TIME", "18:30")
        validate_setting_override("ANSWER_WEB_SEARCH_ENABLED", "true")
        with self.assertRaises(ValueError):
            validate_setting_override("JOKE_TIME", "25:00")
        with self.assertRaises(ValueError):
            validate_setting_override("ANSWER_WEB_SEARCH_ENABLED", "maybe")

    def test_conspiracy_defaults_favor_coherent_output(self) -> None:
        overrides = {
            "TELEGRAM_BOT_TOKEN": "token",
            "OPENROUTER_API_KEY": "key",
        }
        with patch.dict(os.environ, {}, clear=True), patch("bot.config.load_dotenv"):
            settings = load_settings(overrides)

        self.assertEqual(settings.conspiracy_params.temperature, 0.85)
        self.assertEqual(settings.conspiracy_params.top_p, 0.95)
        self.assertEqual(settings.conspiracy_params.presence_penalty, 0.0)
        self.assertEqual(settings.conspiracy_params.frequency_penalty, 0.05)

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
