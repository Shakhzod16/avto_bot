"""Lifespan helpers for polling and webhook Telegram bot operation."""

from __future__ import annotations

import asyncio
import logging
import re
from urllib.parse import urlparse

from aiogram import Bot, Dispatcher
from aiogram.exceptions import TelegramAPIError, TelegramUnauthorizedError
from aiogram.types import (
    BotCommand,
    MenuButtonWebApp,
    WebAppInfo,
)
from aiogram.utils.token import TokenValidationError

from backend.app.bot.handlers import router
from backend.app.core.config import (
    BOT_MODE,
    BOT_TOKEN,
    ENV_FILE,
    PUBLIC_BASE_URL,
    WEBAPP_URL,
    WEBHOOK_PATH,
    WEBHOOK_SECRET,
    webapp_url_error,
)

logger = logging.getLogger(__name__)
BOT_COMMANDS = [
    BotCommand(command="start", description="Katalogni ochish"),
    BotCommand(command="contact", description="Manzil va aloqa"),
    BotCommand(command="cancel", description="Amalni bekor qilish"),
    BotCommand(command="help", description="Yordam"),
    BotCommand(command="stats", description="Qisqa statistika"),
    BotCommand(command="leads", description="Oxirgi arizalar"),
]


def _validate_bot_settings() -> None:
    if not BOT_TOKEN:
        raise RuntimeError(
            "BOT_TOKEN bo'sh / BOT_TOKEN is missing. "
            f"Tekshirilgan fayl / Checked file: {ENV_FILE}"
        )
    if BOT_MODE not in {"polling", "webhook"}:
        raise RuntimeError("BOT_MODE faqat 'polling' yoki 'webhook' bo'lishi mumkin.")
    url_error = webapp_url_error(WEBAPP_URL)
    if url_error:
        logger.warning(
            "%s Mini App menyu tugmasi o'zgartirilmadi. Ommaviy HTTPS tunnelni "
            "ishga tushiring va botni qayta boshlang.",
            url_error,
        )
    if BOT_MODE == "webhook":
        public = urlparse(PUBLIC_BASE_URL)
        if public.scheme != "https" or not public.netloc:
            raise RuntimeError(
                "Webhook rejimida PUBLIC_BASE_URL ochiq HTTPS havola bo'lishi kerak."
            )
        if not WEBHOOK_PATH.startswith("/") or "?" in WEBHOOK_PATH:
            raise RuntimeError(
                "WEBHOOK_PATH / bilan boshlanishi va query string bo'lmasligi kerak."
            )
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,256}", WEBHOOK_SECRET):
            raise RuntimeError(
                "Webhook rejimida WEBHOOK_SECRET 1-256 ta harf, raqam, _ yoki - bo'lishi kerak."
            )


def _log_polling_result(task: asyncio.Task) -> None:
    if task.cancelled():
        return
    error = task.exception()
    if error is not None:
        logger.error(
            "Telegram polling vazifasi xato bilan to'xtadi",
            exc_info=(type(error), error, error.__traceback__),
        )
    else:
        logger.info("Telegram polling vazifasi yakunlandi")


async def start_telegram_bot(app) -> None:
    """Validate the token, configure bot UI and start polling or webhook mode."""
    _validate_bot_settings()
    try:
        bot = Bot(token=BOT_TOKEN)
    except TokenValidationError as exc:
        raise RuntimeError(
            "BOT_TOKEN formati noto'g'ri. BotFather tokenini tekshiring."
        ) from exc
    dispatcher = Dispatcher()
    dispatcher.include_router(router)
    app.state.telegram_bot = bot
    app.state.telegram_dispatcher = dispatcher
    app.state.bot_polling_task = None

    try:
        me = await bot.get_me()
    except TelegramUnauthorizedError as exc:
        await bot.session.close()
        app.state.telegram_bot = None
        raise RuntimeError(
            "Telegram BOT_TOKEN rad etdi (Unauthorized). BotFather'dan tokenni tekshiring yoki yangilang."
        ) from exc
    except TelegramAPIError as exc:
        await bot.session.close()
        app.state.telegram_bot = None
        raise RuntimeError(
            "Telegram API bilan bog'lanib bo'lmadi; tarmoq va tokenni tekshiring."
        ) from exc

    app.state.telegram_bot_username = me.username
    logger.info("Telegram bot ulandi: @%s (ID: %s)", me.username, me.id)
    await bot.set_my_commands(BOT_COMMANDS)
    if webapp_url_error(WEBAPP_URL) is None:
        try:
            await bot.set_chat_menu_button(
                menu_button=MenuButtonWebApp(
                    text="🚗 Katalog",
                    web_app=WebAppInfo(url=WEBAPP_URL),
                )
            )
        except TelegramAPIError:
            logger.exception(
                "Telegram menyu tugmasi yangilanmadi; WEBAPP_URL qiymatini tekshiring"
            )

    if BOT_MODE == "polling":
        await bot.delete_webhook(drop_pending_updates=False)
        app.state.bot_polling_task = asyncio.create_task(
            dispatcher.start_polling(
                bot, handle_signals=False, close_bot_session=False
            ),
            name="telegram-polling",
        )
        app.state.bot_polling_task.add_done_callback(_log_polling_result)
        await asyncio.sleep(0)
        logger.info("Start polling")
    else:
        await bot.set_webhook(
            url=f"{PUBLIC_BASE_URL}{WEBHOOK_PATH}",
            secret_token=WEBHOOK_SECRET,
            drop_pending_updates=False,
        )
        logger.info(
            "Telegram bot webhook manzili sozlandi: %s%s", PUBLIC_BASE_URL, WEBHOOK_PATH
        )


async def stop_telegram_bot(app) -> None:
    """Stop polling cleanly and close the bot's HTTP session."""
    task = getattr(app.state, "bot_polling_task", None)
    dispatcher = getattr(app.state, "telegram_dispatcher", None)
    bot = getattr(app.state, "telegram_bot", None)

    try:
        if task is not None and not task.done():
            if dispatcher is None:
                task.cancel()
            else:
                try:
                    await dispatcher.stop_polling()
                except RuntimeError:
                    logger.debug(
                        "Telegram polling hali ishga tushmagan; yopishni kutyapman"
                    )
            try:
                await asyncio.wait_for(task, timeout=10)
            except TimeoutError:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        elif task is not None and task.done() and not task.cancelled():
            error = task.exception()
            if error is not None:
                logger.error(
                    "Telegram polling xatolik bilan yakunlandi", exc_info=error
                )
    except Exception:
        logger.exception("Telegram pollingni to'xtatishda xatolik")
    finally:
        if bot is not None:
            if BOT_MODE == "webhook":
                try:
                    await bot.delete_webhook(drop_pending_updates=False)
                except TelegramAPIError:
                    logger.exception("Webhookni o'chirishda Telegram xatosi")
            await bot.session.close()
