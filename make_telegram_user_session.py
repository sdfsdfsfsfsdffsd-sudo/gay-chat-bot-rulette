from __future__ import annotations

import asyncio
import getpass
import os

from telethon import TelegramClient
from telethon.sessions import StringSession


def ask_required(prompt: str, *, secret: bool = False) -> str:
    while True:
        value = (getpass.getpass(prompt) if secret else input(prompt)).strip()
        if value:
            return value
        print("Value cannot be empty.")


def ask_api_id() -> int:
    env_value = os.getenv("TELEGRAM_USER_API_ID", "").strip()
    while True:
        raw = input(f"Telegram API ID [{env_value}]: ").strip() or env_value
        try:
            return int(raw)
        except ValueError:
            print("Telegram API ID must be a number from https://my.telegram.org/apps.")


async def main() -> None:
    print("Create API credentials at https://my.telegram.org/apps first.")
    api_id = ask_api_id()
    api_hash = os.getenv("TELEGRAM_USER_API_HASH", "").strip() or ask_required("Telegram API hash: ", secret=True)
    phone = ask_required("Phone number, international format: ")

    async with TelegramClient(StringSession(), api_id, api_hash) as client:
        await client.start(phone=phone)
        print("\nTELEGRAM_USER_SESSION:")
        print(client.session.save())


if __name__ == "__main__":
    asyncio.run(main())
