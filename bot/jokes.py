from __future__ import annotations

import html
import random
import re
from dataclasses import dataclass
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup


DEFAULT_JOKE_SOURCE_URLS = [
    "https://www.motustrans.ru/forum/forum12/topic3/messages/",
    "https://anekdotovstreet.com/transport/dalnoboyschiki/",
    "https://taha163.ru/?page_id=135",
]

BLOCKED_JOKE_SOURCE_MARKERS = (
    "anekdoty-pro-evreev",
    "/anec/17/",
)


@dataclass(frozen=True)
class JokeItem:
    text: str
    source_url: str


def allowed_joke_source(url: str) -> bool:
    lowered = url.lower()
    return not any(marker in lowered for marker in BLOCKED_JOKE_SOURCE_MARKERS)


def _clean_text(value: str) -> str:
    value = re.sub(r"\r\n?", "\n", value)
    value = re.sub(r"[ \t]+", " ", value)
    value = re.sub(r"\n{3,}", "\n\n", value)
    return value.strip(" \n\t-–—")


def _looks_like_joke(text: str) -> bool:
    if len(text) < 25 or len(text) > 2500:
        return False
    lowered = text.lower()
    blocked_fragments = (
        "читайте свежие",
        "добавить анекдот",
        "поиск по сайту",
        "страницы:",
        "регистрация:",
        "сообщений:",
        "грузоперевозки",
        "все права защищены",
    )
    return not any(fragment in lowered for fragment in blocked_fragments)


def _dedupe(items: list[JokeItem]) -> list[JokeItem]:
    seen: set[str] = set()
    result: list[JokeItem] = []
    for item in items:
        key = re.sub(r"\W+", "", item.text.lower())[:220]
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def _parse_anekdotovstreet(url: str, soup: BeautifulSoup) -> list[JokeItem]:
    items: list[JokeItem] = []
    for paragraph in soup.select("p"):
        text = _clean_text(paragraph.get_text("\n", strip=True))
        if _looks_like_joke(text):
            items.append(JokeItem(text=text, source_url=url))
    return _dedupe(items)


def _parse_motustrans(url: str, soup: BeautifulSoup) -> list[JokeItem]:
    text = soup.get_text("\n", strip=True)
    pattern = re.compile(
        r"#\d+\s*\n\s*\d{2}\.\d{2}\.\d{4}\s+\d{2}:\d{2}:\d{2}\s*(.*?)(?=\n\s*#\d+\s*\n\s*\d{2}\.\d{2}\.\d{4}|\n\s*Страницы:|\Z)",
        re.DOTALL,
    )
    items: list[JokeItem] = []
    for match in pattern.finditer(text):
        post_text = _clean_text(match.group(1))
        post_text = re.sub(r"\n?Image: [^\n]+", "", post_text)
        post_text = _clean_text(post_text)
        chunks = re.split(r"\n{2,}", post_text)
        for chunk in chunks:
            joke = _clean_text(chunk)
            if _looks_like_joke(joke):
                items.append(JokeItem(text=joke, source_url=url))
    return _dedupe(items)


def _parse_generic(url: str, soup: BeautifulSoup) -> list[JokeItem]:
    container = (
        soup.select_one("article")
        or soup.select_one(".entry-content")
        or soup.select_one(".post")
        or soup.select_one(".content")
        or soup.body
        or soup
    )
    items: list[JokeItem] = []
    paragraphs = container.select("p, li")
    if paragraphs:
        for node in paragraphs:
            text = _clean_text(node.get_text("\n", strip=True))
            if _looks_like_joke(text):
                items.append(JokeItem(text=text, source_url=url))
    if not items:
        text = _clean_text(container.get_text("\n", strip=True))
        for chunk in re.split(r"\n{2,}|(?:^|\n)\d+[\).]\s+", text):
            joke = _clean_text(chunk)
            if _looks_like_joke(joke):
                items.append(JokeItem(text=joke, source_url=url))
    return _dedupe(items)


def parse_jokes_from_html(url: str, html_text: str) -> list[JokeItem]:
    soup = BeautifulSoup(html_text, "html.parser")
    host = urlparse(url).netloc.lower()
    if "anekdotovstreet.com" in host:
        return _parse_anekdotovstreet(url, soup)
    if "motustrans.ru" in host:
        return _parse_motustrans(url, soup)
    return _parse_generic(url, soup)


async def fetch_jokes_from_source(client: httpx.AsyncClient, url: str) -> list[JokeItem]:
    if not allowed_joke_source(url):
        return []
    response = await client.get(url)
    response.raise_for_status()
    return parse_jokes_from_html(url, response.text)


async def fetch_random_joke(source_urls: list[str]) -> JokeItem | None:
    urls = [url.strip() for url in source_urls if url.strip() and allowed_joke_source(url)]
    random.shuffle(urls)
    timeout = httpx.Timeout(12, connect=8)
    headers = {"User-Agent": "Mozilla/5.0 TelegramBot JokeFetcher/1.0"}
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True, headers=headers) as client:
        for url in urls:
            try:
                jokes = await fetch_jokes_from_source(client, url)
            except Exception:
                continue
            if jokes:
                return random.choice(jokes)
    return None



def format_joke_html(joke: JokeItem) -> str:
    return html.escape(joke.text, quote=False)
