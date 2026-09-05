from __future__ import annotations

import logging
from dataclasses import dataclass

from aiogram import Bot
from aiogram.types import BotCommand, BotCommandScopeChat, BotCommandScopeChatMember, BotCommandScopeDefault

from bot.config import Settings


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CommandDefinition:
    name: str
    description: str
    role: str = "admin"
    aliases: tuple[str, ...] = ()


COMMANDS = (
    CommandDefinition("start", "Проверить, что бот работает", "public"),
    CommandDefinition("commands", "Показать доступные команды", "public"),
    CommandDefinition("bully", "Забуллить жертву", "public"),
    CommandDefinition("word_stats_now", "Вывести статистику слов на данный момент", "public"),
    CommandDefinition("alabuga", "Случайный пост Алабуга Политех", "public", ("alabuga_random",)),
    CommandDefinition("admin", "Открыть панель управления"),
    CommandDefinition("runtime_config", "Показать модели и параметры runtime"),
    CommandDefinition("forward_config", "Показать настройки Telegram forward"),
    CommandDefinition("bind_chat", "Привязать текущий чат"),
    CommandDefinition("summary_now", "Сделать сводку сейчас"),
    CommandDefinition("horoscope_now", "Сделать гороскоп сейчас"),
    CommandDefinition("joke_now", "Анекдот сейчас: a, b или random"),
    CommandDefinition("conspiracy_now", "Создать теорию заговора сейчас"),
    CommandDefinition("alabuga_circle", "Отправить тестовый кружок Алабуги"),
    CommandDefinition("bully_text", "Показать или изменить bully-текст"),
    CommandDefinition("bully_target", "Показать или изменить bully-цель"),
)


def available_commands(is_admin: bool) -> tuple[CommandDefinition, ...]:
    return tuple(command for command in COMMANDS if command.role == "public" or is_admin)


def command_definition(command_name: str) -> CommandDefinition | None:
    normalized = command_name.lstrip("/").split("@", 1)[0]
    for command in COMMANDS:
        if normalized == command.name or normalized in command.aliases:
            return command
    return None


def can_use_command(command_name: str, is_admin: bool) -> bool:
    command = command_definition(command_name)
    if command is None:
        return is_admin
    return command.role == "public" or is_admin


def telegram_commands(is_admin: bool) -> list[BotCommand]:
    return [
        BotCommand(command=command.name, description=command.description)
        for command in available_commands(is_admin)
    ]


def commands_text(is_admin: bool) -> str:
    public = [command for command in available_commands(is_admin) if command.role == "public"]
    admin = [command for command in available_commands(is_admin) if command.role == "admin"]
    sections = ["<b>Доступные команды</b>", "", "<b>Для всех</b>"]
    sections.extend(f"/{command.name} - {command.description}" for command in public)
    if admin:
        sections.extend(("", "<b>Для администраторов</b>"))
        sections.extend(f"/{command.name} - {command.description}" for command in admin)
    return "\n".join(sections)


async def register_bot_commands(bot: Bot, settings: Settings) -> None:
    public_commands = telegram_commands(False)
    admin_commands = telegram_commands(True)

    if not settings.admin_user_ids:
        await bot.set_my_commands(admin_commands, scope=BotCommandScopeDefault())
        return

    await bot.set_my_commands(public_commands, scope=BotCommandScopeDefault())
    for user_id in settings.admin_user_ids:
        try:
            await bot.set_my_commands(admin_commands, scope=BotCommandScopeChat(chat_id=user_id))
        except Exception as error:
            logger.warning("Could not register private command menu for admin %s: %s", user_id, error)
        if settings.bot_chat_id is not None:
            try:
                await bot.set_my_commands(
                    admin_commands,
                    scope=BotCommandScopeChatMember(chat_id=settings.bot_chat_id, user_id=user_id),
                )
            except Exception as error:
                logger.warning(
                    "Could not register group command menu for admin %s in chat %s: %s",
                    user_id,
                    settings.bot_chat_id,
                    error,
                )
