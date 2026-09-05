from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, patch

from bot.sources import FeedItem, FeedMedia, fetch_random_unsent_telegram_item, parse_telegram_feed_html, parse_tg_post_ref


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

    def test_feed_parser_recognizes_round_video(self) -> None:
        content = """
        <div class="tgme_widget_message roundvideo_media" data-post="alabugapolytech/3506">
          <video class="tgme_widget_message_roundvideo js-message_roundvideo"
                 src="https://cdn.example/round.mp4"></video>
        </div>
        """

        items = parse_telegram_feed_html(content, "https://t.me/s/alabugapolytech")

        self.assertEqual(items[0].media[0].kind, "video_note")

    def test_feed_parser_skips_blurred_video_preview(self) -> None:
        content = """
        <div class="tgme_widget_message" data-post="alabugapolytech/3507">
          <video class="tgme_widget_message_video blured js-message_video_blured"
                 src="https://cdn.example/preview.mp4"></video>
          <video class="tgme_widget_message_video js-message_video"
                 src="https://cdn.example/original.mp4"></video>
        </div>
        """

        items = parse_telegram_feed_html(content, "https://t.me/s/alabugapolytech")

        self.assertEqual(
            [(media.kind, media.url) for media in items[0].media],
            [("video", "https://cdn.example/original.mp4")],
        )

    def test_feed_parser_preserves_supported_telegram_formatting(self) -> None:
        content = """
        <div class="tgme_widget_message" data-post="alabugapolytech/3508">
          <div class="tgme_widget_message_text">
            <b>Title</b><br><i>Details</i> &amp; text
            <blockquote>Quoted</blockquote>
            <a href="https://example.test/?a=1&amp;b=2">Link</a>
          </div>
        </div>
        """

        item = parse_telegram_feed_html(content, "https://t.me/s/alabugapolytech")[0]

        self.assertIn("<b>Title</b>\n<i>Details</i> &amp; text", item.html_text)
        self.assertIn("<blockquote>Quoted</blockquote>", item.html_text)
        self.assertIn('<a href="https://example.test/?a=1&amp;b=2">Link</a>', item.html_text)


class TelegramSourceAsyncTests(unittest.IsolatedAsyncioTestCase):
    async def test_random_unsent_selection_gives_video_notes_ten_percent_more_weight(self) -> None:
        regular = FeedItem("regular", "", "", media=(FeedMedia("photo", "photo"),))
        circle = FeedItem("circle", "", "", media=(FeedMedia("video_note", "circle"),))
        already_sent = FeedItem("sent", "", "", media=(FeedMedia("video_note", "sent"),))
        was_sent = AsyncMock(side_effect=lambda key: key == "sent")

        with patch(
            "bot.sources.fetch_telegram_feed",
            new=AsyncMock(return_value=[regular, circle, already_sent]),
        ), patch("bot.sources.random.choices", return_value=[circle]) as choices:
            result = await fetch_random_unsent_telegram_item("https://t.me/s/channel", was_sent)

        self.assertIs(result, circle)
        self.assertEqual(choices.call_args.kwargs["weights"], [1.0, 1.1])


if __name__ == "__main__":
    unittest.main()
