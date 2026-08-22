from __future__ import annotations

from dataclasses import dataclass, fields
from pathlib import Path

from bot import prompts as defaults
from bot.config import Settings

PROMPT_OVERRIDE_KEYS = {
    "SYSTEM_PROMPT_TEXT": "system_base",
    "HOROSCOPE_PROMPT_TEXT": "horoscope",
    "JOKE_PROMPT_TEXT": "joke",
    "SUMMARY_PROMPT_TEXT": "summary",
    "CONSPIRACY_PROMPT_TEXT": "conspiracy",
    "ROAST_PROMPT_TEXT": "roast",
}


@dataclass
class PromptSet:
    system_base: str
    horoscope: str
    joke: str
    summary: str
    conspiracy: str
    roast: str


def _read_prompt(path: Path | None, fallback: str, override: str | None = None) -> str:
    if override is not None:
        return override.strip()
    if path and path.exists():
        return path.read_text(encoding="utf-8").strip()
    return fallback.strip()


def load_prompts(settings: Settings, overrides: dict[str, str] | None = None) -> PromptSet:
    overrides = overrides or {}
    return PromptSet(
        system_base=_read_prompt(settings.system_prompt_path, defaults.SYSTEM_BASE, overrides.get("SYSTEM_PROMPT_TEXT")),
        horoscope=_read_prompt(settings.horoscope_prompt_path, defaults.HOROSCOPE_PROMPT, overrides.get("HOROSCOPE_PROMPT_TEXT")),
        joke=_read_prompt(settings.joke_prompt_path, defaults.JOKE_PROMPT, overrides.get("JOKE_PROMPT_TEXT")),
        summary=_read_prompt(settings.summary_prompt_path, defaults.SUMMARY_PROMPT, overrides.get("SUMMARY_PROMPT_TEXT")),
        conspiracy=_read_prompt(settings.conspiracy_prompt_path, defaults.CONSPIRACY_PROMPT, overrides.get("CONSPIRACY_PROMPT_TEXT")),
        roast=_read_prompt(settings.roast_prompt_path, defaults.ROAST_PROMPT, overrides.get("ROAST_PROMPT_TEXT")),
    )


def apply_prompts(target: PromptSet, source: PromptSet) -> None:
    for field in fields(PromptSet):
        setattr(target, field.name, getattr(source, field.name))
