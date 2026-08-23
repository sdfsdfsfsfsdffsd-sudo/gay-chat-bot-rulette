from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from bot.config import Settings


logger = logging.getLogger(__name__)


def userbot_is_configured(settings: "Settings") -> bool:
    return bool(
        settings.telegram_user_api_id
        and settings.telegram_user_api_hash
        and settings.telegram_user_session
    )


async def forward_post_with_userbot(
    settings: "Settings",
    target_chat_id: int,
    channel_username: str,
    message_id: int,
) -> bool:
    if not userbot_is_configured(settings):
        return False
    try:
        from telethon import TelegramClient
        from telethon.sessions import StringSession

        async with TelegramClient(
            StringSession(settings.telegram_user_session),
            settings.telegram_user_api_id,
            settings.telegram_user_api_hash,
        ) as client:
            target = await client.get_entity(target_chat_id)
            source = await client.get_entity(channel_username)
            await client.forward_messages(target, message_id, source)
        return True
    except Exception as error:
        logger.warning(
            "Could not forward Telegram post with userbot %s/%s: %s",
            channel_username,
            message_id,
            error,
        )
        return False
