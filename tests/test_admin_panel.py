from __future__ import annotations

import unittest
from types import SimpleNamespace

from bot.admin_panel import (
    FIELDS,
    GROUPS,
    HOME_GROUPS,
    admin_cancel_keyboard,
    admin_clear_keyboard,
    admin_field_keyboard,
    admin_field_text,
    admin_group_keyboard,
    admin_home_keyboard,
    admin_home_text,
    admin_set_prompt_text,
    display_value,
)


def settings_stub(**overrides):
    values = {
        "has_bound_chat": True,
        "summary_enabled": True,
        "horoscope_enabled": True,
        "word_stats_enabled": True,
        "joke_a_enabled": True,
        "joke_b_enabled": False,
        "conspiracy_enabled": True,
        "auto_bully_enabled": False,
        "alabuga_enabled": True,
        "answer_web_search_enabled": True,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


class AdminPanelTests(unittest.TestCase):
    def test_home_contains_only_task_oriented_sections(self) -> None:
        self.assertEqual(HOME_GROUPS, ("automations", "features", "integrations", "access", "advanced"))
        buttons = [button.text for row in admin_home_keyboard(settings_stub()).inline_keyboard for button in row]
        self.assertIn("📅 Автопубликации", buttons)
        self.assertIn("🧩 Функции", buttons)
        self.assertNotIn("📁 Файлы промптов", buttons)

    def test_legacy_and_image_fields_are_not_exposed(self) -> None:
        for key in (
            "TARGET_USERNAME", "ROAST_PROBABILITY", "RANDOM_IMAGE_ENABLED",
            "IMAGE_SOURCE_CHANNELS", "LOCAL_IMAGE_DIR", "JOKE_MODEL", "JOKE_PROMPT_PATH",
        ):
            self.assertNotIn(key, FIELDS)
        self.assertIn("BULLY_PROBABILITY", FIELDS)
        self.assertIn("BULLY_TARGET_USERNAME", FIELDS)

    def test_features_have_clear_nested_navigation(self) -> None:
        buttons = [button.text for row in admin_group_keyboard("features", settings_stub()).inline_keyboard for button in row]
        self.assertIn("📝 Сводка", buttons)
        self.assertIn("🎯 Буллинг", buttons)
        self.assertIn("← Назад", buttons)
        self.assertIn("⌂ Главная", buttons)

    def test_automation_dashboard_shows_live_state(self) -> None:
        keyboard = admin_group_keyboard("automations", settings_stub())
        buttons = [button.text for row in keyboard.inline_keyboard for button in row]
        self.assertTrue(any(button.startswith("✅ Сводка · ежедневно 23:30") for button in buttons))
        self.assertTrue(any(button.startswith("⛔ Анекдот B · ежедневно 18:00") for button in buttons))
        self.assertTrue(any(button.startswith("⛔ Автоматический буллинг · каждые 240 мин.") for button in buttons))

    def test_boolean_field_button_names_resulting_action(self) -> None:
        enabled = [button.text for row in admin_field_keyboard("ALABUGA_ENABLED", "alabuga", settings_stub()).inline_keyboard for button in row]
        disabled = [button.text for row in admin_field_keyboard("ALABUGA_ENABLED", "alabuga", settings_stub(alabuga_enabled=False)).inline_keyboard for button in row]
        self.assertIn("⏯ Выключить", enabled)
        self.assertIn("⏯ Включить", disabled)

    def test_database_path_is_read_only(self) -> None:
        buttons = [button.text for row in admin_field_keyboard("DATABASE_PATH", "advanced", settings_stub()).inline_keyboard for button in row]
        self.assertNotIn("✏️ Изменить", buttons)

    def test_callback_data_stays_within_telegram_limit(self) -> None:
        keyboards = [admin_home_keyboard(settings_stub())]
        keyboards.extend(admin_group_keyboard(key, settings_stub()) for key in GROUPS)
        for key in FIELDS:
            keyboards.append(admin_field_keyboard(key, settings=settings_stub()))
            group = "conspiracy_generation" if key.startswith("CONSPIRACY_") else "advanced"
            keyboards.append(admin_clear_keyboard(key, group))
            keyboards.append(admin_cancel_keyboard(key, group))
        for keyboard in keyboards:
            for row in keyboard.inline_keyboard:
                for button in row:
                    if button.callback_data:
                        self.assertLessEqual(len(button.callback_data.encode("utf-8")), 64, button.callback_data)

    def test_home_text_summarizes_state(self) -> None:
        text = admin_home_text(settings_stub())
        self.assertIn("Чат: <b>подключён</b>", text)
        self.assertIn("6 из 8", text)

    def test_masks_secret_values(self) -> None:
        self.assertEqual(display_value("OPENROUTER_API_KEY", "sk-1234567890"), "sk-1...7890")

    def test_prompt_and_setting_sources_are_readable(self) -> None:
        prompt_text = admin_field_text("SUMMARY_PROMPT_TEXT", {"SUMMARY_PROMPT_TEXT": "admin prompt"})
        setting_text = admin_field_text("ANSWER_TEMPERATURE", setting_overrides={"ANSWER_TEMPERATURE": "1.05"})
        self.assertIn("задано через админку", prompt_text)
        self.assertIn("задано через админку", setting_text)

    def test_edit_prompt_has_contextual_hint(self) -> None:
        self.assertIn("123456789, 987654321", admin_set_prompt_text("ADMIN_USER_IDS"))
        self.assertIn("{target}", admin_set_prompt_text("BULLY_MESSAGE_TEXT"))


if __name__ == "__main__":
    unittest.main()
