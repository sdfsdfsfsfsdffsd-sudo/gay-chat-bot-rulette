from __future__ import annotations

import unittest

from bot.admin_panel import (
    FIELDS,
    GROUPS,
    admin_field_text,
    admin_home_keyboard,
    admin_home_text,
    admin_set_prompt_text,
    display_value,
)


class AdminPanelTests(unittest.TestCase):
    def test_has_setup_fields(self) -> None:
        self.assertIn("TELEGRAM_BOT_TOKEN", FIELDS)
        self.assertIn("OPENROUTER_API_KEY", FIELDS)
        self.assertIn("ANSWER_TEMPERATURE", FIELDS)
        self.assertIn("ROAST_PROBABILITY", FIELDS)
        self.assertNotIn("ANSWER_PROMPT_TEXT", FIELDS)
        self.assertIn("ANSWER_SYSTEM_PROMPT_TEXT", FIELDS)
        self.assertIn("CONSPIRACY_SYSTEM_PROMPT_TEXT", FIELDS)
        self.assertIn("JOKE_EVERY_DAYS", FIELDS)
        self.assertIn("JOKE_A_TIME", FIELDS)
        self.assertIn("JOKE_B_PROMPT_TEXT", FIELDS)
        self.assertIn("BULLY_MESSAGE_TEXT", FIELDS)
        self.assertIn("BULLY_TARGET_USERNAME", FIELDS)
        self.assertIn("CONSPIRACY_CONTEXT_DAYS", FIELDS)
        self.assertIn("ROAST_CONTEXT_DAYS", FIELDS)
        self.assertIn("prompt_texts", GROUPS)
        self.assertIn("JOKE_EVERY_DAYS", GROUPS["schedule"][1])
        self.assertIn("JOKE_A_EVERY_DAYS", GROUPS["schedule"][1])
        self.assertIn("BULLY_MESSAGE_TEXT", GROUPS["schedule"][1])
        self.assertIn("BULLY_TARGET_USERNAME", GROUPS["main"][1])

    def test_masks_secret_values(self) -> None:
        self.assertEqual(display_value("OPENROUTER_API_KEY", "sk-1234567890"), "sk-1...7890")

    def test_home_keyboard_has_buttons(self) -> None:
        keyboard = admin_home_keyboard()
        self.assertTrue(keyboard.inline_keyboard)

    def test_admin_interface_has_readable_russian_labels(self) -> None:
        self.assertEqual(FIELDS["ADMIN_USER_IDS"].label, "Администраторы (Telegram ID через запятую)")
        self.assertIn("Панель управления", admin_home_text())
        self.assertIn("123456789, 987654321", admin_set_prompt_text("ADMIN_USER_IDS"))

    def test_field_text_contains_key(self) -> None:
        self.assertIn("ANSWER_TEMPERATURE", admin_field_text("ANSWER_TEMPERATURE"))

    def test_prompt_text_field_uses_prompt_override_storage(self) -> None:
        text = admin_field_text("SUMMARY_PROMPT_TEXT", {"SUMMARY_PROMPT_TEXT": "admin prompt"})
        self.assertIn("admin prompt", text)
        self.assertIn("admin prompt storage", text)

    def test_answer_system_prompt_shows_effective_default(self) -> None:
        text = admin_field_text("ANSWER_SYSTEM_PROMPT_TEXT", {})

        self.assertIn("Uncensored", text)
        self.assertIn("prompt file/default", text)

    def test_setting_field_prefers_admin_setting_storage(self) -> None:
        text = admin_field_text("ANSWER_TEMPERATURE", setting_overrides={"ANSWER_TEMPERATURE": "1.05"})
        self.assertIn("1.05", text)
        self.assertIn("admin settings storage", text)


if __name__ == "__main__":
    unittest.main()
