from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from bot.config import Settings


logger = logging.getLogger(__name__)


def userbot_is_configured(settings: "Settings") -> bool:
    return bool(
        getattr(settings, "telegram_user_api_id", None)
        and getattr(settings, "telegram_user_api_hash", "")
        and getattr(settings, "telegram_user_session", "")
    )


def missing_userbot_fields(settings: "Settings") -> list[str]:
    missing: list[str] = []
    if not getattr(settings, "telegram_user_api_id", None):
        missing.append("TELEGRAM_USER_API_ID")
    if not getattr(settings, "telegram_user_api_hash", ""):
        missing.append("TELEGRAM_USER_API_HASH")
    if not getattr(settings, "telegram_user_session", ""):
        missing.append("TELEGRAM_USER_SESSION")
    return missing


async def _resolve_target_dialog(client, target_chat_id: int):
    try:
        return await client.get_input_entity(target_chat_id)
    except (TypeError, ValueError):
        pass

    async for dialog in client.iter_dialogs():
        if dialog.id == target_chat_id:
            return dialog.input_entity
    raise ValueError(
        f"Target chat {target_chat_id} is not available to the Telegram user account. "
        "Add that account to the destination chat first."
    )


async def forward_post_with_userbot(
    settings: "Settings",
    target_chat_id: int,
    channel_username: str,
    message_id: int,
) -> bool:
    if not userbot_is_configured(settings):
        logger.info(
            "Userbot forward skipped: missing %s",
            ", ".join(missing_userbot_fields(settings)),
        )
        return False
    try:
        from telethon import TelegramClient
        from telethon.sessions import StringSession

        async with TelegramClient(
            StringSession(settings.telegram_user_session),
            settings.telegram_user_api_id,
            settings.telegram_user_api_hash,
        ) as client:
            target = await _resolve_target_dialog(client, target_chat_id)
            source = await client.get_input_entity(channel_username)
            await client.forward_messages(target, message_id, source)
        logger.info(
            "Forwarded Telegram post with user account: source=%s/%s target=%s",
            channel_username,
            message_id,
            target_chat_id,
        )
        return True
    except Exception as error:
        logger.warning(
            "Could not forward Telegram post with userbot %s/%s to %s: %s: %s",
            channel_username,
            message_id,
            target_chat_id,
            type(error).__name__,
            error,
        )
        return False
