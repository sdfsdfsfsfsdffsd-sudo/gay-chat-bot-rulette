from __future__ import annotations

import unittest

from bot.admin_panel import FIELDS, GROUPS, admin_field_text, admin_home_keyboard, display_value


class AdminPanelTests(unittest.TestCase):
    def test_has_setup_fields(self) -> None:
        self.assertIn("TELEGRAM_BOT_TOKEN", FIELDS)
        self.assertIn("OPENROUTER_API_KEY", FIELDS)
        self.assertIn("ANSWER_TEMPERATURE", FIELDS)
        self.assertIn("ROAST_PROBABILITY", FIELDS)
        self.assertIn("ANSWER_PROMPT_TEXT", FIELDS)
        self.assertIn("prompt_texts", GROUPS)

    def test_masks_secret_values(self) -> None:
        self.assertEqual(display_value("OPENROUTER_API_KEY", "sk-1234567890"), "sk-1...7890")

    def test_home_keyboard_has_buttons(self) -> None:
        keyboard = admin_home_keyboard()
        self.assertTrue(keyboard.inline_keyboard)

    def test_field_text_contains_key(self) -> None:
        self.assertIn("ANSWER_TEMPERATURE", admin_field_text("ANSWER_TEMPERATURE"))

    def test_prompt_text_field_uses_prompt_override_storage(self) -> None:
        text = admin_field_text("ANSWER_PROMPT_TEXT", {"ANSWER_PROMPT_TEXT": "admin prompt"})
        self.assertIn("admin prompt", text)
        self.assertIn("admin prompt storage", text)

    def test_setting_field_prefers_admin_setting_storage(self) -> None:
        text = admin_field_text("ANSWER_TEMPERATURE", setting_overrides={"ANSWER_TEMPERATURE": "1.05"})
        self.assertIn("1.05", text)
        self.assertIn("admin settings storage", text)


if __name__ == "__main__":
    unittest.main()
