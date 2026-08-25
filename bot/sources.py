from __future__ import annotations

import random
import re
from dataclasses import dataclass

import httpx
from bs4 import BeautifulSoup


@dataclass(frozen=True)
class FeedItem:
    key: str
    text: str
    url: str
    channel_username: str | None = None
    message_id: int | None = None


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
