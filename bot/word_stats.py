from __future__ import annotations

import re
from collections import Counter, defaultdict
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from bot.storage import Storage


def count_words_by_user(
    rows: list[dict[str, str]],
    tracked_words: list[str],
) -> dict[str, Counter[str]]:
    patterns = {
        word: re.compile(rf"(?<!\w){re.escape(word)}(?!\w)", flags=re.IGNORECASE)
        for word in tracked_words
        if word.strip()
    }
    stats: dict[str, Counter[str]] = defaultdict(Counter)
    for row in rows:
        name = row["display_name"] or "user"
        text = row["text"] or ""
        for word, pattern in patterns.items():
            count = len(pattern.findall(text))
            if count:
                stats[name][word] += count
    return dict(stats)


def format_word_stats(stats: dict[str, Counter[str]], tracked_words: list[str]) -> str:
    words = [word for word in tracked_words if word.strip()]
    if not words:
        return "Daily word stats are disabled: TRACKED_WORDS is empty."
    if not stats:
        return "Daily word stats: nobody hit the tracked words today."

    totals = Counter()
    for counter in stats.values():
        totals.update(counter)

    lines = ["Daily tracked word stats", ""]
    lines.append("Totals: " + ", ".join(f"{word}: {totals[word]}" for word in words))
    lines.append("")

    ranked = sorted(stats.items(), key=lambda item: sum(item[1].values()), reverse=True)
    for name, counter in ranked[:20]:
        total = sum(counter.values())
        details = ", ".join(f"{word}: {counter[word]}" for word in words if counter[word])
        lines.append(f"{name} - {total} ({details})")
    return "\n".join(lines)


async def build_daily_word_stats(storage: Storage, chat_id: int, tracked_words: list[str]) -> str:
    rows = await storage.recent_message_rows(chat_id, hours=24)
    stats = count_words_by_user(rows, tracked_words)
    return format_word_stats(stats, tracked_words)
