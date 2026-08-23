from __future__ import annotations

DEFAULT_BULLY_MESSAGE_TEXT = "{target}, today the bot has selected you for ceremonial group bullying."


def render_bully_message(template: str | None, target: str) -> str:
    value = (template or "").strip() or DEFAULT_BULLY_MESSAGE_TEXT
    username = target.lstrip("@")
    try:
        return value.format(target=target, username=username)
    except (KeyError, ValueError):
        return f"{target}, {value}"
