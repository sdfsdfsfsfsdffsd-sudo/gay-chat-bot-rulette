from __future__ import annotations

import unittest

from bot.sources import parse_tg_post_ref


class TelegramSourceTests(unittest.TestCase):
    def test_parse_tg_post_ref_extracts_channel_and_message_id(self) -> None:
        self.assertEqual(
            parse_tg_post_ref("https://t.me/alabugapolytech/123"),
            ("alabugapolytech", 123),
        )

    def test_parse_tg_post_ref_ignores_web_preview_urls(self) -> None:
        self.assertIsNone(parse_tg_post_ref("https://t.me/s/alabugapolytech"))


if __name__ == "__main__":
    unittest.main()
