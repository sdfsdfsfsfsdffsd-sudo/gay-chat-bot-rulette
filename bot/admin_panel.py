from __future__ import annotations

import html
from dataclasses import dataclass
from pathlib import Path

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot import prompts as default_prompts
from bot.bully import DEFAULT_BULLY_MESSAGE_TEXT
from bot.config import BOOLEAN_SETTING_KEYS
from bot.env_file import read_env
from setup_cli import DEFAULTS, QUESTIONS


SECRET_KEYS = {"TELEGRAM_BOT_TOKEN", "OPENROUTER_API_KEY", "TELEGRAM_USER_API_HASH", "TELEGRAM_USER_SESSION"}
PROMPT_TEXT_KEYS = {
    "ANSWER_SYSTEM_PROMPT_TEXT": "Ответы · System prompt",
    "SUMMARY_SYSTEM_PROMPT_TEXT": "Сводка · System prompt",
    "CONSPIRACY_SYSTEM_PROMPT_TEXT": "Заговоры · System prompt",
    "HOROSCOPE_SYSTEM_PROMPT_TEXT": "Гороскоп · System prompt",
    "JOKE_SYSTEM_PROMPT_TEXT": "Анекдоты · System prompt",
    "SUMMARY_PROMPT_TEXT": "Сводка · Основной промпт",
    "CONSPIRACY_PROMPT_TEXT": "Заговоры · Основной промпт",
    "HOROSCOPE_PROMPT_TEXT": "Гороскоп · Основной промпт",
    "JOKE_PROMPT_TEXT": "Анекдоты · Основной промпт",
    "JOKE_A_PROMPT_TEXT": "Joke A · Основной промпт",
    "JOKE_B_PROMPT_TEXT": "Joke B · Основной промпт",
}

FIELD_LABELS = {
    "TELEGRAM_BOT_TOKEN": "Токен Telegram-бота",
    "OPENROUTER_API_KEY": "Ключ OpenRouter API",
    "BOT_CHAT_ID": "Привязанный чат (Chat ID)",
    "ADMIN_USER_IDS": "Администраторы (Telegram ID через запятую)",
    "TELEGRAM_USER_API_ID": "Userbot · Telegram API ID",
    "TELEGRAM_USER_API_HASH": "Userbot · Telegram API hash",
    "TELEGRAM_USER_SESSION": "Userbot · StringSession",
    "TARGET_USERNAME": "Участник для автоматического roast",
    "BULLY_TARGET_USERNAME": "Bully · цель по умолчанию",
    "TIMEZONE": "Часовой пояс",
    "OPENROUTER_DEFAULT_MODEL": "Модель по умолчанию",
    "OPENROUTER_QUALITY_MODEL": "Качественная модель",
    "OPENROUTER_CHEAP_MODEL": "Экономичная модель",
    "IMAGE_SOURCE_CHANNELS": "Каналы-источники изображений",
    "ALABUGA_CHANNEL_URL": "Канал Алабуга Политех",
    "ALABUGA_JOBS_URL": "Источник вакансий Алабуги",
    "LOCAL_IMAGE_DIR": "Каталог локальных изображений",
    "DATABASE_PATH": "Путь к SQLite",
    "TRACKED_WORDS": "Отслеживаемые слова",
    "ANSWER_WEB_SEARCH_ENABLED": "Ответы · поиск в интернете",
    "HOROSCOPE_ENABLED": "Автопостинг · гороскоп",
    "SUMMARY_ENABLED": "Автопостинг · сводка",
    "WORD_STATS_ENABLED": "Автопостинг · статистика слов",
    "JOKE_A_ENABLED": "Автопостинг · Joke A",
    "JOKE_B_ENABLED": "Автопостинг · Joke B",
    "CONSPIRACY_ENABLED": "Автопостинг · теория заговора",
    "RANDOM_IMAGE_ENABLED": "Автопостинг · случайные картинки",
    "AUTO_BULLY_ENABLED": "Автопостинг · bully",
    "ALABUGA_ENABLED": "Автопостинг · Алабуга",
    "JOKE_A_TIME": "Joke A · время отправки",
    "JOKE_A_EVERY_DAYS": "Joke A · интервал в днях",
    "JOKE_B_TIME": "Joke B · время отправки",
    "JOKE_B_EVERY_DAYS": "Joke B · интервал в днях",
    "JOKE_A_PROMPT_PATH": "Joke A · файл промпта",
    "JOKE_B_PROMPT_PATH": "Joke B · файл промпта",
    "BULLY_MESSAGE_TEXT": "Bully · статичный текст",
}

SERVICE_LABELS = {
    "ANSWER": "Ответы",
    "SUMMARY": "Сводка",
    "CONSPIRACY": "Заговоры",
    "HOROSCOPE": "Гороскоп",
    "JOKE": "Анекдоты",
}

PARAMETER_LABELS = {
    "MODEL": "модель",
    "TEMPERATURE": "температура",
    "TOP_P": "Top P",
    "TOP_K": "Top K",
    "PRESENCE_PENALTY": "presence penalty",
    "FREQUENCY_PENALTY": "frequency penalty",
    "REPETITION_PENALTY": "repetition penalty",
    "MIN_P": "Min P",
    "TOP_A": "Top A",
    "MAX_TOKENS": "максимум токенов",
    "TIME": "время отправки",
    "EVERY_DAYS": "интервал в днях",
    "CONTEXT_DAYS": "контекст в днях",
    "CONTEXT_HOURS": "контекст в часах",
    "PROMPT_PATH": "файл промпта",
}

PROMPT_FALLBACKS = {
    "ANSWER_SYSTEM_PROMPT_TEXT": (None, default_prompts.ANSWER_SYSTEM_PROMPT),
    "SUMMARY_SYSTEM_PROMPT_TEXT": ("SYSTEM_PROMPT_PATH", default_prompts.SYSTEM_BASE),
    "CONSPIRACY_SYSTEM_PROMPT_TEXT": (None, ""),
    "HOROSCOPE_SYSTEM_PROMPT_TEXT": (None, ""),
    "JOKE_SYSTEM_PROMPT_TEXT": (None, ""),
    "SUMMARY_PROMPT_TEXT": ("SUMMARY_PROMPT_PATH", default_prompts.SUMMARY_PROMPT),
    "CONSPIRACY_PROMPT_TEXT": ("CONSPIRACY_PROMPT_PATH", default_prompts.CONSPIRACY_PROMPT),
    "HOROSCOPE_PROMPT_TEXT": ("HOROSCOPE_PROMPT_PATH", default_prompts.HOROSCOPE_PROMPT),
    "JOKE_PROMPT_TEXT": ("JOKE_PROMPT_PATH", default_prompts.JOKE_PROMPT),
    "JOKE_A_PROMPT_TEXT": ("JOKE_A_PROMPT_PATH", default_prompts.JOKE_PROMPT),
    "JOKE_B_PROMPT_TEXT": ("JOKE_B_PROMPT_PATH", default_prompts.JOKE_B_PROMPT),
}


@dataclass(frozen=True)
class AdminField:
    key: str
    label: str
    secret: bool = False


GROUPS: dict[str, tuple[str, list[str]]] = {
    "main": (
        "⚙️ Основное",
        [
            "TELEGRAM_BOT_TOKEN",
            "OPENROUTER_API_KEY",
            "BOT_CHAT_ID",
            "ADMIN_USER_IDS",
            "TELEGRAM_USER_API_ID",
            "TELEGRAM_USER_API_HASH",
            "TELEGRAM_USER_SESSION",
            "TARGET_USERNAME",
            "BULLY_TARGET_USERNAME",
            "TIMEZONE",
        ],
    ),
    "models": (
        "🧠 Модели",
        [
            "OPENROUTER_DEFAULT_MODEL",
            "OPENROUTER_QUALITY_MODEL",
            "OPENROUTER_CHEAP_MODEL",
            "ANSWER_MODEL",
            "SUMMARY_MODEL",
            "CONSPIRACY_MODEL",
            "HOROSCOPE_MODEL",
            "JOKE_MODEL",
        ],
    ),
    "sources": (
        "📡 Источники",
        [
            "IMAGE_SOURCE_CHANNELS",
            "ALABUGA_CHANNEL_URL",
            "ALABUGA_JOBS_URL",
            "LOCAL_IMAGE_DIR",
            "DATABASE_PATH",
        ],
    ),
    "schedule": (
        "🕒 Расписание",
        [
            "HOROSCOPE_TIME",
            "HOROSCOPE_EVERY_DAYS",
            "DAILY_SUMMARY_TIME",
            "SUMMARY_EVERY_DAYS",
            "WORD_STATS_TIME",
            "JOKE_TIME",
            "JOKE_EVERY_DAYS",
            "JOKE_A_TIME",
            "JOKE_A_EVERY_DAYS",
            "JOKE_B_TIME",
            "JOKE_B_EVERY_DAYS",
            "CONSPIRACY_TIME",
            "CONSPIRACY_EVERY_DAYS",
            "ALABUGA_EVERY_HOURS",
            "SUMMARY_CONTEXT_HOURS",
            "HOROSCOPE_CONTEXT_DAYS",
            "CONSPIRACY_CONTEXT_DAYS",
            "RANDOM_IMAGE_EVERY_MINUTES",
            "RANDOM_IMAGE_PROBABILITY",
            "ROAST_EVERY_MINUTES",
            "ROAST_PROBABILITY",
            "BULLY_MESSAGE_TEXT",
            "TRACKED_WORDS",
        ],
    ),
    "automations": (
        "⏯ Автопостинг",
        [
            "HOROSCOPE_ENABLED",
            "SUMMARY_ENABLED",
            "WORD_STATS_ENABLED",
            "JOKE_A_ENABLED",
            "JOKE_B_ENABLED",
            "CONSPIRACY_ENABLED",
            "RANDOM_IMAGE_ENABLED",
            "AUTO_BULLY_ENABLED",
            "ALABUGA_ENABLED",
        ],
    ),
    "answer": ("💬 Ответы", []),
    "summary": ("📝 Сводка", []),
    "conspiracy": ("🕵️ Заговоры", []),
    "horoscope": ("🔮 Гороскоп", []),
    "joke": ("🎭 Анекдоты", []),
    "prompts": (
        "📁 Файлы промптов",
        [
            "SYSTEM_PROMPT_PATH",
            "SUMMARY_PROMPT_PATH",
            "CONSPIRACY_PROMPT_PATH",
            "HOROSCOPE_PROMPT_PATH",
            "JOKE_PROMPT_PATH",
            "JOKE_A_PROMPT_PATH",
            "JOKE_B_PROMPT_PATH",
        ],
    ),
    "prompt_texts": ("✍️ Тексты промптов", list(PROMPT_TEXT_KEYS)),
}


def field_label(key: str, fallback: str) -> str:
    if key in FIELD_LABELS:
        return FIELD_LABELS[key]
    for prefix, service_label in SERVICE_LABELS.items():
        marker = f"{prefix}_"
        if key.startswith(marker):
            suffix = key[len(marker):]
            return f"{service_label} · {PARAMETER_LABELS.get(suffix, fallback)}"
    return fallback


def _build_fields() -> dict[str, AdminField]:
    fields: dict[str, AdminField] = {}
    for key, label, secret in QUESTIONS:
        fields[key] = AdminField(key, field_label(key, label), secret or key in SECRET_KEYS)
    for key in DEFAULTS:
        fallback = key.replace("_", " ").title()
        fields.setdefault(key, AdminField(key, field_label(key, fallback), key in SECRET_KEYS))
    for key, label in PROMPT_TEXT_KEYS.items():
        fields.setdefault(key, AdminField(key, label, False))
    return fields


FIELDS = _build_fields()
for prefix in ("ANSWER", "SUMMARY", "CONSPIRACY", "HOROSCOPE", "JOKE"):
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
    rows = []
    if key in BOOLEAN_SETTING_KEYS:
        rows.append([InlineKeyboardButton(text="⏯ Переключить", callback_data=f"admin:toggle:{key}")])
    rows.extend(
        [
            [InlineKeyboardButton(text="Изменить", callback_data=f"admin:set:{key}")],
            [InlineKeyboardButton(text="Очистить", callback_data=f"admin:clear:{key}")],
            [InlineKeyboardButton(text="Назад", callback_data=f"admin:back:{group_for_key(key)}")],
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


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
        "<b>⚙️ Панель управления</b>\n\n"
        "Выбери раздел, затем нужный параметр.\n\n"
        "<b>Как применяются изменения</b>\n"
        "Значения сохраняются в SQLite и применяются сразу, без перезапуска. "
        "Конфигурация из <code>.env</code> используется как резервная."
    )


def admin_group_text(group_key: str) -> str:
    title, _ = GROUPS[group_key]
    return f"<b>{html.escape(title)}</b>\n\nВыбери параметр для просмотра или изменения."


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
        value = env.get(key, DEFAULTS.get(key, DEFAULT_BULLY_MESSAGE_TEXT if key == "BULLY_MESSAGE_TEXT" else ""))
        source = ".env/default"
    return (
        f"<b>⚙️ {html.escape(field.label)}</b>\n"
        f"<code>{html.escape(key)}</code>\n\n"
        f"<b>Источник</b>\n<code>{html.escape(source)}</code>\n\n"
        f"<b>Текущее значение</b>\n<code>{html.escape(display_value(key, value))}</code>\n\n"
        "Нажми «Изменить» и отправь новое значение следующим сообщением."
    )


def admin_set_prompt_text(key: str) -> str:
    field = FIELDS[key]
    hint = (
        "\n\n<b>Формат:</b> Telegram ID через запятую.\n"
        "Пример: <code>123456789, 987654321</code>"
        if key == "ADMIN_USER_IDS"
        else ""
    )
    return (
        f"<b>✏️ Изменение параметра</b>\n\n"
        f"<b>{html.escape(field.label)}</b>\n"
        f"Ключ: <code>{html.escape(key)}</code>"
        f"{hint}\n\n"
        "Отправь новое значение одним сообщением.\n"
        "Очистить override: <code>-</code>\n"
        "Отменить изменение: <code>/cancel</code>"
    )
