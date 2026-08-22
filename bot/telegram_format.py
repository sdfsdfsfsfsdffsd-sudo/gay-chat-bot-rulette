from __future__ import annotations

import html
import re


_MARKDOWN_BOLD_RE = re.compile(r"\*\*(.+?)\*\*", re.DOTALL)


def normalize_telegram_html(text: str) -> str:
    if "**" not in text:
        return text
    escaped = html.escape(text, quote=False)
    return _MARKDOWN_BOLD_RE.sub(r"<b>\1</b>", escaped)
