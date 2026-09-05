from __future__ import annotations

import unittest

from bot.sources import parse_telegram_feed_html, parse_tg_post_ref


class TelegramSourceTests(unittest.TestCase):
    def test_parse_tg_post_ref_extracts_channel_and_message_id(self) -> None:
        self.assertEqual(
            parse_tg_post_ref("https://t.me/alabugapolytech/123"),
            ("alabugapolytech", 123),
        )

    def test_parse_tg_post_ref_extracts_data_post_value(self) -> None:
        self.assertEqual(parse_tg_post_ref("alabugapolytech/123"), ("alabugapolytech", 123))

    def test_parse_tg_post_ref_ignores_web_preview_urls(self) -> None:
        self.assertIsNone(parse_tg_post_ref("https://t.me/s/alabugapolytech"))

    def test_feed_parser_extracts_direct_post_link_and_media_without_downloading(self) -> None:
        content = """
        <div class="tgme_widget_message" data-post="alabugapolytech/3500">
          <div class="tgme_widget_message_text">Post text</div>
          <a class="tgme_widget_message_photo_wrap"
             style="background-image:url('https://cdn.example/photo.jpg?x=1&amp;y=2')"></a>
          <video src="https://cdn.example/video.mp4?token=abc"></video>
        </div>
        """

        items = parse_telegram_feed_html(content, "https://t.me/s/alabugapolytech")

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].url, "https://t.me/alabugapolytech/3500")
        self.assertEqual(
            [(media.kind, media.url) for media in items[0].media],
            [
                ("photo", "https://cdn.example/photo.jpg?x=1&y=2"),
                ("video", "https://cdn.example/video.mp4?token=abc"),
            ],
        )

    def test_feed_parser_keeps_media_only_posts(self) -> None:
        content = """
        <div class="tgme_widget_message" data-post="alabugapolytech/3501">
          <video src="https://cdn.example/video.mp4"></video>
        </div>
        """

        items = parse_telegram_feed_html(content, "https://t.me/s/alabugapolytech")

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].text, "")
        self.assertEqual(items[0].media[0].kind, "video")


if __name__ == "__main__":
    unittest.main()
