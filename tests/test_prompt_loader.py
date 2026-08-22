from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from bot.prompt_loader import load_prompts


def settings_stub(**overrides):
    values = {
        "system_prompt_path": None,
        "answer_system_prompt_path": None,
        "horoscope_prompt_path": None,
        "joke_prompt_path": None,
        "summary_prompt_path": None,
        "conspiracy_prompt_path": None,
        "roast_prompt_path": None,
        "answer_prompt_path": None,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


class PromptLoaderTests(unittest.TestCase):
    def test_loads_answer_system_prompt_from_configured_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "answer_system.txt"
            path.write_text("custom answer system", encoding="utf-8")
            settings = settings_stub(answer_system_prompt_path=path)

            prompts = load_prompts(settings)

        self.assertEqual(prompts.answer_system, "custom answer system")

    def test_empty_prompt_file_overrides_default(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "answer.txt"
            path.write_text("", encoding="utf-8")
            settings = settings_stub(answer_prompt_path=path)

            prompts = load_prompts(settings)

        self.assertEqual(prompts.answer, "")

    def test_prompt_text_override_wins_over_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "answer.txt"
            path.write_text("file prompt", encoding="utf-8")
            settings = settings_stub(answer_prompt_path=path)

            prompts = load_prompts(settings, {"ANSWER_PROMPT_TEXT": "admin prompt"})

        self.assertEqual(prompts.answer, "admin prompt")


if __name__ == "__main__":
    unittest.main()
