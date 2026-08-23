from __future__ import annotations

import asyncio
import getpass

from telethon import TelegramClient
from telethon.sessions import StringSession


async def main() -> None:
    api_id = int(input("Telegram API ID: ").strip())
    api_hash = getpass.getpass("Telegram API hash: ").strip()
    phone = input("Phone number, international format: ").strip()

    async with TelegramClient(StringSession(), api_id, api_hash) as client:
        await client.start(phone=phone)
        print("\nTELEGRAM_USER_SESSION:")
        print(client.session.save())


if __name__ == "__main__":
    asyncio.run(main())
