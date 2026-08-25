from __future__ import annotations

import asyncio
import hashlib
import html
import logging
import random
import re
from collections.abc import Awaitable, Callable

from aiogram import Bot, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from bot.admin_panel import (
    FIELDS,
    admin_field_keyboard,
    admin_field_text,
    admin_group_keyboard,
    admin_group_text,
    admin_home_keyboard,
    admin_home_text,
    admin_set_prompt_text,
    GROUPS,
    PROMPT_TEXT_KEYS,
)
from bot.answer_pipeline import AnswerExtractionError, generate_clean_answer
from bot.bully import render_bully_message
from bot.config import BOOLEAN_SETTING_KEYS, Settings, validate_setting_override
from bot.commands import can_use_command, commands_text
from bot.horoscope import split_horoscope_by_participant
from bot.jokes import fetch_random_joke, format_joke_html
from bot.llm import OpenRouterClient
from bot.prompt_loader import PromptSet
from bot.runtime_config import sync_runtime_config
from bot.sources import fetch_random_telegram_item
from bot.storage import Storage
from bot.telegram_format import normalize_telegram_html
from bot.userbot import forward_post_with_userbot, missing_userbot_fields, userbot_is_configured
from bot.word_stats import build_daily_word_stats


logger = logging.getLogger(__name__)


def participants_block(participants: list[str]) -> str:
    if not participants:
        return "Участники: список пуст, сделай общий формат без персональных тегов."
    return "Участники для тегирования:\n" + "\n".join(f"- {participant}" for participant in participants)


CONTEXT_REQUEST_MARKERS = (
    "по чату",
    "по контексту",
    "из контекста",
    "последние сообщения",
    "последних сообщений",
    "что обсуждали",
    "о чем говорили",
    "что было в чате",
    "с учетом чата",
)

def wants_chat_context(text: str) -> bool:
    normalized = text.lower()
    return any(marker in normalized for marker in CONTEXT_REQUEST_MARKERS)


def clean_question_text(text: str, bot_username: str | None) -> str:
    cleaned = text
    if bot_username:
        cleaned = re.sub(rf"@{re.escape(bot_username)}\b", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" ,:;-")
    return cleaned or text.strip()


def build_answer_prompt(question: str, context: str | None = None) -> str:
    if context:
        return f"Контекст чата:\n{context}\n\nВопрос:\n{question}"
    return question


def build_short_reply_answer_prompt(question: str) -> str:
    return (
        "Ответь одним коротким предложением: дерзко, жестко и по делу. "
        "Без рассуждений, без списков, без ролей.\n\n"
        f"{question}"
    )


def command_argument(text: str | None) -> str:
    if not text:
        return ""
    parts = text.split(maxsplit=1)
    return parts[1].strip() if len(parts) > 1 else ""


def build_runtime_config_text(settings: Settings, prompts: PromptSet) -> str:
    rows = ["Effective runtime config:"]
    missing_forward_fields = missing_userbot_fields(settings)
    rows.append(
        "telegram_forwarding: "
        f"userbot={'configured' if userbot_is_configured(settings) else 'missing'} | "
        f"missing={','.join(missing_forward_fields) if missing_forward_fields else 'none'}"
    )
    rows.append(f"answer_web_search_enabled={getattr(settings, 'answer_web_search_enabled', True)}")
    rows.append(
        "automations: "
        f"summary={settings.summary_enabled} | horoscope={settings.horoscope_enabled} | "
        f"joke_a={settings.joke_a_enabled} | joke_b={settings.joke_b_enabled} | "
        f"conspiracy={settings.conspiracy_enabled} | word_stats={settings.word_stats_enabled} | "
        f"random_image={settings.random_image_enabled} | bully={settings.auto_bully_enabled} | "
        f"alabuga={settings.alabuga_enabled}"
    )
    for service in ("answer", "summary", "conspiracy", "horoscope", "joke"):
        model = getattr(settings, f"{service}_model")
        system_prompt = getattr(prompts, f"{service}_system").strip()
        fingerprint = (
            hashlib.sha256(system_prompt.encode("utf-8")).hexdigest()[:12]
            if system_prompt
            else "none"
        )
        rows.append(
            f"{service}: model={model} | system_sha256={fingerprint} | system_chars={len(system_prompt)}"
        )
        params = getattr(settings, f"{service}_params")
        rows.append(
            "  sampling: "
            f"temperature={params.temperature} | top_p={params.top_p} | top_k={params.top_k} | "
            f"presence={params.presence_penalty} | frequency={params.frequency_penalty} | "
            f"repetition={params.repetition_penalty} | max_tokens={params.max_tokens}"
        )
    return "\n".join(rows)


def format_roast_target(value: str) -> str:
    value = value.strip()
    if not value:
        return ""
    if value.startswith("@"):
        return value
    if re.fullmatch(r"[A-Za-z0-9_]{5,}", value):
        return f"@{value}"
    return value


def build_router(
    settings: Settings,
    storage: Storage,
    llm: OpenRouterClient,
    prompts: PromptSet,
    *,
    reload_scheduler: Callable[[], None] | None = None,
    reload_command_menu: Callable[[], Awaitable[None]] | None = None,
) -> Router:
    router = Router()
    active_questions: dict[int, asyncio.Lock] = {}
    pending_admin_updates: dict[int, str] = {}

    def is_admin_user(user_id: int | None) -> bool:
        if not settings.admin_user_ids:
            return True
        return bool(user_id and user_id in settings.admin_user_ids)

    def is_admin(message: Message) -> bool:
        return is_admin_user(message.from_user.id if message.from_user else None)

    def can_run(message: Message, command_name: str) -> bool:
        return can_use_command(command_name, is_admin(message))

    async def refresh_runtime_config() -> None:
        await sync_runtime_config(settings, prompts, storage)
        if reload_scheduler is not None:
            reload_scheduler()
        if reload_command_menu is not None:
            await reload_command_menu()

    async def field_text(key: str) -> str:
        return admin_field_text(
            key,
            await storage.prompt_overrides(),
            await storage.settings_overrides(),
        )

    @router.message(Command("start"))
    async def start(message: Message) -> None:
        await message.answer(
            "Я жив. Для привязки чата админ может написать /bind_chat. "
            "Для списка команд: /commands."
        )

    @router.message(Command("commands"))
    async def commands(message: Message) -> None:
        await message.answer(
            commands_text(is_admin(message)),
            parse_mode="HTML",
        )

    @router.message(Command("admin"))
    async def admin(message: Message) -> None:
        if not is_admin(message):
            return
        await message.answer(admin_home_text(), reply_markup=admin_home_keyboard(), parse_mode="HTML")

    @router.message(Command("runtime_config"))
    async def runtime_config(message: Message) -> None:
        if not is_admin(message):
            return
        await sync_runtime_config(settings, prompts, storage)
        await message.answer(build_runtime_config_text(settings, prompts))

    @router.message(Command("forward_config"))
    async def forward_config(message: Message) -> None:
        if not is_admin(message):
            return
        await sync_runtime_config(settings, prompts, storage)
        missing = missing_userbot_fields(settings)
        status = "configured" if not missing else "missing"
        await message.answer(
            "<b>Telegram forward config</b>\n\n"
            f"Bot API forward: <code>enabled</code>\n"
            f"Userbot forward: <code>{status}</code>\n"
            f"Missing: <code>{html.escape(', '.join(missing) if missing else 'none')}</code>\n\n"
            "Если Bot API пишет <code>message to forward not found</code>, нужен userbot: "
            "<code>TELEGRAM_USER_API_ID</code>, <code>TELEGRAM_USER_API_HASH</code>, "
            "<code>TELEGRAM_USER_SESSION</code>.",
            parse_mode="HTML",
        )

    @router.callback_query(lambda callback: bool(callback.data and callback.data.startswith("admin:")))
    async def admin_callback(callback: CallbackQuery) -> None:
        if not is_admin_user(callback.from_user.id if callback.from_user else None):
            await callback.answer("Только для админов.", show_alert=True)
            return
        if not callback.message:
            await callback.answer()
            return

        data = callback.data or ""
        parts = data.split(":", 2)
        action = parts[1] if len(parts) > 1 else ""
        value = parts[2] if len(parts) > 2 else ""

        if action == "home":
            await callback.message.edit_text(admin_home_text(), reply_markup=admin_home_keyboard(), parse_mode="HTML")
        elif action == "g" and value in GROUPS:
            await callback.message.edit_text(admin_group_text(value), reply_markup=admin_group_keyboard(value), parse_mode="HTML")
        elif action == "f" and value in FIELDS:
            await callback.message.edit_text(
                await field_text(value),
                reply_markup=admin_field_keyboard(value),
                parse_mode="HTML",
            )
        elif action == "set" and value in FIELDS:
            pending_admin_updates[callback.from_user.id] = value
            await callback.message.answer(admin_set_prompt_text(value), parse_mode="HTML")
        elif action == "toggle" and value in FIELDS and value in BOOLEAN_SETTING_KEYS:
            await sync_runtime_config(settings, prompts, storage)
            current = bool(getattr(settings, value.lower(), True))
            await storage.set_setting_override(value, "false" if current else "true")
            await refresh_runtime_config()
            await callback.message.edit_text(
                await field_text(value),
                reply_markup=admin_field_keyboard(value),
                parse_mode="HTML",
            )
            await callback.message.answer("Готово: переключил и применил без перезапуска.")
        elif action == "clear" and value in FIELDS:
            if value in PROMPT_TEXT_KEYS:
                await storage.clear_prompt_override(value)
                message_text = "Prompt override очищен в SQLite и применён в runtime."
            else:
                await storage.clear_setting_override(value)
                message_text = "Setting override очищен в SQLite. Теперь используется fallback из .env/default."
            await refresh_runtime_config()
            await callback.message.edit_text(
                await field_text(value),
                reply_markup=admin_field_keyboard(value),
                parse_mode="HTML",
            )
            await callback.message.answer(message_text)
        elif action == "back" and value in GROUPS:
            await callback.message.edit_text(admin_group_text(value), reply_markup=admin_group_keyboard(value), parse_mode="HTML")
        elif action == "close":
            await callback.message.edit_text("Админка закрыта.")
        await callback.answer()

    @router.message(lambda message: bool(message.from_user and message.from_user.id in pending_admin_updates))
    async def admin_update_value(message: Message) -> None:
        if not is_admin(message):
            return
        user_id = message.from_user.id
        key = pending_admin_updates.pop(user_id)
        value = (message.text or "").strip()
        if value == "/cancel":
            await message.answer("Изменение отменено.")
            return
        if value == "-":
            value = ""
        if key in PROMPT_TEXT_KEYS:
            if value:
                await storage.set_prompt_override(key, value)
                action_text = "Saved prompt override in SQLite."
            else:
                await storage.clear_prompt_override(key)
                action_text = "Cleared prompt override in SQLite."
            await refresh_runtime_config()
            await message.answer(
                f"{action_text}\nKey: <code>{key}</code>\n"
                "Applied in runtime.",
                parse_mode="HTML",
            )
        else:
            if value:
                try:
                    validate_setting_override(key, value)
                except (ValueError, OverflowError) as error:
                    await message.answer(
                        f"Некорректное значение для {key}: {error}",
                    )
                    return
                await storage.set_setting_override(key, value)
                action_text = "Saved setting override in SQLite."
            else:
                await storage.clear_setting_override(key)
                action_text = "Cleared setting override in SQLite. Runtime now uses .env/default fallback."
            await refresh_runtime_config()
            await message.answer(
                f"{action_text}\nKey: <code>{key}</code>\n"
                "Applied in runtime.",
                parse_mode="HTML",
            )

    @router.message(Command("bind_chat"))
    async def bind_chat(message: Message) -> None:
        if not is_admin(message):
            await message.answer("This command is only for admins.")
            return
        await storage.set_setting_override("BOT_CHAT_ID", str(message.chat.id))
        await refresh_runtime_config()
        await message.answer(
            f"Chat id: `{message.chat.id}`\n"
            "Saved to SQLite as BOT_CHAT_ID and applied in runtime.",
            parse_mode="Markdown",
        )

    @router.message(Command("summary_now"))
    async def summary_now(message: Message) -> None:
        if not is_admin(message):
            return
        await sync_runtime_config(settings, prompts, storage)
        lines = await storage.recent_messages(message.chat.id, hours=settings.summary_context_hours)
        if not lines:
            await message.answer("За сутки пока пусто.")
            return
        participants = await storage.recent_participants(message.chat.id, hours=settings.summary_context_hours)
        prompt = f"{participants_block(participants)}\n\nСообщения за день:\n" + "\n".join(lines[-500:])
        text = await llm.generate_with_params(
            f"{prompts.summary}\n\n{prompt}",
            system_prompt=prompts.summary_system,
            model=settings.summary_model,
            params=settings.summary_params,
            max_tokens=1600,
        )
        try:
            await message.answer(text[:4000], parse_mode="HTML")
        except Exception:
            await message.answer(text[:4000])

    @router.message(Command("horoscope_now"))
    async def horoscope_now(message: Message) -> None:
        if not is_admin(message):
            return
        await sync_runtime_config(settings, prompts, storage)
        context_hours = settings.horoscope_context_days * 24
        participants = await storage.recent_participants(message.chat.id, hours=context_hours)
        context = "\n".join(await storage.recent_messages(message.chat.id, hours=context_hours, limit=700))
        text = await llm.generate_with_params(
            f"{prompts.horoscope}\n\n{participants_block(participants)}\n\nКонтекст чата за последнее время:\n{context}",
            system_prompt=prompts.horoscope_system,
            model=settings.horoscope_model,
            params=settings.horoscope_params,
            max_tokens=1400,
        )
        for message_text in split_horoscope_by_participant(text, participants):
            try:
                await message.answer(message_text[:4000], parse_mode="HTML")
            except Exception:
                await message.answer(message_text[:4000])


    @router.message(Command("joke_now"))
    async def joke_now(message: Message) -> None:
        if not is_admin(message):
            return
        await sync_runtime_config(settings, prompts, storage)
        joke = await fetch_random_joke(settings.joke_source_urls)
        if joke is None:
            await message.answer("Не смог найти анекдот: источники не ответили или пустые.")
            return
        try:
            await message.answer(format_joke_html(joke)[:4000], parse_mode="HTML", disable_web_page_preview=True)
        except Exception:
            await message.answer(joke.text[:4000])

    @router.message(Command("conspiracy_now"))
    async def conspiracy_now(message: Message) -> None:
        if not is_admin(message):
            return
        await sync_runtime_config(settings, prompts, storage)
        context_hours = settings.conspiracy_context_days * 24
        lines = await storage.recent_messages(message.chat.id, hours=context_hours, limit=700)
        participants = await storage.recent_participants(message.chat.id, hours=context_hours)
        prompt = (
            f"{participants_block(participants)}\n\n"
            f"{prompts.conspiracy}\n\n"
            "Контекст:\n" + "\n".join(lines[-700:])
        )
        text = await llm.generate_with_params(
            prompt,
            system_prompt=prompts.conspiracy_system,
            model=settings.conspiracy_model,
            params=settings.conspiracy_params,
            max_tokens=900,
        )
        try:
            await message.answer(normalize_telegram_html(text)[:4000], parse_mode="HTML")
        except Exception:
            await message.answer(text[:4000])

    @router.message(Command("bully"))
    async def bully_now(message: Message) -> None:
        if not can_run(message, "bully"):
            return
        await sync_runtime_config(settings, prompts, storage)
        arg = command_argument(message.text).lstrip("@")
        participants = await storage.recent_participants(message.chat.id, hours=24)
        if arg.lower() == "random":
            target = random.choice(participants) if participants else ""
        elif arg:
            target = format_roast_target(arg)
        elif settings.bully_target_username or settings.target_username:
            target = format_roast_target(settings.bully_target_username or settings.target_username or "")
        else:
            target = ""

        if not target:
            await message.answer(
                "Некого bully-ить: укажи <code>/bully @username</code> или задай "
                "<code>BULLY_TARGET_USERNAME</code> через <code>/bully_target</code> или админку.",
                parse_mode="HTML",
            )
            return

        text = render_bully_message(settings.bully_message_text, target)
        await message.answer(normalize_telegram_html(text)[:4000], parse_mode="HTML")

    @router.message(Command("bully_text"))
    async def bully_text(message: Message) -> None:
        if not is_admin(message):
            return
        await sync_runtime_config(settings, prompts, storage)
        value = command_argument(message.text)
        if not value:
            await message.answer(
                "<b>Текущий bully-текст</b>\n"
                f"<code>{html.escape(settings.bully_message_text)}</code>\n\n"
                "Изменить: <code>/bully_text новый текст {target}</code>\n"
                "Сбросить: <code>/bully_text -</code>\n"
                "Доступные плейсхолдеры: <code>{target}</code>, <code>{username}</code>",
                parse_mode="HTML",
            )
            return
        if value == "-":
            await storage.clear_setting_override("BULLY_MESSAGE_TEXT")
            await refresh_runtime_config()
            await message.answer("Bully-текст сброшен на дефолт.")
            return
        await storage.set_setting_override("BULLY_MESSAGE_TEXT", value)
        await refresh_runtime_config()
        await message.answer(
            "Bully-текст сохранён:\n"
            f"<code>{html.escape(value)}</code>",
            parse_mode="HTML",
        )

    @router.message(Command("bully_target"))
    async def bully_target(message: Message) -> None:
        if not is_admin(message):
            return
        await sync_runtime_config(settings, prompts, storage)
        value = command_argument(message.text).strip().lstrip("@")
        if not value:
            current = settings.bully_target_username or settings.target_username or ""
            await message.answer(
                "<b>Текущая bully-цель</b>\n"
                f"<code>{html.escape('@' + current if current else '<не задано>')}</code>\n\n"
                "Изменить: <code>/bully_target username</code>\n"
                "Сбросить: <code>/bully_target -</code>",
                parse_mode="HTML",
            )
            return
        if value == "-":
            await storage.clear_setting_override("BULLY_TARGET_USERNAME")
            await refresh_runtime_config()
            await message.answer("Bully-цель сброшена.")
            return
        await storage.set_setting_override("BULLY_TARGET_USERNAME", value)
        await refresh_runtime_config()
        await message.answer(f"Bully-цель сохранена: <code>@{html.escape(value)}</code>", parse_mode="HTML")

    @router.message(Command("word_stats_now"))
    async def word_stats_now(message: Message) -> None:
        if not can_run(message, "word_stats_now"):
            return
        text = await build_daily_word_stats(storage, message.chat.id, settings.tracked_words)
        await message.answer(text[:4000])

    @router.message(Command("alabuga", "alabuga_random"))
    async def alabuga_random(message: Message, bot: Bot) -> None:
        if not can_run(message, "alabuga"):
            return
        item = await fetch_random_telegram_item(settings.alabuga_channel_url, limit=30)
        if not item:
            await message.answer("Не смог найти посты в канале Алабуга Политех.")
            return
        if item.channel_username and item.message_id:
            try:
                await bot.forward_message(message.chat.id, f"@{item.channel_username}", item.message_id)
                return
            except Exception as error:
                logger.warning("Could not forward Telegram post %s/%s: %s", item.channel_username, item.message_id, error)
            if await forward_post_with_userbot(settings, message.chat.id, item.channel_username, item.message_id):
                return
        await message.answer(f"Alabuga Polytech:\n\n{item.text[:3400]}\n\n{item.url}")


    @router.message()
    async def collect_and_answer(message: Message, bot: Bot) -> None:
        if not message.text:
            return
        user = message.from_user
        await storage.save_message(
            chat_id=message.chat.id,
            user_id=user.id if user else None,
            username=user.username if user else None,
            full_name=user.full_name if user else None,
            text=message.text,
            created_at=message.date.replace(tzinfo=None),
        )

        me = await bot.get_me()
        mentioned = f"@{me.username}".lower() in message.text.lower() if me.username else False
        replied_to_bot = bool(message.reply_to_message and message.reply_to_message.from_user and message.reply_to_message.from_user.id == me.id)
        if not (mentioned or replied_to_bot or message.chat.type == "private"):
            return

        lock = active_questions.setdefault(message.chat.id, asyncio.Lock())
        if lock.locked():
            await message.reply("Я еще думаю над прошлым вопросом. Секунду.")
            return

        async with lock:
            processing_message = await message.reply("Ищу ответ на вопрос...")
            try:
                text = await generate_answer(message, me.username, settings, storage, llm, short_reply=replied_to_bot)
                try:
                    await message.reply(normalize_telegram_html(text)[:4000], parse_mode="HTML")
                except Exception:
                    await message.reply(text[:4000])
            except AnswerExtractionError:
                await message.reply("Не удалось выделить чистый ответ. Попробуйте задать вопрос ещё раз.")
            except Exception:
                await message.reply("Не удалось получить ответ от модели. Попробуйте ещё раз чуть позже.")
            finally:
                try:
                    await processing_message.delete()
                except Exception:
                    pass

    async def generate_answer(
        message: Message,
        bot_username: str | None,
        settings: Settings,
        storage: Storage,
        llm: OpenRouterClient,
        *,
        short_reply: bool = False,
    ) -> str:
        await sync_runtime_config(settings, prompts, storage)
        question = clean_question_text(message.text or "", bot_username)
        if short_reply:
            prompt = build_short_reply_answer_prompt(question)
            max_tokens = 120
            web_search = False
        elif wants_chat_context(message.text):
            context = "\n".join(await storage.recent_messages(message.chat.id, hours=6, limit=80))
            prompt = build_answer_prompt(question, context)
            max_tokens = None
            web_search = False
        else:
            prompt = build_answer_prompt(question)
            max_tokens = None
            web_search = settings.answer_web_search_enabled
        text = await generate_clean_answer(
            llm,
            prompt,
            system_prompt=prompts.answer_system,
            model=settings.answer_model,
            params=settings.answer_params,
            max_tokens=max_tokens,
            web_search=web_search,
        )
        return text

    return router
