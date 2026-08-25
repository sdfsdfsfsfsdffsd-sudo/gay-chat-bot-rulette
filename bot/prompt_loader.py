from __future__ import annotations

from dataclasses import dataclass, fields
from pathlib import Path

from bot import prompts as defaults
from bot.config import Settings

PROMPT_OVERRIDE_KEYS = {
    "ANSWER_SYSTEM_PROMPT_TEXT": "answer_system",
    "SUMMARY_SYSTEM_PROMPT_TEXT": "summary_system",
    "CONSPIRACY_SYSTEM_PROMPT_TEXT": "conspiracy_system",
    "HOROSCOPE_SYSTEM_PROMPT_TEXT": "horoscope_system",
    "HOROSCOPE_PROMPT_TEXT": "horoscope",
    "SUMMARY_PROMPT_TEXT": "summary",
    "CONSPIRACY_PROMPT_TEXT": "conspiracy",
}


@dataclass
class PromptSet:
    answer_system: str
    summary_system: str
    conspiracy_system: str
    horoscope_system: str
    horoscope: str
    summary: str
    conspiracy: str


def _read_prompt(path: Path | None, fallback: str, override: str | None = None) -> str:
    if override is not None:
        return override.strip()
    if path and path.exists():
        return path.read_text(encoding="utf-8").strip()
    return fallback.strip()


def load_prompts(settings: Settings, overrides: dict[str, str] | None = None) -> PromptSet:
    overrides = overrides or {}
    base_system = _read_prompt(settings.system_prompt_path, defaults.SYSTEM_BASE)
    return PromptSet(
        answer_system=_read_prompt(None, defaults.ANSWER_SYSTEM_PROMPT, overrides.get("ANSWER_SYSTEM_PROMPT_TEXT")),
        summary_system=_read_prompt(None, base_system, overrides.get("SUMMARY_SYSTEM_PROMPT_TEXT")),
        conspiracy_system=_read_prompt(None, "", overrides.get("CONSPIRACY_SYSTEM_PROMPT_TEXT")),
        horoscope_system=_read_prompt(None, "", overrides.get("HOROSCOPE_SYSTEM_PROMPT_TEXT")),
        horoscope=_read_prompt(settings.horoscope_prompt_path, defaults.HOROSCOPE_PROMPT, overrides.get("HOROSCOPE_PROMPT_TEXT")),
        summary=_read_prompt(settings.summary_prompt_path, defaults.SUMMARY_PROMPT, overrides.get("SUMMARY_PROMPT_TEXT")),
        conspiracy=_read_prompt(settings.conspiracy_prompt_path, defaults.CONSPIRACY_PROMPT, overrides.get("CONSPIRACY_PROMPT_TEXT")),
    )


def apply_prompts(target: PromptSet, source: PromptSet) -> None:
    for field in fields(PromptSet):
        setattr(target, field.name, getattr(source, field.name))
