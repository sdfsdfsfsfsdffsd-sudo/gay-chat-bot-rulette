from __future__ import annotations

import unittest

from bot.telegram_format import normalize_telegram_html


class TelegramFormatTests(unittest.TestCase):
    def test_converts_markdown_bold_to_telegram_html(self) -> None:
        self.assertEqual(
            normalize_telegram_html("**Title**\nText"),
            "<b>Title</b>\nText",
        )

    def test_escapes_html_when_converting_markdown_bold(self) -> None:
        self.assertEqual(
            normalize_telegram_html("**A < B** & ok"),
            "<b>A &lt; B</b> &amp; ok",
        )

    def test_leaves_existing_html_without_markdown_unchanged(self) -> None:
        self.assertEqual(
            normalize_telegram_html("<b>Title</b>\nText"),
            "<b>Title</b>\nText",
        )


if __name__ == "__main__":
    unittest.main()
