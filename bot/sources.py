from __future__ import annotations

import random
import re
from dataclasses import dataclass
from html import escape as html_escape, unescape

import httpx
from bs4 import BeautifulSoup, NavigableString, Tag


@dataclass(frozen=True)
class FeedMedia:
    kind: str
    url: str


@dataclass(frozen=True)
class FeedItem:
    key: str
    text: str
    url: str
    channel_username: str | None = None
    message_id: int | None = None
    media: tuple[FeedMedia, ...] = ()
    html_text: str = ""


BACKGROUND_URL_RE = re.compile(r"background-image\s*:\s*url\((['\"]?)(.*?)\1\)", re.IGNORECASE)
TELEGRAM_TAGS = {
    "b": "b",
    "strong": "b",
    "i": "i",
    "em": "i",
    "u": "u",
    "ins": "u",
    "s": "s",
    "strike": "s",
    "del": "s",
    "code": "code",
    "pre": "pre",
    "blockquote": "blockquote",
}


def _telegram_html(node) -> str:
    if isinstance(node, NavigableString):
        return html_escape(str(node))
    if not isinstance(node, Tag):
        return ""
    if node.name == "br":
        return "\n"

    inner = "".join(_telegram_html(child) for child in node.children)
    if node.name == "tg-emoji" or (node.name == "i" and "emoji" in node.get("class", ())):
        return html_escape(node.get_text())
    if node.name == "a":
        href = node.get("href")
        return f'<a href="{html_escape(href, quote=True)}">{inner}</a>' if href else inner
    output_tag = TELEGRAM_TAGS.get(node.name)
    return f"<{output_tag}>{inner}</{output_tag}>" if output_tag else inner


def _plain_text(node) -> str:
    if isinstance(node, NavigableString):
        return str(node)
    if not isinstance(node, Tag):
        return ""
    if node.name == "br":
        return "\n"
    return "".join(_plain_text(child) for child in node.children)


def parse_tg_post_ref(value: str) -> tuple[str, int] | None:
    match = re.search(r"(?:https://t\.me/)?(?!s/)([A-Za-z0-9_]{5,})/(\d+)", value)
    if not match:
        return None
    return match.group(1), int(match.group(2))


def parse_telegram_feed_html(content: str, source_url: str, *, limit: int = 8) -> list[FeedItem]:
    soup = BeautifulSoup(content, "html.parser")
    items: list[FeedItem] = []
    for message in soup.select(".tgme_widget_message")[-limit:]:
        post_url = message.get("data-post") or ""
        key = f"tg:{post_url}"
        text_node = message.select_one(".tgme_widget_message_text")
        text = _plain_text(text_node).strip() if text_node else ""
        html_text = "".join(_telegram_html(child) for child in text_node.children).strip() if text_node else ""
        link_node = message.select_one("a.tgme_widget_message_date, .tgme_widget_message_date a")
        href = link_node["href"] if link_node and link_node.has_attr("href") else source_url
        post_ref = parse_tg_post_ref(post_url) or parse_tg_post_ref(href)
        if post_ref:
            href = f"https://t.me/{post_ref[0]}/{post_ref[1]}"

        media: list[FeedMedia] = []
        seen_urls: set[str] = set()
        for photo in message.select(".tgme_widget_message_photo_wrap"):
            match = BACKGROUND_URL_RE.search(photo.get("style", ""))
            if match:
                media_url = unescape(match.group(2))
                if media_url and media_url not in seen_urls:
                    media.append(FeedMedia("photo", media_url))
                    seen_urls.add(media_url)
        for video in message.select("video[src]"):
            classes = set(video.get("class", ()))
            if "blured" in classes or "js-message_video_blured" in classes:
                continue
            media_url = unescape(video.get("src", ""))
            if media_url and media_url not in seen_urls:
                kind = "video_note" if "tgme_widget_message_roundvideo" in classes else "video"
                media.append(FeedMedia(kind, media_url))
                seen_urls.add(media_url)

        if text or media:
            items.append(
                FeedItem(
                    key=key,
                    text=text,
                    url=href,
                    channel_username=post_ref[0] if post_ref else None,
                    message_id=post_ref[1] if post_ref else None,
                    media=tuple(media[:10]),
                    html_text=html_text,
                )
            )
    return items


async def fetch_telegram_feed(url: str, *, limit: int = 8) -> list[FeedItem]:
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        response = await client.get(url)
        response.raise_for_status()
    return parse_telegram_feed_html(response.text, url, limit=limit)


async def fetch_latest_unsent_telegram_item(
    url: str,
    was_sent,
    *,
    limit: int = 12,
) -> FeedItem | None:
    for item in reversed(await fetch_telegram_feed(url, limit=limit)):
        if not await was_sent(item.key):
            return item
    return None


async def fetch_random_telegram_item(url: str, *, limit: int = 30) -> FeedItem | None:
    items = await fetch_telegram_feed(url, limit=limit)
    return random.choice(items) if items else None


async def fetch_random_unsent_telegram_item(
    url: str,
    was_sent,
    *,
    limit: int = 30,
    video_note_weight: float = 1.1,
) -> FeedItem | None:
    items = [item for item in await fetch_telegram_feed(url, limit=limit) if not await was_sent(item.key)]
    if not items:
        return None
    weights = [video_note_weight if any(media.kind == "video_note" for media in item.media) else 1.0 for item in items]
    return random.choices(items, weights=weights, k=1)[0]
