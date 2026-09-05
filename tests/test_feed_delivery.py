from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, patch

from aiogram.types import BufferedInputFile
from bot.feed_delivery import forward_or_copy_feed_item
from bot.sources import FeedItem, FeedMedia


class FakeBot:
    def __init__(self, *, forward_fails: bool = True, media_fails: bool = False, url_media_fails: bool = False) -> None:
        self.forward_fails = forward_fails
        self.media_fails = media_fails
        self.url_media_fails = url_media_fails
        self.calls: list[tuple] = []

    async def forward_message(self, *args):
        self.calls.append(("forward", *args))
        if self.forward_fails:
            raise RuntimeError("source unavailable")

    async def send_photo(self, chat_id, photo, **kwargs):
        self.calls.append(("photo", chat_id, photo, kwargs))
        if self.media_fails or (self.url_media_fails and isinstance(photo, str)):
            raise RuntimeError("URL unavailable")

    async def send_video(self, chat_id, video, **kwargs):
        self.calls.append(("video", chat_id, video, kwargs))
        if self.media_fails or (self.url_media_fails and isinstance(video, str)):
            raise RuntimeError("URL unavailable")

    async def send_video_note(self, chat_id, video_note, **kwargs):
        self.calls.append(("video_note", chat_id, video_note, kwargs))
        if self.media_fails:
            raise RuntimeError("video note unavailable")

    async def send_media_group(self, chat_id, media):
        self.calls.append(("album", chat_id, media))
        if self.media_fails:
            raise RuntimeError("URL unavailable")

    async def send_message(self, chat_id, text, **kwargs):
        self.calls.append(("text", chat_id, text, kwargs))


class FeedDeliveryTests(unittest.IsolatedAsyncioTestCase):
    async def test_photo_url_is_sent_directly_without_local_file(self) -> None:
        bot = FakeBot()
        item = FeedItem(
            key="post",
            text="Caption",
            url="https://t.me/channel/1",
            channel_username="channel",
            message_id=1,
            media=(FeedMedia("photo", "https://cdn.example/photo.jpg"),),
        )

        result = await forward_or_copy_feed_item(bot, -1001, item)

        self.assertEqual(result, "media")
        self.assertEqual(bot.calls[1][0:3], ("photo", -1001, "https://cdn.example/photo.jpg"))
        self.assertEqual(bot.calls[1][3]["caption"], "Caption")
        self.assertEqual(bot.calls[1][3]["parse_mode"], "HTML")

    async def test_album_uses_remote_urls_and_caption_on_first_item(self) -> None:
        bot = FakeBot()
        item = FeedItem(
            key="album",
            text="Album",
            url="https://t.me/channel/2",
            media=(
                FeedMedia("photo", "https://cdn.example/one.jpg"),
                FeedMedia("video", "https://cdn.example/two.mp4"),
            ),
        )

        result = await forward_or_copy_feed_item(bot, -1001, item)

        self.assertEqual(result, "media")
        album = bot.calls[0][2]
        self.assertEqual(album[0].media, "https://cdn.example/one.jpg")
        self.assertEqual(album[0].caption, "Album")
        self.assertEqual(album[0].parse_mode, "HTML")
        self.assertEqual(album[1].media, "https://cdn.example/two.mp4")
        self.assertIsNone(album[1].caption)

    async def test_media_error_falls_back_to_text(self) -> None:
        bot = FakeBot(media_fails=True)
        item = FeedItem(
            key="post",
            text="Text",
            url="https://t.me/channel/3",
            media=(FeedMedia("photo", "https://cdn.example/photo.jpg"),),
        )

        with patch(
            "bot.feed_delivery._download_media_assets",
            new=AsyncMock(side_effect=RuntimeError("download unavailable")),
        ):
            result = await forward_or_copy_feed_item(bot, -1001, item)

        self.assertEqual(result, "text")
        self.assertEqual(bot.calls[-1][0:3], ("text", -1001, "Text"))
        self.assertTrue(bot.calls[-1][3]["link_preview_options"].is_disabled)

    async def test_failed_remote_url_retries_with_in_memory_upload(self) -> None:
        bot = FakeBot(url_media_fails=True)
        item = FeedItem(
            key="post",
            text="Text",
            url="https://t.me/channel/4",
            media=(FeedMedia("photo", "https://cdn.example/photo.jpg"),),
        )
        buffered = BufferedInputFile(b"photo bytes", "photo.jpg")

        with patch(
            "bot.feed_delivery._download_media_assets",
            new=AsyncMock(return_value=[buffered]),
        ):
            result = await forward_or_copy_feed_item(bot, -1001, item)

        self.assertEqual(result, "media")
        self.assertIs(bot.calls[-1][2], buffered)

    async def test_round_video_is_uploaded_from_memory_as_video_note(self) -> None:
        bot = FakeBot()
        item = FeedItem(
            key="round",
            text="",
            url="https://t.me/channel/5",
            media=(FeedMedia("video_note", "https://cdn.example/round.mp4"),),
        )
        buffered = BufferedInputFile(b"round video bytes", "round.mp4")

        with patch(
            "bot.feed_delivery._download_media_assets",
            new=AsyncMock(return_value=[buffered]),
        ):
            result = await forward_or_copy_feed_item(bot, -1001, item)

        self.assertEqual(result, "media")
        self.assertEqual(bot.calls[0][0], "video_note")
        self.assertIs(bot.calls[0][2], buffered)
        self.assertEqual(len(bot.calls), 1)

    async def test_original_html_is_used_for_media_caption(self) -> None:
        bot = FakeBot()
        item = FeedItem(
            key="formatted",
            text="Title\nDetails",
            html_text="<b>Title</b>\n<i>Details</i>",
            url="https://t.me/channel/6",
            media=(FeedMedia("photo", "https://cdn.example/photo.jpg"),),
        )

        result = await forward_or_copy_feed_item(bot, -1001, item)

        self.assertEqual(result, "media")
        self.assertEqual(bot.calls[0][3]["caption"], "<b>Title</b>\n<i>Details</i>")


if __name__ == "__main__":
    unittest.main()
