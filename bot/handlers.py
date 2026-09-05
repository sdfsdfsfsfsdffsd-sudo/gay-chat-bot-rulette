from __future__ import annotations

import asyncio
import hashlib
import html
import logging
import random
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime

from aiogram import Bot, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from bot.admin_panel import (
    FIELDS,
    admin_cancel_keyboard,
    admin_clear_keyboard,
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
from bot.feed_delivery import forward_or_copy_feed_item
from bot.horoscope import split_horoscope_by_participant
from bot.jokes import fetch_random_joke, format_joke_html
from bot.llm import OpenRouterClient
from bot.prompt_loader import PromptSet
from bot.runtime_config import sync_runtime_config
from bot.sources import fetch_random_telegram_item
from bot.storage import Storage
from bot.telegram_format import normalize_telegram_html
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
        return (
            "Предыдущие сообщения приведены только как справочный контекст. "
            "Не отвечай на них по отдельности и не продолжай эту переписку. "
            "Ответь только на вопрос после блока контекста.\n\n"
            f"Контекст чата:\n{context}\n\n"
            f"Вопрос пользователя:\n{question}"
        )
    return question


def build_short_reply_answer_prompt(question: str, context: str | None = None) -> str:
    instruction = (
        "Ответь одним коротким предложением: дерзко, жестко и по делу. "
        "Без рассуждений, без списков, без ролей."
    )
    return f"{instruction}\n\n{build_answer_prompt(question, context)}"


def command_argument(text: str | None) -> str:
    if not text:
        return ""
    parts = text.split(maxsplit=1)
    return parts[1].strip() if len(parts) > 1 else ""


def build_runtime_config_text(settings: Settings, prompts: PromptSet) -> str:
    rows = ["Effective runtime config:"]
    rows.append("telegram_forwarding: bot_api_only")
    rows.append(f"answer_web_search_enabled={getattr(settings, 'answer_web_search_enabled', True)}")
    rows.append(
        "automations: "
        f"summary={settings.summary_enabled} | horoscope={settings.horoscope_enabled} | "
        f"joke_a={settings.joke_a_enabled} | joke_b={settings.joke_b_enabled} | "
        f"conspiracy={settings.conspiracy_enabled} | word_stats={settings.word_stats_enabled} | "
        f"bully={settings.auto_bully_enabled} | "
        f"alabuga={settings.alabuga_enabled}"
    )
    for service in ("answer", "summary", "conspiracy", "horoscope"):
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


def format_bully_target(value: str) -> str:
    value = value.strip()
    if not value:
        return ""
    if value.startswith("@"):
        return value
    if re.fullmatch(r"[A-Za-z0-9_]{5,}", value):
        return f"@{value}"
    return value


@dataclass(frozen=True)
class PendingAdminUpdate:
    key: str
    return_group: str
    menu_chat_id: int
    menu_message_id: int


def build_router(
    settings: Settings,
    storage: Storage,
    llm: OpenRouterClient,
    prompts: PromptSet,
    *,
    reload_scheduler: Callable[[], None] | None = None,
    reload_command_menu: Callable[[], Awaitable[None]] | None = None,
    get_scheduled_runs: Callable[[], dict[str, datetime]] | None = None,
) -> Router:
    router = Router()
    active_questions: dict[int, asyncio.Lock] = {}
    pending_admin_updates: dict[tuple[int, int], PendingAdminUpdate] = {}

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
            settings,
            get_scheduled_runs() if get_scheduled_runs is not None else None,
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
        await sync_runtime_config(settings, prompts, storage)
        await message.answer(admin_home_text(settings), reply_markup=admin_home_keyboard(settings), parse_mode="HTML")

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
        await message.answer(
            "<b>Telegram-пересылка</b>\n\n"
            "Режим: <code>только Bot API</code>\n"
            "Настоящий forward сохраняет исходное медиа и подпись автоматически. "
            "Если исходный пост недоступен боту, фото, видео и альбомы копируются "
            "с публичной страницы без сохранения на диск. Если медиа недоступно, "
            "отправляются текст и ссылка.",
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
        parts = data.split(":")
        action = parts[1] if len(parts) > 1 else ""
        value = parts[2] if len(parts) > 2 else ""
        return_group = parts[3] if len(parts) > 3 and parts[3] in GROUPS else ""

        if action == "home":
            await sync_runtime_config(settings, prompts, storage)
            await callback.message.edit_text(admin_home_text(settings), reply_markup=admin_home_keyboard(settings), parse_mode="HTML")
        elif action == "g" and value in GROUPS:
            await sync_runtime_config(settings, prompts, storage)
            scheduled_runs = get_scheduled_runs() if get_scheduled_runs is not None else None
            await callback.message.edit_text(admin_group_text(value, settings, scheduled_runs), reply_markup=admin_group_keyboard(value, settings, scheduled_runs), parse_mode="HTML")
        elif action == "f" and value in FIELDS:
            await callback.message.edit_text(
                await field_text(value),
                reply_markup=admin_field_keyboard(value, return_group, settings),
                parse_mode="HTML",
            )
        elif action == "set" and value in FIELDS:
            group_key = return_group or "advanced"
            pending_admin_updates[(callback.from_user.id, callback.message.chat.id)] = PendingAdminUpdate(
                key=value,
                return_group=group_key,
                menu_chat_id=callback.message.chat.id,
                menu_message_id=callback.message.message_id,
            )
            await callback.message.edit_text(
                admin_set_prompt_text(value),
                reply_markup=admin_cancel_keyboard(value, group_key),
                parse_mode="HTML",
            )
        elif action in {"toggle", "toggle_field"} and value in FIELDS and value in BOOLEAN_SETTING_KEYS:
            await sync_runtime_config(settings, prompts, storage)
            current = bool(getattr(settings, value.lower(), True))
            await storage.set_setting_override(value, "false" if current else "true")
            await refresh_runtime_config()
            if action == "toggle" and return_group in GROUPS:
                scheduled_runs = get_scheduled_runs() if get_scheduled_runs is not None else None
                await callback.message.edit_text(
                    admin_group_text(return_group, settings, scheduled_runs),
                    reply_markup=admin_group_keyboard(return_group, settings, scheduled_runs),
                    parse_mode="HTML",
                )
            else:
                await callback.message.edit_text(
                    await field_text(value),
                    reply_markup=admin_field_keyboard(value, return_group, settings),
                    parse_mode="HTML",
                )
        elif action == "clear" and value in FIELDS:
            group_key = return_group or "advanced"
            await callback.message.edit_text(
                f"<b>Вернуть стандартное значение?</b>\n\n{html.escape(FIELDS[value].label)} будет снова брать значение из .env или встроенных настроек.",
                reply_markup=admin_clear_keyboard(value, group_key),
                parse_mode="HTML",
            )
        elif action == "cc" and value in FIELDS:
            if value in PROMPT_TEXT_KEYS:
                await storage.clear_prompt_override(value)
            else:
                await storage.clear_setting_override(value)
            await refresh_runtime_config()
            await callback.message.edit_text(
                await field_text(value),
                reply_markup=admin_field_keyboard(value, return_group, settings),
                parse_mode="HTML",
            )
        elif action == "x" and value in FIELDS:
            pending_admin_updates.pop((callback.from_user.id, callback.message.chat.id), None)
            await callback.message.edit_text(
                await field_text(value),
                reply_markup=admin_field_keyboard(value, return_group, settings),
                parse_mode="HTML",
            )
        elif action == "close":
            pending_admin_updates.pop((callback.from_user.id, callback.message.chat.id), None)
            await callback.message.edit_text("Админка закрыта.")
        else:
            await callback.message.edit_text(admin_home_text(settings), reply_markup=admin_home_keyboard(settings), parse_mode="HTML")
            await callback.answer("Меню обновилось. Открыл актуальную главную.", show_alert=True)
            return
        await callback.answer()

    @router.message(
        lambda message: bool(
            message.text is not None
            and message.from_user
            and (message.from_user.id, message.chat.id) in pending_admin_updates
        )
    )
    async def admin_update_value(message: Message, bot: Bot) -> None:
        if not is_admin(message):
            return
        user_id = message.from_user.id
        pending_key = (user_id, message.chat.id)
        pending = pending_admin_updates[pending_key]
        key = pending.key
        value = (message.text or "").strip()
        if value == "/cancel":
            pending_admin_updates.pop(pending_key, None)
            await bot.edit_message_text(
                await field_text(key),
                chat_id=pending.menu_chat_id,
                message_id=pending.menu_message_id,
                reply_markup=admin_field_keyboard(key, pending.return_group, settings),
                parse_mode="HTML",
            )
            return
        if value == "-":
            value = ""
        if key in PROMPT_TEXT_KEYS:
            if value:
                await storage.set_prompt_override(key, value)
            else:
                await storage.clear_prompt_override(key)
        else:
            if value:
                try:
                    validate_setting_override(key, value)
                except (ValueError, OverflowError) as error:
                    await bot.edit_message_text(
                        f"{admin_set_prompt_text(key)}\n\n<b>Ошибка:</b> {html.escape(str(error))}\nПопробуй ещё раз.",
                        chat_id=pending.menu_chat_id,
                        message_id=pending.menu_message_id,
                        reply_markup=admin_cancel_keyboard(key, pending.return_group),
                        parse_mode="HTML",
                    )
                    return
                await storage.set_setting_override(key, value)
            else:
                await storage.clear_setting_override(key)
        pending_admin_updates.pop(pending_key, None)
        await refresh_runtime_config()
        await bot.edit_message_text(
            f"✅ <b>Сохранено</b>\n\n{await field_text(key)}",
            chat_id=pending.menu_chat_id,
            message_id=pending.menu_message_id,
            reply_markup=admin_field_keyboard(key, pending.return_group, settings),
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
        await storage.mark_sent("schedule:summary")
        await refresh_runtime_config()

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
        await storage.mark_sent("schedule:horoscope")
        await refresh_runtime_config()


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
        requested_kind = command_argument(message.text).lower()
        joke_kind = requested_kind if requested_kind in {"a", "b"} else random.choice(("a", "b"))
        await storage.mark_sent(f"schedule:joke_{joke_kind}")
        await refresh_runtime_config()

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
        await storage.mark_sent("schedule:conspiracy")
        await refresh_runtime_config()

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
            target = format_bully_target(arg)
        elif settings.bully_target_username:
            target = format_bully_target(settings.bully_target_username)
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
            current = settings.bully_target_username or ""
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
        await forward_or_copy_feed_item(bot, message.chat.id, item)


    @router.message()
    async def collect_and_answer(message: Message, bot: Bot) -> None:
        if not message.text:
            return
        user = message.from_user
        stored_message_id = await storage.save_message(
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
                text = await generate_answer(
                    message,
                    me.username,
                    settings,
                    storage,
                    llm,
                    short_reply=replied_to_bot,
                    stored_message_id=stored_message_id,
                )
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
        stored_message_id: int | None = None,
    ) -> str:
        await sync_runtime_config(settings, prompts, storage)
        question = clean_question_text(message.text or "", bot_username)
        if short_reply:
            replied_text = (message.reply_to_message.text or message.reply_to_message.caption or "").strip() if message.reply_to_message else ""
            history_limit = 4 if replied_text else 5
            history = (
                await storage.messages_before(message.chat.id, stored_message_id, limit=history_limit)
                if stored_message_id is not None
                else []
            )
            if replied_text:
                history.append(f"Бот: {replied_text}")
            context = "\n".join(history)
            prompt = build_short_reply_answer_prompt(question, context or None)
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
