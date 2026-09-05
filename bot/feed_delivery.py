from __future__ import annotations

import logging
from pathlib import PurePosixPath
from urllib.parse import urlparse

import httpx
from aiogram import Bot
from aiogram.types import BufferedInputFile, InputMediaPhoto, InputMediaVideo

from bot.sources import FeedItem


logger = logging.getLogger(__name__)
MAX_SINGLE_MEDIA_BYTES = 20 * 1024 * 1024
MAX_TOTAL_MEDIA_BYTES = 80 * 1024 * 1024


def feed_text(item: FeedItem) -> str:
    parts = [part for part in (item.text.strip(), item.url.strip()) if part]
    return "\n\n".join(parts)


def _media_filename(url: str, kind: str, index: int) -> str:
    suffix = PurePosixPath(urlparse(url).path).suffix
    if not suffix:
        suffix = ".mp4" if kind == "video" else ".jpg"
    return f"telegram_media_{index}{suffix}"


async def _download_media_assets(media) -> list[BufferedInputFile]:
    files: list[BufferedInputFile] = []
    total_size = 0
    headers = {"User-Agent": "Mozilla/5.0", "Referer": "https://t.me/"}
    async with httpx.AsyncClient(timeout=60, follow_redirects=True, headers=headers) as client:
        for index, asset in enumerate(media):
            content = bytearray()
            async with client.stream("GET", asset.url) as response:
                response.raise_for_status()
                declared_size = int(response.headers.get("content-length", "0") or 0)
                if declared_size > MAX_SINGLE_MEDIA_BYTES:
                    raise ValueError(f"Media item is too large: {declared_size} bytes")
                async for chunk in response.aiter_bytes():
                    content.extend(chunk)
                    if len(content) > MAX_SINGLE_MEDIA_BYTES:
                        raise ValueError("Media item exceeded the in-memory size limit")
            total_size += len(content)
            if total_size > MAX_TOTAL_MEDIA_BYTES:
                raise ValueError("Media album exceeded the in-memory size limit")
            files.append(BufferedInputFile(bytes(content), _media_filename(asset.url, asset.kind, index)))
    return files


async def _send_media_payload(bot: Bot, chat_id: int, media, payloads, caption: str | None) -> None:
    if len(media) == 1:
        asset = media[0]
        if asset.kind == "video":
            await bot.send_video(chat_id, payloads[0], caption=caption, supports_streaming=True)
        else:
            await bot.send_photo(chat_id, payloads[0], caption=caption)
        return

    album = []
    for index, (asset, payload) in enumerate(zip(media, payloads)):
        kwargs = {"media": payload, "caption": caption if index == 0 else None}
        album.append(InputMediaVideo(**kwargs) if asset.kind == "video" else InputMediaPhoto(**kwargs))
    await bot.send_media_group(chat_id, album)


async def _send_media_copy(bot: Bot, chat_id: int, item: FeedItem) -> bool:
    item_media = getattr(item, "media", ())
    if not item_media:
        return False

    text = feed_text(item)
    caption = text if len(text) <= 1024 else None
    media = item_media[:10]
    if len(media) == 1 and media[0].kind == "video_note":
        try:
            in_memory_file = (await _download_media_assets(media))[0]
            await bot.send_video_note(chat_id, in_memory_file)
            if text:
                await bot.send_message(chat_id, text[:4000])
            return True
        except Exception as error:
            logger.warning(
                "Could not send parsed Telegram video note for %s: %s: %s",
                item.url,
                type(error).__name__,
                error,
            )
            return False

    try:
        await _send_media_payload(bot, chat_id, media, [asset.url for asset in media], caption)
    except Exception as url_error:
        logger.info("Telegram could not fetch remote media for %s: %s", item.url, url_error)
        try:
            in_memory_files = await _download_media_assets(media)
            await _send_media_payload(bot, chat_id, media, in_memory_files, caption)
        except Exception as upload_error:
            logger.warning(
                "Could not send parsed Telegram media for %s: %s: %s",
                item.url,
                type(upload_error).__name__,
                upload_error,
            )
            return False

    try:
        if caption is None and text:
            await bot.send_message(chat_id, text[:4000])
        return True
    except Exception as error:
        logger.warning(
            "Media was sent but its separate caption failed for %s: %s: %s",
            item.url,
            type(error).__name__,
            error,
        )
        return True


async def forward_or_copy_feed_item(bot: Bot, chat_id: int, item: FeedItem) -> str:
    if item.channel_username and item.message_id:
        try:
            await bot.forward_message(chat_id, f"@{item.channel_username}", item.message_id)
            return "forward"
        except Exception as error:
            logger.warning(
                "Could not forward Telegram post %s/%s: %s",
                item.channel_username,
                item.message_id,
                error,
            )
    if await _send_media_copy(bot, chat_id, item):
        return "media"
    await bot.send_message(chat_id, feed_text(item)[:4000])
    return "text"
