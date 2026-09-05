from __future__ import annotations

import os
from dataclasses import dataclass, fields
from math import isfinite
from pathlib import Path
from typing import Callable

from dotenv import load_dotenv

from bot.bully import DEFAULT_BULLY_MESSAGE_TEXT
from bot.jokes import DEFAULT_JOKE_SOURCE_URLS

MODEL_SETTING_FIELDS = {
    "ANSWER_MODEL": "answer_model",
    "SUMMARY_MODEL": "summary_model",
    "CONSPIRACY_MODEL": "conspiracy_model",
    "HOROSCOPE_MODEL": "horoscope_model",
}

DECIMAL_DAY_SETTING_KEYS = {
    "HOROSCOPE_EVERY_DAYS",
    "SUMMARY_EVERY_DAYS",
    "JOKE_A_EVERY_DAYS",
    "JOKE_B_EVERY_DAYS",
    "CONSPIRACY_EVERY_DAYS",
}
NONNEGATIVE_INTEGER_SETTING_KEYS = {
    "ALABUGA_EVERY_HOURS",
    "BULLY_EVERY_MINUTES",
}
POSITIVE_INTEGER_SETTING_KEYS = {
    "SUMMARY_CONTEXT_HOURS",
    "HOROSCOPE_CONTEXT_DAYS",
    "CONSPIRACY_CONTEXT_DAYS",
}
TIME_SETTING_KEYS = {
    "HOROSCOPE_TIME",
    "DAILY_SUMMARY_TIME",
    "WORD_STATS_TIME",
    "JOKE_A_TIME",
    "JOKE_B_TIME",
    "CONSPIRACY_TIME",
}
BOOLEAN_SETTING_KEYS = {
    "ANSWER_WEB_SEARCH_ENABLED",
    "HOROSCOPE_ENABLED",
    "SUMMARY_ENABLED",
    "WORD_STATS_ENABLED",
    "JOKE_A_ENABLED",
    "JOKE_B_ENABLED",
    "CONSPIRACY_ENABLED",
    "AUTO_BULLY_ENABLED",
    "ALABUGA_ENABLED",
}


def _csv(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip().lstrip("@") for item in value.split(",") if item.strip()]


def _ints(value: str | None) -> set[int]:
    result: set[int] = set()
    for item in _csv(value):
        try:
            result.add(int(item))
        except ValueError:
            continue
    return result


@dataclass(frozen=True)
class GenerationParams:
    temperature: float
    top_p: float | None
    top_k: int | None
    presence_penalty: float | None
    frequency_penalty: float | None
    repetition_penalty: float | None
    min_p: float | None
    top_a: float | None
    max_tokens: int


@dataclass
class Settings:
    telegram_bot_token: str
    openrouter_api_key: str
    openrouter_default_model: str
    openrouter_quality_model: str
    openrouter_cheap_model: str
    answer_model: str
    summary_model: str
    conspiracy_model: str
    horoscope_model: str
    answer_web_search_enabled: bool
    horoscope_enabled: bool
    summary_enabled: bool
    word_stats_enabled: bool
    joke_a_enabled: bool
    joke_b_enabled: bool
    conspiracy_enabled: bool
    auto_bully_enabled: bool
    alabuga_enabled: bool
    bot_chat_id: int | None
    admin_user_ids: set[int]
    bully_target_username: str | None
    timezone: str
    database_path: Path
    joke_source_urls: list[str]
    alabuga_channel_url: str
    horoscope_time: str
    horoscope_every_days: float
    daily_summary_time: str
    summary_every_days: float
    word_stats_time: str
    joke_a_time: str
    joke_a_every_days: float
    joke_b_time: str
    joke_b_every_days: float
    conspiracy_time: str
    alabuga_every_hours: int
    summary_context_hours: int
    horoscope_context_days: int
    conspiracy_context_days: int
    tracked_words: list[str]
    bully_every_minutes: int
    bully_probability: float
    bully_message_text: str
    conspiracy_every_days: float
    answer_params: GenerationParams
    summary_params: GenerationParams
    conspiracy_params: GenerationParams
    horoscope_params: GenerationParams
    system_prompt_path: Path | None
    horoscope_prompt_path: Path | None
    summary_prompt_path: Path | None
    conspiracy_prompt_path: Path | None

    @property
    def has_bound_chat(self) -> bool:
        return self.bot_chat_id is not None


def _optional_int(value: str | None) -> int | None:
    if not value:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def _optional_path(value: str | None) -> Path | None:
    if not value or not value.strip():
        return None
    return Path(value.strip())


def _model_value(value: str | None, fallback: str) -> str:
    return value.strip() if value and value.strip() else fallback


def _storage_path(
    get: Callable[[str, str], str],
    key: str,
    local_default: str,
    volume_child: str,
) -> Path:
    configured = get(key, "").strip()
    if configured:
        return Path(configured)

    railway_volume = get("RAILWAY_VOLUME_MOUNT_PATH", "").strip()
    if railway_volume:
        return Path(railway_volume) / volume_child

    return Path(local_default)


def _optional_float(value: str | None) -> float | None:
    if value is None or not value.strip():
        return None
    try:
        parsed = float(value)
    except ValueError:
        return None
    return parsed if isfinite(parsed) else None


def _optional_int_value(value: str | None) -> int | None:
    if value is None or not value.strip():
        return None
    try:
        return int(value)
    except ValueError:
        return None


def _int_value(value: str | None, default: int) -> int:
    parsed = _optional_int_value(value)
    return parsed if parsed is not None else default


def _float_value(value: str | None, default: float) -> float:
    parsed = _optional_float(value)
    return parsed if parsed is not None else default


def _bool_value(value: str | None, default: bool = False) -> bool:
    if value is None or not value.strip():
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on", "да"}


def validate_setting_override(key: str, value: str) -> None:
    if key == "BULLY_PROBABILITY":
        number = float(value)
        if not isfinite(number) or not 0 <= number <= 1:
            raise ValueError("Вероятность должна быть числом от 0 до 1.")
    elif key in DECIMAL_DAY_SETTING_KEYS:
        number = float(value)
        if not isfinite(number) or number < 0:
            raise ValueError("Значение должно быть числом не меньше 0. Дробные дни разрешены: 0.5 = 12 часов.")
    elif key in NONNEGATIVE_INTEGER_SETTING_KEYS:
        if int(value) < 0:
            raise ValueError("Значение должно быть целым числом не меньше 0.")
    elif key in POSITIVE_INTEGER_SETTING_KEYS:
        if int(value) <= 0:
            raise ValueError("Значение должно быть целым числом больше 0.")
    elif key in TIME_SETTING_KEYS:
        parts = value.split(":")
        if len(parts) != 2 or not all(part.isdigit() for part in parts):
            raise ValueError("Время должно быть в формате HH:MM, например 18:30.")
        hour, minute = map(int, parts)
        if not 0 <= hour <= 23 or not 0 <= minute <= 59:
            raise ValueError("Время должно быть в диапазоне 00:00–23:59.")
    elif key in BOOLEAN_SETTING_KEYS:
        if value.strip().lower() not in {"1", "0", "true", "false", "yes", "no", "y", "n", "on", "off", "да", "нет"}:
            raise ValueError("Значение должно быть boolean: true/false, yes/no или 1/0.")


def _time_value(value: str | None, default: str) -> str:
    candidate = value.strip() if value else default
    try:
        validate_setting_override("HOROSCOPE_TIME", candidate)
    except ValueError:
        return default
    return candidate


def _generation_params(
    prefix: str,
    default_temperature: float,
    get: Callable[[str, str], str],
    default_max_tokens: int = 900,
    defaults: dict[str, str] | None = None,
) -> GenerationParams:
    defaults = defaults or {}
    return GenerationParams(
        temperature=_float_value(get(f"{prefix}_TEMPERATURE", str(default_temperature)), default_temperature),
        top_p=_optional_float(get(f"{prefix}_TOP_P", defaults.get("TOP_P", ""))),
        top_k=_optional_int_value(get(f"{prefix}_TOP_K", defaults.get("TOP_K", ""))),
        presence_penalty=_optional_float(
            get(f"{prefix}_PRESENCE_PENALTY", defaults.get("PRESENCE_PENALTY", ""))
        ),
        frequency_penalty=_optional_float(
            get(f"{prefix}_FREQUENCY_PENALTY", defaults.get("FREQUENCY_PENALTY", ""))
        ),
        repetition_penalty=_optional_float(
            get(f"{prefix}_REPETITION_PENALTY", defaults.get("REPETITION_PENALTY", ""))
        ),
        min_p=_optional_float(get(f"{prefix}_MIN_P", defaults.get("MIN_P", ""))),
        top_a=_optional_float(get(f"{prefix}_TOP_A", defaults.get("TOP_A", ""))),
        max_tokens=_int_value(get(f"{prefix}_MAX_TOKENS", str(default_max_tokens)), default_max_tokens),
    )


def load_settings(overrides: dict[str, str] | None = None, *, require_secrets: bool = True) -> Settings:
    load_dotenv()
    overrides = overrides or {}

    def get(key: str, default: str = "") -> str:
        if key in overrides:
            return overrides[key]
        return os.getenv(key, default)

    token = get("TELEGRAM_BOT_TOKEN", "").strip()
    openrouter_key = get("OPENROUTER_API_KEY", "").strip()
    if require_secrets and not token:
        raise RuntimeError(
            "TELEGRAM_BOT_TOKEN is missing. Configure it in .env or Railway service Variables."
        )
    if require_secrets and not openrouter_key:
        raise RuntimeError(
            "OPENROUTER_API_KEY is missing. Configure it in .env or Railway service Variables."
        )

    default_model = get("OPENROUTER_DEFAULT_MODEL", "cognitivecomputations/dolphin-mistral-24b-venice-edition")
    quality_model = get("OPENROUTER_QUALITY_MODEL", "deepseek/deepseek-chat")
    cheap_model = get("OPENROUTER_CHEAP_MODEL", "openai/gpt-4.1-nano")
    answer_model = _model_value(get("ANSWER_MODEL", ""), default_model)
    summary_model = _model_value(get("SUMMARY_MODEL", ""), quality_model)
    conspiracy_model = _model_value(get("CONSPIRACY_MODEL", ""), quality_model)
    horoscope_model = _model_value(get("HOROSCOPE_MODEL", ""), summary_model)

    return Settings(
        telegram_bot_token=token,
        openrouter_api_key=openrouter_key,
        openrouter_default_model=default_model,
        openrouter_quality_model=quality_model,
        openrouter_cheap_model=cheap_model,
        answer_model=answer_model,
        summary_model=summary_model,
        conspiracy_model=conspiracy_model,
        horoscope_model=horoscope_model,
        answer_web_search_enabled=_bool_value(get("ANSWER_WEB_SEARCH_ENABLED", "true"), True),
        horoscope_enabled=_bool_value(get("HOROSCOPE_ENABLED", "true"), True),
        summary_enabled=_bool_value(get("SUMMARY_ENABLED", "true"), True),
        word_stats_enabled=_bool_value(get("WORD_STATS_ENABLED", "true"), True),
        joke_a_enabled=_bool_value(get("JOKE_A_ENABLED", "true"), True),
        joke_b_enabled=_bool_value(get("JOKE_B_ENABLED", "true"), True),
        conspiracy_enabled=_bool_value(get("CONSPIRACY_ENABLED", "true"), True),
        auto_bully_enabled=_bool_value(get("AUTO_BULLY_ENABLED", "true"), True),
        alabuga_enabled=_bool_value(get("ALABUGA_ENABLED", "true"), True),
        bot_chat_id=_optional_int(get("BOT_CHAT_ID", "")),
        admin_user_ids=_ints(get("ADMIN_USER_IDS", "")),
        bully_target_username=(get("BULLY_TARGET_USERNAME", get("TARGET_USERNAME", "")) or "").strip().lstrip("@") or None,
        timezone=get("TIMEZONE", "Europe/Warsaw"),
        database_path=_storage_path(get, "DATABASE_PATH", "data/bot.sqlite3", "bot.sqlite3"),
        joke_source_urls=_csv(get("JOKE_SOURCE_URLS", ",".join(DEFAULT_JOKE_SOURCE_URLS))),
        alabuga_channel_url=get("ALABUGA_CHANNEL_URL", "https://t.me/s/alabugapolytech"),
        horoscope_time=_time_value(get("HOROSCOPE_TIME", "09:30"), "09:30"),
        horoscope_every_days=_float_value(get("HOROSCOPE_EVERY_DAYS", "1"), 1.0),
        daily_summary_time=_time_value(get("DAILY_SUMMARY_TIME", "23:30"), "23:30"),
        summary_every_days=_float_value(get("SUMMARY_EVERY_DAYS", "1"), 1.0),
        word_stats_time=_time_value(get("WORD_STATS_TIME", get("DAILY_SUMMARY_TIME", "23:30")), "23:30"),
        joke_a_time=_time_value(get("JOKE_A_TIME", get("JOKE_TIME", "12:00")), "12:00"),
        joke_a_every_days=_float_value(get("JOKE_A_EVERY_DAYS", get("JOKE_EVERY_DAYS", "1")), 1.0),
        joke_b_time=_time_value(get("JOKE_B_TIME", "18:00"), "18:00"),
        joke_b_every_days=_float_value(get("JOKE_B_EVERY_DAYS", get("JOKE_EVERY_DAYS", "1")), 1.0),
        conspiracy_time=_time_value(get("CONSPIRACY_TIME", "20:00"), "20:00"),
        alabuga_every_hours=_int_value(get("ALABUGA_EVERY_HOURS", "4"), 4),
        summary_context_hours=_int_value(get("SUMMARY_CONTEXT_HOURS", "24"), 24),
        horoscope_context_days=_int_value(get("HOROSCOPE_CONTEXT_DAYS", "7"), 7),
        conspiracy_context_days=_int_value(get("CONSPIRACY_CONTEXT_DAYS", "3"), 3),
        tracked_words=_csv(get("TRACKED_WORDS", "")),
        bully_every_minutes=_int_value(get("BULLY_EVERY_MINUTES", get("ROAST_EVERY_MINUTES", "240")), 240),
        bully_probability=_float_value(get("BULLY_PROBABILITY", get("ROAST_PROBABILITY", "0.25")), 0.25),
        bully_message_text=get("BULLY_MESSAGE_TEXT", DEFAULT_BULLY_MESSAGE_TEXT).strip(),
        conspiracy_every_days=_float_value(get("CONSPIRACY_EVERY_DAYS", "3"), 3.0),
        answer_params=_generation_params("ANSWER", 0.7, get, 1800),
        summary_params=_generation_params("SUMMARY", 0.5, get),
        conspiracy_params=_generation_params(
            "CONSPIRACY",
            0.85,
            get,
            defaults={
                "TOP_P": "0.95",
                "PRESENCE_PENALTY": "0",
                "FREQUENCY_PENALTY": "0.05",
            },
        ),
        horoscope_params=_generation_params("HOROSCOPE", 1.0, get),
        system_prompt_path=_optional_path(get("SYSTEM_PROMPT_PATH", "prompts/system.txt")),
        horoscope_prompt_path=_optional_path(get("HOROSCOPE_PROMPT_PATH", "prompts/horoscope.txt")),
        summary_prompt_path=_optional_path(get("SUMMARY_PROMPT_PATH", "prompts/summary.txt")),
        conspiracy_prompt_path=_optional_path(get("CONSPIRACY_PROMPT_PATH", "prompts/conspiracy.txt")),
    )


def apply_settings(target: Settings, source: Settings) -> None:
    for field in fields(Settings):
        setattr(target, field.name, getattr(source, field.name))


def effective_model_settings(settings: Settings) -> dict[str, str]:
    return {key: getattr(settings, field_name) for key, field_name in MODEL_SETTING_FIELDS.items()}
