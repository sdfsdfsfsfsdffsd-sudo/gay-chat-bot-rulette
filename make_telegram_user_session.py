from __future__ import annotations

import asyncio
import getpass
import os
import re

from telethon import TelegramClient
from telethon.errors import ApiIdInvalidError
from telethon.sessions import StringSession


def ask_required(prompt: str, *, secret: bool = False) -> str:
    while True:
        value = (getpass.getpass(prompt) if secret else input(prompt)).strip()
        if value:
            return value
        print("Value cannot be empty.")


def clean_hash(value: str) -> str:
    return re.sub(r"\s+", "", value.strip())


def hash_mask(value: str) -> str:
    if len(value) <= 8:
        return "*" * len(value)
    return f"{value[:4]}...{value[-4:]}"


def ask_api_id() -> int:
    env_value = os.getenv("TELEGRAM_USER_API_ID", "").strip()
    while True:
        raw = input(f"Telegram API ID [{env_value}]: ").strip() or env_value
        try:
            return int(raw)
        except ValueError:
            print("Telegram API ID must be a number from https://my.telegram.org/apps.")


def ask_api_hash() -> str:
    env_value = clean_hash(os.getenv("TELEGRAM_USER_API_HASH", ""))
    if env_value:
        print(f"Telegram API hash from env: {hash_mask(env_value)} ({len(env_value)} chars)")
        return env_value

    visible = input("Show API hash while typing? [y/N]: ").strip().lower() in {"y", "yes"}
    while True:
        raw = ask_required("Telegram API hash: ", secret=not visible)
        value = clean_hash(raw)
        print(f"Hash read as: {hash_mask(value)} ({len(value)} chars)")
        if re.fullmatch(r"[0-9a-fA-F]{32}", value):
            return value
        print("Telegram API hash must be exactly 32 hex characters from https://my.telegram.org/apps.")


async def main() -> None:
    print("Create API credentials at https://my.telegram.org/apps first.")
    api_id = ask_api_id()
    api_hash = ask_api_hash()
    phone = ask_required("Phone number, international format: ")

    print(f"Using api_id={api_id}, api_hash={hash_mask(api_hash)} ({len(api_hash)} chars)")

    client = TelegramClient(StringSession(), api_id, api_hash)
    try:
        await client.start(phone=phone)
        print("\nTELEGRAM_USER_SESSION:")
        print(client.session.save())
    except ApiIdInvalidError:
        print(
            "\nInvalid api_id/api_hash pair. Use API credentials from "
            "https://my.telegram.org/apps, not the Telegram bot token."
        )
        raise
    finally:
        await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
