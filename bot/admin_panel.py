from __future__ import annotations

import html
from dataclasses import dataclass
from datetime import datetime, timedelta
from math import ceil
from pathlib import Path
from zoneinfo import ZoneInfo

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot import prompts as default_prompts
from bot.bully import DEFAULT_BULLY_MESSAGE_TEXT
from bot.config import BOOLEAN_SETTING_KEYS, Settings
from bot.env_file import read_env
from setup_cli import DEFAULTS, QUESTIONS


SECRET_KEYS = {"TELEGRAM_BOT_TOKEN", "OPENROUTER_API_KEY", "TELEGRAM_USER_API_HASH", "TELEGRAM_USER_SESSION"}
PROMPT_TEXT_KEYS = {
    "ANSWER_SYSTEM_PROMPT_TEXT": "Системный промпт",
    "SUMMARY_SYSTEM_PROMPT_TEXT": "Системный промпт",
    "CONSPIRACY_SYSTEM_PROMPT_TEXT": "Системный промпт",
    "HOROSCOPE_SYSTEM_PROMPT_TEXT": "Системный промпт",
    "SUMMARY_PROMPT_TEXT": "Основной промпт",
    "CONSPIRACY_PROMPT_TEXT": "Основной промпт",
    "HOROSCOPE_PROMPT_TEXT": "Основной промпт",
}

PROMPT_FALLBACKS = {
    "ANSWER_SYSTEM_PROMPT_TEXT": (None, default_prompts.ANSWER_SYSTEM_PROMPT),
    "SUMMARY_SYSTEM_PROMPT_TEXT": ("SYSTEM_PROMPT_PATH", default_prompts.SYSTEM_BASE),
    "CONSPIRACY_SYSTEM_PROMPT_TEXT": (None, ""),
    "HOROSCOPE_SYSTEM_PROMPT_TEXT": (None, ""),
    "SUMMARY_PROMPT_TEXT": ("SUMMARY_PROMPT_PATH", default_prompts.SUMMARY_PROMPT),
    "CONSPIRACY_PROMPT_TEXT": ("CONSPIRACY_PROMPT_PATH", default_prompts.CONSPIRACY_PROMPT),
    "HOROSCOPE_PROMPT_TEXT": ("HOROSCOPE_PROMPT_PATH", default_prompts.HOROSCOPE_PROMPT),
}

FIELD_LABELS = {
    "TELEGRAM_BOT_TOKEN": "Токен Telegram-бота",
    "OPENROUTER_API_KEY": "Ключ OpenRouter",
    "BOT_CHAT_ID": "Привязанный чат",
    "ADMIN_USER_IDS": "Администраторы",
    "TELEGRAM_USER_API_ID": "Telegram API ID",
    "TELEGRAM_USER_API_HASH": "Telegram API hash",
    "TELEGRAM_USER_SESSION": "Telegram StringSession",
    "BULLY_TARGET_USERNAME": "Цель буллинга",
    "BULLY_MESSAGE_TEXT": "Текст буллинга",
    "BULLY_EVERY_MINUTES": "Интервал проверки",
    "BULLY_PROBABILITY": "Вероятность отправки",
    "TIMEZONE": "Часовой пояс",
    "DATABASE_PATH": "Файл базы данных",
    "OPENROUTER_DEFAULT_MODEL": "Модель по умолчанию",
    "OPENROUTER_QUALITY_MODEL": "Качественная модель",
    "OPENROUTER_CHEAP_MODEL": "Экономичная модель",
    "ANSWER_MODEL": "Модель ответов",
    "SUMMARY_MODEL": "Модель сводки",
    "CONSPIRACY_MODEL": "Модель теорий заговора",
    "HOROSCOPE_MODEL": "Модель гороскопа",
    "ANSWER_WEB_SEARCH_ENABLED": "Поиск в интернете",
    "HOROSCOPE_ENABLED": "Гороскоп",
    "SUMMARY_ENABLED": "Сводка",
    "WORD_STATS_ENABLED": "Статистика слов",
    "JOKE_A_ENABLED": "Анекдот A",
    "JOKE_B_ENABLED": "Анекдот B",
    "CONSPIRACY_ENABLED": "Теория заговора",
    "AUTO_BULLY_ENABLED": "Автоматический буллинг",
    "ALABUGA_ENABLED": "Алабуга",
    "JOKE_SOURCE_URLS": "Сайты с анекдотами",
    "ALABUGA_CHANNEL_URL": "Канал Алабуга Политех",
    "TRACKED_WORDS": "Отслеживаемые слова",
    "HOROSCOPE_TIME": "Время отправки",
    "HOROSCOPE_EVERY_DAYS": "Интервал в днях",
    "DAILY_SUMMARY_TIME": "Время отправки",
    "SUMMARY_EVERY_DAYS": "Интервал в днях",
    "WORD_STATS_TIME": "Время отправки",
    "JOKE_A_TIME": "Время анекдота A",
    "JOKE_A_EVERY_DAYS": "Интервал анекдота A",
    "JOKE_B_TIME": "Время анекдота B",
    "JOKE_B_EVERY_DAYS": "Интервал анекдота B",
    "CONSPIRACY_TIME": "Время отправки",
    "CONSPIRACY_EVERY_DAYS": "Интервал в днях",
    "ALABUGA_EVERY_HOURS": "Интервал в часах",
    "SUMMARY_CONTEXT_HOURS": "Контекст в часах",
    "HOROSCOPE_CONTEXT_DAYS": "Контекст в днях",
    "CONSPIRACY_CONTEXT_DAYS": "Контекст в днях",
    "SYSTEM_PROMPT_PATH": "Файл системного промпта сводки",
    "SUMMARY_PROMPT_PATH": "Файл промпта сводки",
    "CONSPIRACY_PROMPT_PATH": "Файл промпта теорий",
    "HOROSCOPE_PROMPT_PATH": "Файл промпта гороскопа",
}

SERVICE_LABELS = {
    "ANSWER": "Ответы",
    "SUMMARY": "Сводка",
    "CONSPIRACY": "Теория заговора",
    "HOROSCOPE": "Гороскоп",
}

PARAMETER_LABELS = {
    "TEMPERATURE": "Температура",
    "TOP_P": "Top P",
    "TOP_K": "Top K",
    "PRESENCE_PENALTY": "Presence penalty",
    "FREQUENCY_PENALTY": "Frequency penalty",
    "REPETITION_PENALTY": "Repetition penalty",
    "MIN_P": "Min P",
    "TOP_A": "Top A",
    "MAX_TOKENS": "Максимум токенов",
}


@dataclass(frozen=True)
class AdminField:
    key: str
    label: str
    secret: bool = False
    editable: bool = True


@dataclass(frozen=True)
class AdminGroup:
    title: str
    description: str
    fields: tuple[str, ...] = ()
    children: tuple[str, ...] = ()
    parent: str = "home"
    toggle_dashboard: bool = False


def field_label(key: str, fallback: str) -> str:
    if key in FIELD_LABELS:
        return FIELD_LABELS[key]
    for prefix, service_label in SERVICE_LABELS.items():
        marker = f"{prefix}_"
        if key.startswith(marker):
            suffix = key[len(marker):]
            return f"{service_label}: {PARAMETER_LABELS.get(suffix, fallback)}"
    return fallback


def _build_fields() -> dict[str, AdminField]:
    fields: dict[str, AdminField] = {}
    for key, label, secret in QUESTIONS:
        if key in SECRET_KEYS:
            continue
        fields[key] = AdminField(key, field_label(key, label), secret or key in SECRET_KEYS)
    for key in DEFAULTS:
        if key in SECRET_KEYS:
            continue
        fallback = key.replace("_", " ").title()
        fields.setdefault(key, AdminField(key, field_label(key, fallback), key in SECRET_KEYS))
    for key, label in PROMPT_TEXT_KEYS.items():
        fields[key] = AdminField(key, label)
    if "DATABASE_PATH" in fields:
        fields["DATABASE_PATH"] = AdminField("DATABASE_PATH", FIELD_LABELS["DATABASE_PATH"], editable=False)
    return fields


FIELDS = _build_fields()


def _sampling(prefix: str) -> tuple[str, ...]:
    suffixes = (
        "TEMPERATURE", "TOP_P", "TOP_K", "PRESENCE_PENALTY", "FREQUENCY_PENALTY",
        "REPETITION_PENALTY", "MIN_P", "TOP_A", "MAX_TOKENS",
    )
    return tuple(key for suffix in suffixes if (key := f"{prefix}_{suffix}") in FIELDS)


GROUPS: dict[str, AdminGroup] = {
    "automations": AdminGroup(
        "📅 Автопубликации",
        "Нажатие сразу включает или приостанавливает задачу. Расписание при этом сохраняется.",
        fields=(
            "SUMMARY_ENABLED", "HOROSCOPE_ENABLED", "WORD_STATS_ENABLED", "JOKE_A_ENABLED",
            "JOKE_B_ENABLED", "CONSPIRACY_ENABLED", "AUTO_BULLY_ENABLED", "ALABUGA_ENABLED",
        ),
        toggle_dashboard=True,
    ),
    "features": AdminGroup(
        "🧩 Функции",
        "Настройка поведения, расписания и содержания каждой функции.",
        children=("answer", "summary", "horoscope", "conspiracy", "jokes", "bully", "word_stats", "alabuga"),
    ),
    "integrations": AdminGroup(
        "🔌 Подключения",
        "Состояние Telegram, OpenRouter и пересылки. Секреты в админке не отображаются.",
        fields=("TELEGRAM_USER_API_ID",),
        children=("sources",),
    ),
    "access": AdminGroup(
        "👥 Доступ и чат",
        "Кто управляет ботом и в какой чат отправляются автоматические публикации.",
        fields=("BOT_CHAT_ID", "ADMIN_USER_IDS"),
    ),
    "advanced": AdminGroup(
        "🛠 Расширенные",
        "Редко используемые системные настройки и файловые fallback-промпты.",
        fields=("TIMEZONE", "DATABASE_PATH"),
        children=("fallback_models", "prompt_files"),
    ),
    "answer": AdminGroup(
        "💬 Ответы на вопросы",
        "Модель, поиск в интернете и стиль обычных ответов.",
        fields=("ANSWER_MODEL", "ANSWER_WEB_SEARCH_ENABLED", "ANSWER_SYSTEM_PROMPT_TEXT"),
        children=("answer_generation",),
        parent="features",
    ),
    "summary": AdminGroup(
        "📝 Сводка",
        "Ежедневная сводка по сообщениям чата.",
        fields=("SUMMARY_ENABLED", "DAILY_SUMMARY_TIME", "SUMMARY_EVERY_DAYS", "SUMMARY_CONTEXT_HOURS", "SUMMARY_MODEL", "SUMMARY_PROMPT_TEXT", "SUMMARY_SYSTEM_PROMPT_TEXT"),
        children=("summary_generation",),
        parent="features",
    ),
    "horoscope": AdminGroup(
        "🔮 Гороскоп",
        "Персональный гороскоп для активных участников.",
        fields=("HOROSCOPE_ENABLED", "HOROSCOPE_TIME", "HOROSCOPE_EVERY_DAYS", "HOROSCOPE_CONTEXT_DAYS", "HOROSCOPE_MODEL", "HOROSCOPE_PROMPT_TEXT", "HOROSCOPE_SYSTEM_PROMPT_TEXT"),
        children=("horoscope_generation",),
        parent="features",
    ),
    "conspiracy": AdminGroup(
        "🕵️ Теория заговора",
        "Теория по контексту чата и его участникам.",
        fields=("CONSPIRACY_ENABLED", "CONSPIRACY_TIME", "CONSPIRACY_EVERY_DAYS", "CONSPIRACY_CONTEXT_DAYS", "CONSPIRACY_MODEL", "CONSPIRACY_PROMPT_TEXT", "CONSPIRACY_SYSTEM_PROMPT_TEXT"),
        children=("conspiracy_generation",),
        parent="features",
    ),
    "jokes": AdminGroup(
        "🎭 Анекдоты",
        "Два независимых расписания. Анекдоты берутся с сайтов, LLM не используется.",
        fields=("JOKE_A_ENABLED", "JOKE_A_TIME", "JOKE_A_EVERY_DAYS", "JOKE_B_ENABLED", "JOKE_B_TIME", "JOKE_B_EVERY_DAYS", "JOKE_SOURCE_URLS"),
        parent="features",
    ),
    "bully": AdminGroup(
        "🎯 Буллинг",
        "Статичный текст, цель и частота автоматической отправки.",
        fields=("AUTO_BULLY_ENABLED", "BULLY_TARGET_USERNAME", "BULLY_MESSAGE_TEXT", "BULLY_EVERY_MINUTES", "BULLY_PROBABILITY"),
        parent="features",
    ),
    "word_stats": AdminGroup(
        "📊 Статистика слов",
        "Ежедневный подсчёт заданных слов по участникам.",
        fields=("WORD_STATS_ENABLED", "WORD_STATS_TIME", "TRACKED_WORDS"),
        parent="features",
    ),
    "alabuga": AdminGroup(
        "📡 Алабуга",
        "Автоматическая пересылка публикаций канала.",
        fields=("ALABUGA_ENABLED", "ALABUGA_EVERY_HOURS", "ALABUGA_CHANNEL_URL"),
        parent="features",
    ),
    "telegram": AdminGroup("🤖 Telegram-бот", "Основной токен Telegram Bot API.", fields=("TELEGRAM_BOT_TOKEN",), parent="integrations"),
    "openrouter": AdminGroup("🧠 OpenRouter", "API-ключ для AI-функций.", fields=("OPENROUTER_API_KEY",), parent="integrations"),
    "forwarding": AdminGroup("📨 Telegram-пересылка", "Данные userbot для настоящего forward из каналов.", fields=("TELEGRAM_USER_API_ID", "TELEGRAM_USER_API_HASH", "TELEGRAM_USER_SESSION"), parent="integrations"),
    "sources": AdminGroup("🌐 Внешние источники", "Ссылки на каналы и сайты, откуда бот берёт публикации.", fields=("ALABUGA_CHANNEL_URL", "JOKE_SOURCE_URLS"), parent="integrations"),
    "fallback_models": AdminGroup("🧠 Резервные модели", "Модели, используемые как fallback для сервисов.", fields=("OPENROUTER_DEFAULT_MODEL", "OPENROUTER_QUALITY_MODEL", "OPENROUTER_CHEAP_MODEL"), parent="advanced"),
    "prompt_files": AdminGroup("📁 Файлы промптов", "Используются, только если текст промпта не задан через админку.", fields=("SYSTEM_PROMPT_PATH", "SUMMARY_PROMPT_PATH", "CONSPIRACY_PROMPT_PATH", "HOROSCOPE_PROMPT_PATH"), parent="advanced"),
    "answer_generation": AdminGroup("🎛 Параметры ответов", "Тонкая настройка генерации. Меняй только если понимаешь влияние параметров.", fields=_sampling("ANSWER"), parent="answer"),
    "summary_generation": AdminGroup("🎛 Параметры сводки", "Тонкая настройка генерации сводки.", fields=_sampling("SUMMARY"), parent="summary"),
    "horoscope_generation": AdminGroup("🎛 Параметры гороскопа", "Тонкая настройка генерации гороскопа.", fields=_sampling("HOROSCOPE"), parent="horoscope"),
    "conspiracy_generation": AdminGroup("🎛 Параметры теорий", "Тонкая настройка генерации теорий заговора.", fields=_sampling("CONSPIRACY"), parent="conspiracy"),
}

HOME_GROUPS = ("automations", "features", "integrations", "access", "advanced")

GROUP_AUTOMATIONS: dict[str, tuple[str, ...]] = {
    "summary": ("SUMMARY_ENABLED",),
    "horoscope": ("HOROSCOPE_ENABLED",),
    "conspiracy": ("CONSPIRACY_ENABLED",),
    "jokes": ("JOKE_A_ENABLED", "JOKE_B_ENABLED"),
    "bully": ("AUTO_BULLY_ENABLED",),
    "word_stats": ("WORD_STATS_ENABLED",),
    "alabuga": ("ALABUGA_ENABLED",),
}

AUTOMATION_JOB_IDS = {
    "SUMMARY_ENABLED": "summary",
    "HOROSCOPE_ENABLED": "horoscope",
    "WORD_STATS_ENABLED": "word_stats",
    "JOKE_A_ENABLED": "joke_a",
    "JOKE_B_ENABLED": "joke_b",
    "CONSPIRACY_ENABLED": "conspiracy",
    "AUTO_BULLY_ENABLED": "bully",
    "ALABUGA_ENABLED": "alabuga",
}


def _enabled(settings: Settings | None, key: str) -> bool:
    if settings is not None:
        return bool(getattr(settings, key.lower(), False))
    raw = read_env().get(key, DEFAULTS.get(key, "false"))
    return raw.strip().lower() in {"1", "true", "yes", "y", "on", "да"}


def _runtime_value(settings: Settings | None, attr: str, key: str) -> str:
    if settings is not None and hasattr(settings, attr):
        return str(getattr(settings, attr))
    return DEFAULTS.get(key, "")


def _days_label(value: str, time_value: str) -> str:
    try:
        days = float(value)
    except ValueError:
        days = 1
    if days == 1:
        return f"ежедневно {time_value}"
    return f"раз в {days:g} дн. · {time_value}"


def _local_now(settings: Settings, now: datetime | None = None) -> tuple[datetime, ZoneInfo]:
    timezone = ZoneInfo(settings.timezone)
    if now is None:
        return datetime.now(timezone), timezone
    if now.tzinfo is None:
        return now.replace(tzinfo=timezone), timezone
    return now.astimezone(timezone), timezone


def _next_time_of_day(current: datetime, time_value: str) -> datetime:
    hour, minute = map(int, time_value.split(":", 1))
    candidate = current.replace(hour=hour, minute=minute, second=0, microsecond=0)
    return candidate + timedelta(days=1) if candidate <= current else candidate


def next_publication_at(settings: Settings, key: str, *, now: datetime | None = None) -> datetime | None:
    if not _enabled(settings, key):
        return None
    current, _ = _local_now(settings, now)
    day_jobs = {
        "SUMMARY_ENABLED": (settings.summary_every_days, settings.daily_summary_time),
        "HOROSCOPE_ENABLED": (settings.horoscope_every_days, settings.horoscope_time),
        "JOKE_A_ENABLED": (settings.joke_a_every_days, settings.joke_a_time),
        "JOKE_B_ENABLED": (settings.joke_b_every_days, settings.joke_b_time),
        "CONSPIRACY_ENABLED": (settings.conspiracy_every_days, settings.conspiracy_time),
    }
    if key in day_jobs:
        every_days, time_value = day_jobs[key]
        if every_days <= 0:
            return None
        if every_days > 1:
            hour, minute = map(int, time_value.split(":", 1))
            return (current + timedelta(days=every_days)).replace(
                hour=hour,
                minute=minute,
                second=0,
                microsecond=0,
            )
        return _next_time_of_day(current, time_value)
    if key == "WORD_STATS_ENABLED":
        return _next_time_of_day(current, settings.word_stats_time)
    if key == "AUTO_BULLY_ENABLED" and settings.bully_every_minutes > 0:
        return current + timedelta(minutes=settings.bully_every_minutes)
    if key == "ALABUGA_ENABLED" and settings.alabuga_every_hours > 0:
        return current + timedelta(hours=settings.alabuga_every_hours)
    return None


def _remaining_label(current: datetime, target: datetime) -> str:
    total_minutes = max(0, ceil((target - current).total_seconds() / 60))
    if total_minutes == 0:
        return "меньше минуты"
    days, remainder = divmod(total_minutes, 24 * 60)
    hours, minutes = divmod(remainder, 60)
    parts: list[str] = []
    if days:
        parts.append(f"{days} дн.")
    if hours:
        parts.append(f"{hours} ч")
    if minutes and len(parts) < 2:
        parts.append(f"{minutes} мин")
    return " ".join(parts)


def publication_preview(
    settings: Settings,
    key: str,
    *,
    now: datetime | None = None,
    scheduled_runs: dict[str, datetime] | None = None,
) -> str:
    if not _enabled(settings, key):
        return "приостановлена, расписание сохранено"
    current, _ = _local_now(settings, now)
    if scheduled_runs is None:
        target = next_publication_at(settings, key, now=current)
    else:
        target = scheduled_runs.get(AUTOMATION_JOB_IDS[key])
        if target is not None:
            target = target.astimezone(current.tzinfo)
    if target is None:
        return "не запланирована: интервал равен 0"
    if target.date() == current.date():
        absolute = f"сегодня в {target:%H:%M}"
    elif target.date() == (current + timedelta(days=1)).date():
        absolute = f"завтра в {target:%H:%M}"
    else:
        absolute = target.strftime("%d.%m в %H:%M")
    return f"через {_remaining_label(current, target)} ({absolute})"


def publication_preview_compact(
    settings: Settings,
    key: str,
    scheduled_runs: dict[str, datetime] | None = None,
) -> str:
    if not _enabled(settings, key):
        return "пауза"
    preview = publication_preview(settings, key, scheduled_runs=scheduled_runs)
    if preview.startswith("не запланирована"):
        return "не запланирована"
    return preview.split(" (")[0]


def _automation_for_group(group_key: str) -> tuple[str, ...]:
    current = group_key
    while current in GROUPS:
        if current in GROUP_AUTOMATIONS:
            return GROUP_AUTOMATIONS[current]
        parent = GROUPS[current].parent
        if parent == "home":
            break
        current = parent
    return ()


def automation_detail(settings: Settings | None, key: str) -> str:
    if key == "SUMMARY_ENABLED":
        return _days_label(_runtime_value(settings, "summary_every_days", "SUMMARY_EVERY_DAYS"), _runtime_value(settings, "daily_summary_time", "DAILY_SUMMARY_TIME"))
    if key == "HOROSCOPE_ENABLED":
        return _days_label(_runtime_value(settings, "horoscope_every_days", "HOROSCOPE_EVERY_DAYS"), _runtime_value(settings, "horoscope_time", "HOROSCOPE_TIME"))
    if key == "WORD_STATS_ENABLED":
        return f"ежедневно {_runtime_value(settings, 'word_stats_time', 'WORD_STATS_TIME')}"
    if key == "JOKE_A_ENABLED":
        return _days_label(_runtime_value(settings, "joke_a_every_days", "JOKE_A_EVERY_DAYS"), _runtime_value(settings, "joke_a_time", "JOKE_A_TIME"))
    if key == "JOKE_B_ENABLED":
        return _days_label(_runtime_value(settings, "joke_b_every_days", "JOKE_B_EVERY_DAYS"), _runtime_value(settings, "joke_b_time", "JOKE_B_TIME"))
    if key == "CONSPIRACY_ENABLED":
        return _days_label(_runtime_value(settings, "conspiracy_every_days", "CONSPIRACY_EVERY_DAYS"), _runtime_value(settings, "conspiracy_time", "CONSPIRACY_TIME"))
    if key == "AUTO_BULLY_ENABLED":
        return f"каждые {_runtime_value(settings, 'bully_every_minutes', 'BULLY_EVERY_MINUTES')} мин."
    if key == "ALABUGA_ENABLED":
        return f"каждые {_runtime_value(settings, 'alabuga_every_hours', 'ALABUGA_EVERY_HOURS')} ч."
    return ""


def admin_home_keyboard(settings: Settings | None = None) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=GROUPS["automations"].title, callback_data="admin:g:automations"), InlineKeyboardButton(text=GROUPS["features"].title, callback_data="admin:g:features")],
        [InlineKeyboardButton(text=GROUPS["integrations"].title, callback_data="admin:g:integrations"), InlineKeyboardButton(text=GROUPS["access"].title, callback_data="admin:g:access")],
        [InlineKeyboardButton(text=GROUPS["advanced"].title, callback_data="admin:g:advanced")],
        [InlineKeyboardButton(text="✖ Закрыть", callback_data="admin:close")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_group_keyboard(
    group_key: str,
    settings: Settings | None = None,
    scheduled_runs: dict[str, datetime] | None = None,
) -> InlineKeyboardMarkup:
    group = GROUPS[group_key]
    rows: list[list[InlineKeyboardButton]] = []
    if group.children:
        current: list[InlineKeyboardButton] = []
        for child_key in group.children:
            current.append(InlineKeyboardButton(text=GROUPS[child_key].title, callback_data=f"admin:g:{child_key}"))
            if len(current) == 2:
                rows.append(current)
                current = []
        if current:
            rows.append(current)
    for key in group.fields:
        if key not in FIELDS:
            continue
        if group.toggle_dashboard:
            status = "✅" if _enabled(settings, key) else "⛔"
            detail = automation_detail(settings, key)
            next_run = publication_preview_compact(settings, key, scheduled_runs) if settings is not None else ""
            suffix = f" · {next_run}" if next_run else ""
            rows.append([InlineKeyboardButton(text=f"{status} {FIELDS[key].label} · {detail}{suffix}", callback_data=f"admin:toggle:{key}:{group_key}")])
        else:
            label = FIELDS[key].label
            if key in BOOLEAN_SETTING_KEYS:
                label = f"{'✅' if _enabled(settings, key) else '⛔'} {label}"
            rows.append([InlineKeyboardButton(text=label, callback_data=f"admin:f:{key}:{group_key}")])
    rows.append([
        InlineKeyboardButton(text="← Назад", callback_data=f"admin:g:{group.parent}" if group.parent != "home" else "admin:home"),
        InlineKeyboardButton(text="⌂ Главная", callback_data="admin:home"),
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_field_keyboard(key: str, return_group: str | None = None, settings: Settings | None = None) -> InlineKeyboardMarkup:
    return_group = return_group if return_group in GROUPS else group_for_key(key)
    rows: list[list[InlineKeyboardButton]] = []
    if key in BOOLEAN_SETTING_KEYS:
        action = "Выключить" if _enabled(settings, key) else "Включить"
        rows.append([InlineKeyboardButton(text=f"⏯ {action}", callback_data=f"admin:toggle_field:{key}:{return_group}")])
        rows.append([InlineKeyboardButton(text="↩️ Вернуть стандартное", callback_data=f"admin:clear:{key}:{return_group}")])
    elif FIELDS[key].editable:
        rows.append([InlineKeyboardButton(text="✏️ Изменить", callback_data=f"admin:set:{key}:{return_group}")])
        rows.append([InlineKeyboardButton(text="↩️ Вернуть стандартное", callback_data=f"admin:clear:{key}:{return_group}")])
    rows.append([
        InlineKeyboardButton(text="← Назад", callback_data=f"admin:g:{return_group}"),
        InlineKeyboardButton(text="⌂ Главная", callback_data="admin:home"),
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_clear_keyboard(key: str, return_group: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Да, вернуть стандартное", callback_data=f"admin:cc:{key}:{return_group}")],
        [InlineKeyboardButton(text="Отмена", callback_data=f"admin:f:{key}:{return_group}")],
    ])


def admin_cancel_keyboard(key: str, return_group: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Отмена", callback_data=f"admin:x:{key}:{return_group}")],
    ])


def group_for_key(key: str) -> str:
    for group_key, group in GROUPS.items():
        if key in group.fields and not group.toggle_dashboard:
            return group_key
    return "advanced"


def display_value(key: str, value: str) -> str:
    if not value:
        return "не задано"
    if FIELDS[key].secret:
        return value[:4] + "..." + value[-4:] if len(value) > 8 else "***"
    return value if len(value) <= 700 else value[:697] + "..."


def admin_home_text(settings: Settings | None = None) -> str:
    enabled = sum(_enabled(settings, key) for key in GROUPS["automations"].fields)
    total = len(GROUPS["automations"].fields)
    chat_status = "подключён" if settings and settings.has_bound_chat else "не подключён"
    return (
        "<b>⚙️ Управление ботом</b>\n\n"
        f"💬 Чат: <b>{chat_status}</b>\n"
        f"📅 Автопубликации: <b>{enabled} из {total}</b> включены\n\n"
        "Выбери, что хочешь настроить. Изменения применяются сразу и сохраняются в базе."
    )


def admin_group_text(
    group_key: str,
    settings: Settings | None = None,
    scheduled_runs: dict[str, datetime] | None = None,
) -> str:
    group = GROUPS[group_key]
    if group_key == "integrations":
        if settings is None:
            return f"<b>{html.escape(group.title)}</b>\n\nДанные подключений пока недоступны."
        bot_status = "✅ подключён" if getattr(settings, "telegram_bot_token", "") else "⛔ не настроен"
        router_status = "✅ подключён" if getattr(settings, "openrouter_api_key", "") else "⛔ не настроен"
        forwarding_ready = all((
            getattr(settings, "telegram_user_api_id", None),
            getattr(settings, "telegram_user_api_hash", ""),
            getattr(settings, "telegram_user_session", ""),
        ))
        forwarding_status = "✅ подключена" if forwarding_ready else "⛔ не настроена полностью"
        api_id = getattr(settings, "telegram_user_api_id", None)
        api_id_text = str(api_id) if api_id is not None else "не задан"
        return (
            f"<b>{html.escape(group.title)}</b>\n\n"
            f"🤖 Telegram-бот: <b>{bot_status}</b>\n"
            f"📨 Telegram-пересылка: <b>{forwarding_status}</b>\n"
            f"└ API ID: <code>{html.escape(api_id_text)}</code>\n"
            f"🧠 OpenRouter: <b>{router_status}</b>\n\n"
            "<i>Токены, API hash и StringSession скрыты и изменяются только в переменных окружения.</i>"
        )
    if group_key == "access":
        if settings is None:
            return f"<b>{html.escape(group.title)}</b>\n\nДанные доступа пока недоступны."
        chat_id = getattr(settings, "bot_chat_id", None)
        chat_text = str(chat_id) if chat_id is not None else "не привязан"
        admin_ids = sorted(getattr(settings, "admin_user_ids", set()))
        admins_text = ", ".join(map(str, admin_ids)) if admin_ids else "не заданы"
        return (
            f"<b>{html.escape(group.title)}</b>\n\n"
            f"💬 Привязанный чат: <code>{html.escape(chat_text)}</code>\n"
            f"👥 Администраторы: <code>{html.escape(admins_text)}</code>\n\n"
            "Нажми нужный пункт ниже, чтобы изменить значение."
        )
    preview = ""
    automation_keys = _automation_for_group(group_key)
    if settings is not None and automation_keys:
        lines = [f"{FIELDS[key].label}: <b>{html.escape(publication_preview(settings, key, scheduled_runs=scheduled_runs))}</b>" for key in automation_keys]
        preview = "\n\n<b>Следующая публикация</b>\n" + "\n".join(lines)
    return f"<b>{html.escape(group.title)}</b>\n\n{html.escape(group.description)}{preview}"


def admin_field_text(
    key: str,
    prompt_overrides: dict[str, str] | None = None,
    setting_overrides: dict[str, str] | None = None,
    settings: Settings | None = None,
    scheduled_runs: dict[str, datetime] | None = None,
) -> str:
    env = read_env()
    field = FIELDS[key]
    if key in PROMPT_TEXT_KEYS:
        if key in (prompt_overrides or {}):
            value = (prompt_overrides or {})[key]
            source = "задано через админку"
        else:
            path_key, fallback = PROMPT_FALLBACKS[key]
            path_value = env.get(path_key, DEFAULTS.get(path_key, "")) if path_key else ""
            path = Path(path_value) if path_value else None
            value = path.read_text(encoding="utf-8").strip() if path and path.exists() else fallback.strip()
            source = "файл или встроенное значение"
    elif key in (setting_overrides or {}):
        value = (setting_overrides or {})[key]
        source = "задано через админку"
    else:
        value = env.get(key, DEFAULTS.get(key, DEFAULT_BULLY_MESSAGE_TEXT if key == "BULLY_MESSAGE_TEXT" else ""))
        source = ".env или встроенное значение"
    shown = display_value(key, value)
    status = ""
    if key in BOOLEAN_SETTING_KEYS:
        status = f"\n\n<b>Состояние:</b> {'✅ включено' if shown.lower() in {'true', '1', 'yes', 'on', 'да'} else '⛔ выключено'}"
    edit_hint = "" if not field.editable or key in BOOLEAN_SETTING_KEYS else "\n\nНажми «Изменить» и отправь новое значение."
    schedule_preview = ""
    if settings is not None:
        automation_keys = _automation_for_group(group_for_key(key))
        if automation_keys:
            lines = [f"{FIELDS[automation_key].label}: <b>{html.escape(publication_preview(settings, automation_key, scheduled_runs=scheduled_runs))}</b>" for automation_key in automation_keys]
            schedule_preview = "\n\n<b>Следующая публикация</b>\n" + "\n".join(lines)
    return (
        f"<b>⚙️ {html.escape(field.label)}</b>"
        f"{status}\n\n"
        f"<b>Текущее значение</b>\n<code>{html.escape(shown)}</code>\n\n"
        f"<i>Источник: {html.escape(source)}</i>{schedule_preview}{edit_hint}"
    )


def admin_set_prompt_text(key: str) -> str:
    field = FIELDS[key]
    hints = {
        "ADMIN_USER_IDS": "Telegram ID через запятую, например: <code>123456789, 987654321</code>",
        "BULLY_PROBABILITY": "Число от 0 до 1, например <code>0.25</code>.",
        "BULLY_MESSAGE_TEXT": "Можно использовать <code>{target}</code> и <code>{username}</code>.",
    }
    hint = f"\n\n<b>Подсказка:</b> {hints[key]}" if key in hints else ""
    return (
        f"<b>✏️ {html.escape(field.label)}</b>\n\n"
        "Отправь новое значение следующим сообщением."
        f"{hint}\n\n"
        "Для отмены нажми кнопку ниже или напиши <code>/cancel</code>."
    )
