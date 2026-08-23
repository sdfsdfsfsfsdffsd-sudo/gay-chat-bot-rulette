from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from bot.prompt_loader import load_prompts


def settings_stub(**overrides):
    values = {
        "system_prompt_path": None,
        "horoscope_prompt_path": None,
        "joke_prompt_path": None,
        "summary_prompt_path": None,
        "conspiracy_prompt_path": None,
        "roast_prompt_path": None,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


class PromptLoaderTests(unittest.TestCase):
    def test_answer_has_uncensored_system_prompt_by_default(self) -> None:
        prompts = load_prompts(settings_stub())

        self.assertIn("You are Uncensored", prompts.answer_system)

    def test_loads_system_prompt_from_configured_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "system.txt"
            path.write_text("custom system", encoding="utf-8")
            settings = settings_stub(system_prompt_path=path)

            prompts = load_prompts(settings)

        self.assertEqual(prompts.summary_system, "custom system")
        self.assertEqual(prompts.conspiracy_system, "")

    def test_conspiracy_has_no_system_prompt_by_default(self) -> None:
        prompts = load_prompts(settings_stub())

        self.assertEqual(prompts.conspiracy_system, "")

    def test_empty_prompt_file_overrides_default(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "summary.txt"
            path.write_text("", encoding="utf-8")
            settings = settings_stub(summary_prompt_path=path)

            prompts = load_prompts(settings)

        self.assertEqual(prompts.summary, "")

    def test_prompt_text_override_wins_over_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "summary.txt"
            path.write_text("file prompt", encoding="utf-8")
            settings = settings_stub(summary_prompt_path=path)

            prompts = load_prompts(settings, {"SUMMARY_PROMPT_TEXT": "admin prompt"})

        self.assertEqual(prompts.summary, "admin prompt")

    def test_service_system_prompts_are_independent(self) -> None:
        prompts = load_prompts(
            settings_stub(),
            {
                "ANSWER_SYSTEM_PROMPT_TEXT": "answer system",
                "CONSPIRACY_SYSTEM_PROMPT_TEXT": "conspiracy system",
            },
        )

        self.assertEqual(prompts.answer_system, "answer system")
        self.assertEqual(prompts.conspiracy_system, "conspiracy system")
        self.assertNotEqual(prompts.summary_system, "conspiracy system")


if __name__ == "__main__":
    unittest.main()
