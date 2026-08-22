from __future__ import annotations

import html
from dataclasses import dataclass
from pathlib import Path

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot import prompts as default_prompts
from bot.env_file import read_env
from setup_cli import DEFAULTS, QUESTIONS


SECRET_KEYS = {"TELEGRAM_BOT_TOKEN", "OPENROUTER_API_KEY"}
PROMPT_TEXT_KEYS = {
    "ANSWER_SYSTEM_PROMPT_TEXT": "Answer system prompt",
    "SUMMARY_SYSTEM_PROMPT_TEXT": "Summary system prompt",
    "CONSPIRACY_SYSTEM_PROMPT_TEXT": "Conspiracy system prompt",
    "HOROSCOPE_SYSTEM_PROMPT_TEXT": "Horoscope system prompt",
    "JOKE_SYSTEM_PROMPT_TEXT": "Joke system prompt",
    "ROAST_SYSTEM_PROMPT_TEXT": "Roast system prompt",
    "SUMMARY_PROMPT_TEXT": "Summary prompt text",
    "CONSPIRACY_PROMPT_TEXT": "Conspiracy prompt text",
    "HOROSCOPE_PROMPT_TEXT": "Horoscope prompt text",
    "JOKE_PROMPT_TEXT": "Joke prompt text",
    "ROAST_PROMPT_TEXT": "Roast prompt text",
}

PROMPT_FALLBACKS = {
    "ANSWER_SYSTEM_PROMPT_TEXT": (None, default_prompts.ANSWER_SYSTEM_PROMPT),
    "SUMMARY_SYSTEM_PROMPT_TEXT": ("SYSTEM_PROMPT_PATH", default_prompts.SYSTEM_BASE),
    "CONSPIRACY_SYSTEM_PROMPT_TEXT": ("SYSTEM_PROMPT_PATH", default_prompts.SYSTEM_BASE),
    "HOROSCOPE_SYSTEM_PROMPT_TEXT": (None, ""),
    "JOKE_SYSTEM_PROMPT_TEXT": (None, ""),
    "ROAST_SYSTEM_PROMPT_TEXT": (None, ""),
    "SUMMARY_PROMPT_TEXT": ("SUMMARY_PROMPT_PATH", default_prompts.SUMMARY_PROMPT),
    "CONSPIRACY_PROMPT_TEXT": ("CONSPIRACY_PROMPT_PATH", default_prompts.CONSPIRACY_PROMPT),
    "HOROSCOPE_PROMPT_TEXT": ("HOROSCOPE_PROMPT_PATH", default_prompts.HOROSCOPE_PROMPT),
    "JOKE_PROMPT_TEXT": ("JOKE_PROMPT_PATH", default_prompts.JOKE_PROMPT),
    "ROAST_PROMPT_TEXT": ("ROAST_PROMPT_PATH", default_prompts.ROAST_PROMPT),
}


@dataclass(frozen=True)
class AdminField:
    key: str
    label: str
    secret: bool = False


GROUPS: dict[str, tuple[str, list[str]]] = {
    "main": (
        "Основное",
        [
            "TELEGRAM_BOT_TOKEN",
            "OPENROUTER_API_KEY",
            "BOT_CHAT_ID",
            "ADMIN_USER_IDS",
            "TARGET_USERNAME",
            "TIMEZONE",
        ],
    ),
    "models": (
        "Модели",
        [
            "OPENROUTER_DEFAULT_MODEL",
            "OPENROUTER_QUALITY_MODEL",
            "OPENROUTER_CHEAP_MODEL",
            "ANSWER_MODEL",
            "SUMMARY_MODEL",
            "CONSPIRACY_MODEL",
            "HOROSCOPE_MODEL",
            "JOKE_MODEL",
            "ROAST_MODEL",
        ],
    ),
    "sources": (
        "Источники",
        [
            "IMAGE_SOURCE_CHANNELS",
            "ALABUGA_CHANNEL_URL",
            "ALABUGA_JOBS_URL",
            "LOCAL_IMAGE_DIR",
            "DATABASE_PATH",
        ],
    ),
    "schedule": (
        "Расписание",
        [
            "HOROSCOPE_TIME",
            "DAILY_SUMMARY_TIME",
            "WORD_STATS_TIME",
            "JOKE_TIME",
            "RANDOM_IMAGE_EVERY_MINUTES",
            "RANDOM_IMAGE_PROBABILITY",
            "ROAST_EVERY_MINUTES",
            "ROAST_PROBABILITY",
            "CONSPIRACY_EVERY_DAYS",
            "TRACKED_WORDS",
        ],
    ),
    "answer": ("Answer", []),
    "summary": ("Summary", []),
    "conspiracy": ("Conspiracy", []),
    "horoscope": ("Horoscope", []),
    "joke": ("Joke", []),
    "roast": ("Roast", []),
    "prompts": (
        "Prompt paths",
        [
            "SYSTEM_PROMPT_PATH",
            "SUMMARY_PROMPT_PATH",
            "CONSPIRACY_PROMPT_PATH",
            "HOROSCOPE_PROMPT_PATH",
            "JOKE_PROMPT_PATH",
            "ROAST_PROMPT_PATH",
        ],
    ),
    "prompt_texts": ("Prompt text", list(PROMPT_TEXT_KEYS)),
}


def _build_fields() -> dict[str, AdminField]:
    fields: dict[str, AdminField] = {}
    for key, label, secret in QUESTIONS:
        fields[key] = AdminField(key, label, secret or key in SECRET_KEYS)
    for key in DEFAULTS:
        fields.setdefault(key, AdminField(key, key.replace("_", " ").title(), key in SECRET_KEYS))
    for key, label in PROMPT_TEXT_KEYS.items():
        fields.setdefault(key, AdminField(key, label, False))
    return fields


FIELDS = _build_fields()
for prefix in ("ANSWER", "SUMMARY", "CONSPIRACY", "HOROSCOPE", "JOKE", "ROAST"):
    group_key = prefix.lower()
    GROUPS[group_key] = (
        GROUPS[group_key][0],
        [key for key in FIELDS if key.startswith(f"{prefix}_")],
    )


def admin_home_keyboard() -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    current_row: list[InlineKeyboardButton] = []
    for group_key, (title, _) in GROUPS.items():
        current_row.append(InlineKeyboardButton(text=title, callback_data=f"admin:g:{group_key}"))
        if len(current_row) == 2:
            rows.append(current_row)
            current_row = []
    if current_row:
        rows.append(current_row)
    rows.append([InlineKeyboardButton(text="Закрыть", callback_data="admin:close")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_group_keyboard(group_key: str) -> InlineKeyboardMarkup:
    _, keys = GROUPS[group_key]
    rows = [[InlineKeyboardButton(text=FIELDS[key].label, callback_data=f"admin:f:{key}")] for key in keys if key in FIELDS]
    rows.append([InlineKeyboardButton(text="Назад", callback_data="admin:home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_field_keyboard(key: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Изменить", callback_data=f"admin:set:{key}")],
            [InlineKeyboardButton(text="Очистить", callback_data=f"admin:clear:{key}")],
            [InlineKeyboardButton(text="Назад", callback_data=f"admin:back:{group_for_key(key)}")],
        ]
    )


def group_for_key(key: str) -> str:
    for group_key, (_, keys) in GROUPS.items():
        if key in keys:
            return group_key
    return "main"


def display_value(key: str, value: str) -> str:
    if not value:
        return "<пусто>"
    if FIELDS[key].secret:
        return value[:4] + "..." + value[-4:] if len(value) > 8 else "***"
    return value if len(value) <= 500 else value[:497] + "..."


def admin_home_text() -> str:
    return (
        "<b>Admin</b>\n\n"
        "Choose a section, then a setting. New values are stored in SQLite and applied in runtime.\n"
        "<code>.env</code> stays as the fallback/bootstrap layer."
    )


def admin_group_text(group_key: str) -> str:
    title, _ = GROUPS[group_key]
    return f"<b>{html.escape(title)}</b>\n\nВыбери параметр."


def admin_field_text(
    key: str,
    prompt_overrides: dict[str, str] | None = None,
    setting_overrides: dict[str, str] | None = None,
) -> str:
    env = read_env()
    field = FIELDS[key]
    if key in PROMPT_TEXT_KEYS:
        if key in (prompt_overrides or {}):
            value = (prompt_overrides or {})[key]
            source = "admin prompt storage"
        else:
            path_key, fallback = PROMPT_FALLBACKS[key]
            path_value = env.get(path_key, DEFAULTS.get(path_key, "")) if path_key else ""
            path = Path(path_value) if path_value else None
            value = path.read_text(encoding="utf-8").strip() if path and path.exists() else fallback.strip()
            source = "prompt file/default"
    elif key in (setting_overrides or {}):
        value = (setting_overrides or {})[key]
        source = "admin settings storage"
    else:
        value = env.get(key, DEFAULTS.get(key, ""))
        source = ".env/default"
    return (
        f"<b>{html.escape(field.label)}</b>\n"
        f"<code>{html.escape(key)}</code>\n\n"
        f"Источник: <code>{html.escape(source)}</code>\n"
        f"Текущее значение:\n<code>{html.escape(display_value(key, value))}</code>\n\n"
        "Нажми “Изменить”, чтобы отправить новое значение следующим сообщением."
    )


def admin_set_prompt_text(key: str) -> str:
    field = FIELDS[key]
    return (
        f"Отправь новое значение для <b>{html.escape(field.label)}</b>.\n"
        f"Ключ: <code>{html.escape(key)}</code>\n\n"
        "Чтобы очистить значение, отправь <code>-</code>.\n"
        "Для многострочного текста можно отправить обычное многострочное сообщение.\n"
        "Чтобы отменить, отправь <code>/cancel</code>."
    )
