from __future__ import annotations

import os
import subprocess
from pathlib import Path

from bot import prompts as default_prompts
from bot.env_file import ENV_PATH, read_env


QUESTIONS = [
    ("TELEGRAM_BOT_TOKEN", "Telegram bot token", True),
    ("OPENROUTER_API_KEY", "OpenRouter API key", True),
    ("BOT_CHAT_ID", "Target Telegram chat id, optional if you will use /bind_chat", False),
    ("ADMIN_USER_IDS", "Admin Telegram user ids, comma-separated", False),
    ("TELEGRAM_USER_API_ID", "Telegram user API ID for userbot forwarding, optional", False),
    ("TELEGRAM_USER_API_HASH", "Telegram user API hash for userbot forwarding, optional", True),
    ("TELEGRAM_USER_SESSION", "Telegram user StringSession for userbot forwarding, optional", True),
    ("TARGET_USERNAME", "Username for playful roast mode, without @", False),
    ("BULLY_TARGET_USERNAME", "Default username for /bully and auto bully, without @", False),
    ("ANSWER_MODEL", "Answer model id", False),
    ("SUMMARY_MODEL", "Summary model id", False),
    ("CONSPIRACY_MODEL", "Conspiracy model id", False),
    ("HOROSCOPE_MODEL", "Horoscope model id", False),
    ("JOKE_MODEL", "Joke model id", False),
    ("ROAST_MODEL", "Roast model id", False),
    ("IMAGE_SOURCE_CHANNELS", "Image source public channels or t.me/s URLs, comma-separated", False),
    ("ALABUGA_CHANNEL_URL", "Alabuga Polytech public channel URL", False),
    ("ALABUGA_JOBS_URL", "Alabuga jobs URL/source, optional", False),
    ("HOROSCOPE_TIME", "Daily horoscope time HH:MM", False),
    ("HOROSCOPE_EVERY_DAYS", "Horoscope every N days; decimals allowed; 0 disables", False),
    ("DAILY_SUMMARY_TIME", "Daily summary time HH:MM", False),
    ("SUMMARY_EVERY_DAYS", "Summary every N days; decimals allowed; 0 disables", False),
    ("WORD_STATS_TIME", "Daily tracked word stats time HH:MM", False),
    ("TRACKED_WORDS", "Tracked words for daily stats, comma-separated", False),
    ("JOKE_TIME", "Joke time HH:MM", False),
    ("JOKE_EVERY_DAYS", "Joke every N days; decimals allowed; 0 disables", False),
    ("JOKE_A_TIME", "Joke A time HH:MM", False),
    ("JOKE_A_EVERY_DAYS", "Joke A every N days; decimals allowed; 0 disables", False),
    ("JOKE_B_TIME", "Joke B time HH:MM", False),
    ("JOKE_B_EVERY_DAYS", "Joke B every N days; decimals allowed; 0 disables", False),
    ("CONSPIRACY_TIME", "Conspiracy time HH:MM", False),
    ("CONSPIRACY_EVERY_DAYS", "Conspiracy every N days; decimals allowed; 0 disables", False),
    ("ALABUGA_EVERY_HOURS", "Alabuga news every N hours; 0 disables", False),
    ("SUMMARY_CONTEXT_HOURS", "Summary context window in hours", False),
    ("HOROSCOPE_CONTEXT_DAYS", "Horoscope context window in days", False),
    ("CONSPIRACY_CONTEXT_DAYS", "Conspiracy context window in days", False),
    ("ROAST_CONTEXT_DAYS", "Roast context window in days", False),
    ("BULLY_MESSAGE_TEXT", "Static bully message text; supports {target} and {username}", False),
    ("ANSWER_TEMPERATURE", "Answer temperature", False),
    ("ANSWER_TOP_P", "Answer top_p, optional", False),
    ("ANSWER_TOP_K", "Answer top_k, optional", False),
    ("ANSWER_PRESENCE_PENALTY", "Answer presence penalty, optional", False),
    ("ANSWER_FREQUENCY_PENALTY", "Answer frequency penalty, optional", False),
    ("ANSWER_REPETITION_PENALTY", "Answer repetition penalty, optional", False),
    ("ANSWER_MIN_P", "Answer min_p, optional", False),
    ("ANSWER_TOP_A", "Answer top_a, optional", False),
    ("ANSWER_MAX_TOKENS", "Answer max tokens", False),
    ("SUMMARY_TEMPERATURE", "Summary temperature", False),
    ("SUMMARY_TOP_P", "Summary top_p, optional", False),
    ("SUMMARY_PRESENCE_PENALTY", "Summary presence penalty, optional", False),
    ("SUMMARY_FREQUENCY_PENALTY", "Summary frequency penalty, optional", False),
    ("CONSPIRACY_TEMPERATURE", "Conspiracy temperature", False),
    ("CONSPIRACY_TOP_P", "Conspiracy top_p", False),
    ("CONSPIRACY_PRESENCE_PENALTY", "Conspiracy presence penalty", False),
    ("CONSPIRACY_FREQUENCY_PENALTY", "Conspiracy frequency penalty", False),
    ("HOROSCOPE_TEMPERATURE", "Horoscope temperature", False),
    ("HOROSCOPE_TOP_P", "Horoscope top_p, optional", False),
    ("HOROSCOPE_PRESENCE_PENALTY", "Horoscope presence penalty, optional", False),
    ("HOROSCOPE_FREQUENCY_PENALTY", "Horoscope frequency penalty, optional", False),
    ("JOKE_TEMPERATURE", "Joke temperature", False),
    ("JOKE_TOP_P", "Joke top_p, optional", False),
    ("JOKE_PRESENCE_PENALTY", "Joke presence penalty, optional", False),
    ("JOKE_FREQUENCY_PENALTY", "Joke frequency penalty, optional", False),
    ("ROAST_TEMPERATURE", "Roast temperature", False),
    ("ROAST_TOP_P", "Roast top_p, optional", False),
    ("ROAST_PRESENCE_PENALTY", "Roast presence penalty, optional", False),
    ("ROAST_FREQUENCY_PENALTY", "Roast frequency penalty, optional", False),
    ("SYSTEM_PROMPT_PATH", "System prompt file path", False),
    ("SUMMARY_PROMPT_PATH", "Summary prompt file path", False),
    ("CONSPIRACY_PROMPT_PATH", "Conspiracy prompt file path", False),
    ("HOROSCOPE_PROMPT_PATH", "Horoscope prompt file path", False),
    ("JOKE_PROMPT_PATH", "Joke prompt file path", False),
    ("JOKE_A_PROMPT_PATH", "Joke A prompt file path", False),
    ("JOKE_B_PROMPT_PATH", "Joke B prompt file path", False),
    ("ROAST_PROMPT_PATH", "Roast prompt file path", False),
    ("TIMEZONE", "Timezone", False),
]


DEFAULTS = {
    "OPENROUTER_DEFAULT_MODEL": "cognitivecomputations/dolphin-mistral-24b-venice-edition",
    "OPENROUTER_QUALITY_MODEL": "deepseek/deepseek-chat",
    "OPENROUTER_CHEAP_MODEL": "openai/gpt-4.1-nano",
    "TELEGRAM_USER_API_ID": "",
    "TELEGRAM_USER_API_HASH": "",
    "TELEGRAM_USER_SESSION": "",
    "ANSWER_MODEL": "cognitivecomputations/dolphin-mistral-24b-venice-edition",
    "SUMMARY_MODEL": "deepseek/deepseek-chat",
    "CONSPIRACY_MODEL": "deepseek/deepseek-chat",
    "HOROSCOPE_MODEL": "",
    "JOKE_MODEL": "cognitivecomputations/dolphin-mistral-24b-venice-edition",
    "ROAST_MODEL": "cognitivecomputations/dolphin-mistral-24b-venice-edition",
    "BULLY_TARGET_USERNAME": "",
    "DATABASE_PATH": "data/bot.sqlite3",
    "LOCAL_IMAGE_DIR": "data/images",
    "ALABUGA_CHANNEL_URL": "https://t.me/s/alabugapolytech",
    "HOROSCOPE_TIME": "09:30",
    "HOROSCOPE_EVERY_DAYS": "1",
    "DAILY_SUMMARY_TIME": "23:30",
    "SUMMARY_EVERY_DAYS": "1",
    "WORD_STATS_TIME": "23:35",
    "JOKE_TIME": "18:00",
    "JOKE_EVERY_DAYS": "1",
    "JOKE_A_TIME": "12:00",
    "JOKE_A_EVERY_DAYS": "1",
    "JOKE_B_TIME": "18:00",
    "JOKE_B_EVERY_DAYS": "1",
    "CONSPIRACY_TIME": "20:00",
    "ALABUGA_EVERY_HOURS": "4",
    "SUMMARY_CONTEXT_HOURS": "24",
    "HOROSCOPE_CONTEXT_DAYS": "7",
    "CONSPIRACY_CONTEXT_DAYS": "3",
    "ROAST_CONTEXT_DAYS": "3",
    "TRACKED_WORDS": "",
    "TIMEZONE": "Europe/Warsaw",
    "RANDOM_IMAGE_EVERY_MINUTES": "180",
    "RANDOM_IMAGE_PROBABILITY": "0.35",
    "ROAST_EVERY_MINUTES": "240",
    "ROAST_PROBABILITY": "0.25",
    "BULLY_MESSAGE_TEXT": "{target}, today the bot has selected you for ceremonial group bullying.",
    "CONSPIRACY_EVERY_DAYS": "3",
    "ANSWER_TEMPERATURE": "0.7",
    "ANSWER_TOP_P": "0.9",
    "ANSWER_TOP_K": "",
    "ANSWER_PRESENCE_PENALTY": "",
    "ANSWER_FREQUENCY_PENALTY": "",
    "ANSWER_REPETITION_PENALTY": "",
    "ANSWER_MIN_P": "",
    "ANSWER_TOP_A": "",
    "ANSWER_MAX_TOKENS": "1800",
    "SUMMARY_TEMPERATURE": "0.5",
    "SUMMARY_TOP_P": "",
    "SUMMARY_PRESENCE_PENALTY": "",
    "SUMMARY_FREQUENCY_PENALTY": "",
    "CONSPIRACY_TEMPERATURE": "0.85",
    "CONSPIRACY_TOP_P": "0.95",
    "CONSPIRACY_PRESENCE_PENALTY": "0",
    "CONSPIRACY_FREQUENCY_PENALTY": "0.05",
    "HOROSCOPE_TEMPERATURE": "1.0",
    "HOROSCOPE_TOP_P": "",
    "HOROSCOPE_PRESENCE_PENALTY": "",
    "HOROSCOPE_FREQUENCY_PENALTY": "",
    "JOKE_TEMPERATURE": "1.0",
    "JOKE_TOP_P": "",
    "JOKE_PRESENCE_PENALTY": "",
    "JOKE_FREQUENCY_PENALTY": "",
    "ROAST_TEMPERATURE": "1.0",
    "ROAST_TOP_P": "",
    "ROAST_PRESENCE_PENALTY": "",
    "ROAST_FREQUENCY_PENALTY": "",
    "SYSTEM_PROMPT_PATH": "prompts/system.txt",
    "SUMMARY_PROMPT_PATH": "prompts/summary.txt",
    "CONSPIRACY_PROMPT_PATH": "prompts/conspiracy.txt",
    "HOROSCOPE_PROMPT_PATH": "prompts/horoscope.txt",
    "JOKE_PROMPT_PATH": "prompts/joke.txt",
    "JOKE_A_PROMPT_PATH": "prompts/joke.txt",
    "JOKE_B_PROMPT_PATH": "prompts/joke_b.txt",
    "ROAST_PROMPT_PATH": "prompts/roast.txt",
}


DEFAULT_PROMPT_TEXTS = {
    "SYSTEM_PROMPT_PATH": default_prompts.SYSTEM_BASE,
    "SUMMARY_PROMPT_PATH": default_prompts.SUMMARY_PROMPT,
    "CONSPIRACY_PROMPT_PATH": default_prompts.CONSPIRACY_PROMPT,
    "HOROSCOPE_PROMPT_PATH": default_prompts.HOROSCOPE_PROMPT,
    "JOKE_PROMPT_PATH": default_prompts.JOKE_PROMPT,
    "JOKE_A_PROMPT_PATH": default_prompts.JOKE_PROMPT,
    "JOKE_B_PROMPT_PATH": default_prompts.JOKE_B_PROMPT,
    "ROAST_PROMPT_PATH": default_prompts.ROAST_PROMPT,
}


def read_existing_env() -> dict[str, str]:
    return read_env(ENV_PATH)


def ask_value(key: str, label: str, secret: bool, existing: dict[str, str]) -> str:
    current = existing.get(key) or DEFAULTS.get(key, "")
    suffix = f" [{current}]" if current and not secret else ""
    prompt = f"{label}{suffix}: "
    raw = input(prompt)
    return raw.strip() or current


def write_env(values: dict[str, str]) -> None:
    ordered_keys = [
        "TELEGRAM_BOT_TOKEN",
        "OPENROUTER_API_KEY",
        "OPENROUTER_DEFAULT_MODEL",
        "OPENROUTER_QUALITY_MODEL",
        "OPENROUTER_CHEAP_MODEL",
        "ANSWER_MODEL",
        "SUMMARY_MODEL",
        "CONSPIRACY_MODEL",
        "HOROSCOPE_MODEL",
        "JOKE_MODEL",
        "ROAST_MODEL",
        "BOT_CHAT_ID",
        "ADMIN_USER_IDS",
        "TELEGRAM_USER_API_ID",
        "TELEGRAM_USER_API_HASH",
        "TELEGRAM_USER_SESSION",
        "TARGET_USERNAME",
        "BULLY_TARGET_USERNAME",
        "TIMEZONE",
        "DATABASE_PATH",
        "LOCAL_IMAGE_DIR",
        "IMAGE_SOURCE_CHANNELS",
        "ALABUGA_CHANNEL_URL",
        "ALABUGA_JOBS_URL",
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
        "TRACKED_WORDS",
        "RANDOM_IMAGE_EVERY_MINUTES",
        "RANDOM_IMAGE_PROBABILITY",
        "ROAST_EVERY_MINUTES",
        "ROAST_PROBABILITY",
        "BULLY_MESSAGE_TEXT",
        "CONSPIRACY_EVERY_DAYS",
        "ALABUGA_EVERY_HOURS",
        "SUMMARY_CONTEXT_HOURS",
        "HOROSCOPE_CONTEXT_DAYS",
        "CONSPIRACY_CONTEXT_DAYS",
        "ROAST_CONTEXT_DAYS",
        "ANSWER_TEMPERATURE",
        "ANSWER_TOP_P",
        "ANSWER_TOP_K",
        "ANSWER_PRESENCE_PENALTY",
        "ANSWER_FREQUENCY_PENALTY",
        "ANSWER_REPETITION_PENALTY",
        "ANSWER_MIN_P",
        "ANSWER_TOP_A",
        "ANSWER_MAX_TOKENS",
        "SUMMARY_TEMPERATURE",
        "SUMMARY_TOP_P",
        "SUMMARY_PRESENCE_PENALTY",
        "SUMMARY_FREQUENCY_PENALTY",
        "CONSPIRACY_TEMPERATURE",
        "CONSPIRACY_TOP_P",
        "CONSPIRACY_PRESENCE_PENALTY",
        "CONSPIRACY_FREQUENCY_PENALTY",
        "HOROSCOPE_TEMPERATURE",
        "HOROSCOPE_TOP_P",
        "HOROSCOPE_PRESENCE_PENALTY",
        "HOROSCOPE_FREQUENCY_PENALTY",
        "JOKE_TEMPERATURE",
        "JOKE_TOP_P",
        "JOKE_PRESENCE_PENALTY",
        "JOKE_FREQUENCY_PENALTY",
        "ROAST_TEMPERATURE",
        "ROAST_TOP_P",
        "ROAST_PRESENCE_PENALTY",
        "ROAST_FREQUENCY_PENALTY",
        "SYSTEM_PROMPT_PATH",
        "SUMMARY_PROMPT_PATH",
        "CONSPIRACY_PROMPT_PATH",
        "HOROSCOPE_PROMPT_PATH",
        "JOKE_PROMPT_PATH",
        "JOKE_A_PROMPT_PATH",
        "JOKE_B_PROMPT_PATH",
        "ROAST_PROMPT_PATH",
    ]
    lines = [f"{key}={values.get(key, '')}" for key in ordered_keys]
    ENV_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def ensure_prompt_files(values: dict[str, str]) -> None:
    for key, default_text in DEFAULT_PROMPT_TEXTS.items():
        path_value = values.get(key, "").strip()
        if not path_value:
            continue
        path = Path(path_value)
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            path.write_text(default_text.strip() + "\n", encoding="utf-8")


def maybe_edit_prompt_files(values: dict[str, str]) -> None:
    print("\nPrompt files:")
    for key in DEFAULT_PROMPT_TEXTS:
        print(f"- {key}: {values.get(key, '')}")
    answer = input("Open prompt files in $EDITOR now? [y/N]: ").strip().lower()
    if answer not in {"y", "yes"}:
        return
    editor = os.environ.get("EDITOR")
    if not editor:
        print("EDITOR is not set. Edit the files above manually, for example with nano or vim.")
        return
    for key in DEFAULT_PROMPT_TEXTS:
        path_value = values.get(key, "").strip()
        if path_value:
            subprocess.run([editor, path_value], check=False)


def main() -> None:
    existing = read_existing_env()
    values = {**DEFAULTS, **existing}
    print("Interactive setup for the Telegram bot. Press Enter to keep defaults.")
    print("Security note: rotate any bot token that was pasted into chat/logs before production.")
    for key, label, secret in QUESTIONS:
        values[key] = ask_value(key, label, secret, existing)
    write_env(values)
    ensure_prompt_files(values)
    Path(values["LOCAL_IMAGE_DIR"]).mkdir(parents=True, exist_ok=True)
    Path(values["DATABASE_PATH"]).parent.mkdir(parents=True, exist_ok=True)
    maybe_edit_prompt_files(values)
    print(f"Saved configuration to {ENV_PATH.resolve()}")


if __name__ == "__main__":
    main()
