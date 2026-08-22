from __future__ import annotations

import os
from dataclasses import dataclass, fields
from pathlib import Path
from typing import Callable

from dotenv import load_dotenv

MODEL_SETTING_FIELDS = {
    "ANSWER_MODEL": "answer_model",
    "SUMMARY_MODEL": "summary_model",
    "CONSPIRACY_MODEL": "conspiracy_model",
    "HOROSCOPE_MODEL": "horoscope_model",
    "JOKE_MODEL": "joke_model",
    "ROAST_MODEL": "roast_model",
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
    joke_model: str
    roast_model: str
    bot_chat_id: int | None
    admin_user_ids: set[int]
    target_username: str | None
    timezone: str
    database_path: Path
    local_image_dir: Path
    image_source_channels: list[str]
    alabuga_channel_url: str
    alabuga_jobs_url: str | None
    horoscope_time: str
    daily_summary_time: str
    word_stats_time: str
    joke_time: str
    tracked_words: list[str]
    random_image_every_minutes: int
    random_image_probability: float
    roast_every_minutes: int
    roast_probability: float
    conspiracy_every_days: int
    answer_params: GenerationParams
    summary_params: GenerationParams
    conspiracy_params: GenerationParams
    horoscope_params: GenerationParams
    joke_params: GenerationParams
    roast_params: GenerationParams
    system_prompt_path: Path | None
    horoscope_prompt_path: Path | None
    joke_prompt_path: Path | None
    summary_prompt_path: Path | None
    conspiracy_prompt_path: Path | None
    roast_prompt_path: Path | None

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
    return float(value)


def _optional_int_value(value: str | None) -> int | None:
    if value is None or not value.strip():
        return None
    return int(value)


def _generation_params(
    prefix: str,
    default_temperature: float,
    get: Callable[[str, str], str],
    default_max_tokens: int = 900,
) -> GenerationParams:
    return GenerationParams(
        temperature=float(get(f"{prefix}_TEMPERATURE", str(default_temperature))),
        top_p=_optional_float(get(f"{prefix}_TOP_P", "")),
        top_k=_optional_int_value(get(f"{prefix}_TOP_K", "")),
        presence_penalty=_optional_float(get(f"{prefix}_PRESENCE_PENALTY", "")),
        frequency_penalty=_optional_float(get(f"{prefix}_FREQUENCY_PENALTY", "")),
        repetition_penalty=_optional_float(get(f"{prefix}_REPETITION_PENALTY", "")),
        min_p=_optional_float(get(f"{prefix}_MIN_P", "")),
        top_a=_optional_float(get(f"{prefix}_TOP_A", "")),
        max_tokens=int(get(f"{prefix}_MAX_TOKENS", str(default_max_tokens))),
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
    joke_model = _model_value(get("JOKE_MODEL", ""), cheap_model)
    roast_model = _model_value(get("ROAST_MODEL", ""), default_model)

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
        joke_model=joke_model,
        roast_model=roast_model,
        bot_chat_id=_optional_int(get("BOT_CHAT_ID", "")),
        admin_user_ids=_ints(get("ADMIN_USER_IDS", "")),
        target_username=(get("TARGET_USERNAME", "") or "").strip().lstrip("@") or None,
        timezone=get("TIMEZONE", "Europe/Warsaw"),
        database_path=_storage_path(get, "DATABASE_PATH", "data/bot.sqlite3", "bot.sqlite3"),
        local_image_dir=_storage_path(get, "LOCAL_IMAGE_DIR", "data/images", "images"),
        image_source_channels=_csv(get("IMAGE_SOURCE_CHANNELS", "")),
        alabuga_channel_url=get("ALABUGA_CHANNEL_URL", "https://t.me/s/alabugapolytech"),
        alabuga_jobs_url=(get("ALABUGA_JOBS_URL", "") or "").strip() or None,
        horoscope_time=get("HOROSCOPE_TIME", "09:30"),
        daily_summary_time=get("DAILY_SUMMARY_TIME", "23:30"),
        word_stats_time=get("WORD_STATS_TIME", get("DAILY_SUMMARY_TIME", "23:30")),
        joke_time=get("JOKE_TIME", "18:00"),
        tracked_words=_csv(get("TRACKED_WORDS", "")),
        random_image_every_minutes=int(get("RANDOM_IMAGE_EVERY_MINUTES", "180")),
        random_image_probability=float(get("RANDOM_IMAGE_PROBABILITY", "0.35")),
        roast_every_minutes=int(get("ROAST_EVERY_MINUTES", "240")),
        roast_probability=float(get("ROAST_PROBABILITY", "0.25")),
        conspiracy_every_days=int(get("CONSPIRACY_EVERY_DAYS", "3")),
        answer_params=_generation_params("ANSWER", 0.7, get, 1800),
        summary_params=_generation_params("SUMMARY", 0.5, get),
        conspiracy_params=_generation_params("CONSPIRACY", 1.05, get),
        horoscope_params=_generation_params("HOROSCOPE", 1.0, get),
        joke_params=_generation_params("JOKE", 1.0, get),
        roast_params=_generation_params("ROAST", 1.0, get),
        system_prompt_path=_optional_path(get("SYSTEM_PROMPT_PATH", "prompts/system.txt")),
        horoscope_prompt_path=_optional_path(get("HOROSCOPE_PROMPT_PATH", "prompts/horoscope.txt")),
        joke_prompt_path=_optional_path(get("JOKE_PROMPT_PATH", "prompts/joke.txt")),
        summary_prompt_path=_optional_path(get("SUMMARY_PROMPT_PATH", "prompts/summary.txt")),
        conspiracy_prompt_path=_optional_path(get("CONSPIRACY_PROMPT_PATH", "prompts/conspiracy.txt")),
        roast_prompt_path=_optional_path(get("ROAST_PROMPT_PATH", "prompts/roast.txt")),
    )


def apply_settings(target: Settings, source: Settings) -> None:
    for field in fields(Settings):
        setattr(target, field.name, getattr(source, field.name))


def effective_model_settings(settings: Settings) -> dict[str, str]:
    return {key: getattr(settings, field_name) for key, field_name in MODEL_SETTING_FIELDS.items()}
