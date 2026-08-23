from __future__ import annotations

import mimetypes
import random
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}


@dataclass(frozen=True)
class FeedItem:
    key: str
    text: str
    url: str
    channel_username: str | None = None
    message_id: int | None = None


def random_local_image(directory: Path) -> Path | None:
    if not directory.exists():
        return None
    candidates = [
        path
        for path in directory.rglob("*")
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
    ]
    return random.choice(candidates) if candidates else None


def normalize_tg_web_url(source: str) -> str | None:
    source = source.strip()
    if not source:
        return None
    if source.startswith("https://t.me/s/"):
        return source
    if source.startswith("https://t.me/"):
        name = source.rstrip("/").split("/")[-1]
        return f"https://t.me/s/{name}"
    name = source.lstrip("@")
    if re.fullmatch(r"[A-Za-z0-9_]{5,}", name):
        return f"https://t.me/s/{name}"
    return None


def parse_tg_post_ref(value: str) -> tuple[str, int] | None:
    match = re.search(r"(?:https://t\.me/)?(?!s/)([A-Za-z0-9_]{5,})/(\d+)", value)
    if not match:
        return None
    return match.group(1), int(match.group(2))


async def fetch_telegram_feed(url: str, *, limit: int = 8) -> list[FeedItem]:
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        response = await client.get(url)
        response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    items: list[FeedItem] = []
    for message in soup.select(".tgme_widget_message")[-limit:]:
        post_url = message.get("data-post") or ""
        key = f"tg:{post_url}"
        text_node = message.select_one(".tgme_widget_message_text")
        text = text_node.get_text("\n", strip=True) if text_node else ""
        link_node = message.select_one(".tgme_widget_message_date a")
        href = link_node["href"] if link_node and link_node.has_attr("href") else url
        post_ref = parse_tg_post_ref(post_url) or parse_tg_post_ref(href)
        if text:
            items.append(
                FeedItem(
                    key=key,
                    text=text,
                    url=href,
                    channel_username=post_ref[0] if post_ref else None,
                    message_id=post_ref[1] if post_ref else None,
                )
            )
    return items


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


async def random_channel_image_url(sources: list[str]) -> str | None:
    urls = [normalize_tg_web_url(source) for source in sources]
    urls = [url for url in urls if url]
    random.shuffle(urls)
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        for url in urls:
            response = await client.get(url)
            if response.status_code >= 400:
                continue
            soup = BeautifulSoup(response.text, "html.parser")
            candidates: list[str] = []
            for link in soup.select(".tgme_widget_message_photo_wrap"):
                style = link.get("style", "")
                match = re.search(r"url\('([^']+)'\)", style)
                if match:
                    candidates.append(urljoin(url, match.group(1)))
            if candidates:
                return random.choice(candidates)
    return None


def guess_mime(path: Path) -> str:
    return mimetypes.guess_type(path.name)[0] or "application/octet-stream"
