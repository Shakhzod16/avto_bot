"""Bot commands and inline callbacks."""

from __future__ import annotations

import html
import json
import logging
from datetime import UTC, datetime

from aiogram import F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    ReplyKeyboardRemove,
    WebAppInfo,
)
from sqlalchemy import func, select

from backend.app.bot.callbacks import LeadStatusCallback
from backend.app.core.config import ADMIN_IDS, WEBAPP_URL, webapp_url_error
from backend.app.db.session import SessionFactory
from backend.app.models import Lead, LeadStatus, Setting, User
from backend.app.services.audit import write_audit_entry

logger = logging.getLogger(__name__)
router = Router(name="backend_telegram")

STATUS_LABELS = {
    LeadStatus.NEW: "Yangi",
    LeadStatus.ACCEPTED: "Qabul qilindi",
    LeadStatus.CONTACTED: "Bog'lanildi",
    LeadStatus.CANCELLED: "Bekor qilindi",
    LeadStatus.DONE: "Yakunlandi",
}


def mini_app_keyboard() -> InlineKeyboardMarkup | None:
    """Build the single Mini App entry button."""
    if webapp_url_error(WEBAPP_URL):
        return None
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🚗 Katalogni ochish",
                    web_app=WebAppInfo(url=WEBAPP_URL),
                )
            ]
        ]
    )


@router.message(CommandStart())
async def start_command(message: Message) -> None:
    """Upsert the Telegram user and provide the Mini App button."""
    telegram_user = message.from_user
    if telegram_user is None:
        return
    full_name = telegram_user.full_name[:120]
    async with SessionFactory() as session:
        user = await session.scalar(select(User).where(User.tg_id == telegram_user.id))
        if user is None:
            session.add(
                User(
                    tg_id=telegram_user.id,
                    name=full_name,
                    username=telegram_user.username,
                    language=(telegram_user.language_code or "uz")[:8],
                )
            )
        else:
            user.name = full_name
            user.username = telegram_user.username
            user.language = (telegram_user.language_code or "uz")[:8]
        await session.commit()

    url_error = webapp_url_error(WEBAPP_URL)
    await message.answer(
        " ",
        reply_markup=ReplyKeyboardRemove(remove_keyboard=True),
    )
    await message.answer(
        f"Assalomu alaykum, {html.escape(full_name)}! 👋\n"
        "Buxara Avto Magnat rasmiy Volkswagen dileriga xush kelibsiz."
        + (
            "\n\nKatalog hozircha ochilmaydi: administrator WEBAPP_URL uchun "
            "ommaviy HTTPS tunnelni sozlab, botni qayta ishga tushirishi kerak."
            if url_error
            else ""
        ),
        reply_markup=mini_app_keyboard(),
    )


@router.message(Command("contact"))
async def contact_command(message: Message) -> None:
    """Show dealership contact details stored in application settings."""
    async with SessionFactory() as session:
        result = await session.execute(select(Setting.key, Setting.value))
        settings: dict[str, str] = {key: value for key, value in result.all()}

    address = settings.get(
        "address",
        "Buxoro shahar, Gazli shox ko'chasi, 500-uy. Mo'ljal: «Severniy» Guliston ko'prigi yonida.",
    )
    try:
        phones = json.loads(settings.get("phones", '["+998553054000","+998996284000"]'))
    except json.JSONDecodeError:
        logger.exception("Aloqa telefonlari sozlamasi noto'g'ri JSON")
        phones = []
    if not isinstance(phones, list):
        logger.error("Aloqa telefonlari sozlamasi ro'yxat emas")
        phones = []
    map_link = settings.get("map_link", "").strip()
    phone_text = "\n".join(f"☎️ {html.escape(str(phone))}" for phone in phones)
    map_text = (
        f'\n🗺️ <a href="{html.escape(map_link, quote=True)}">Xaritada ochish</a>'
        if map_link.startswith(("https://", "http://"))
        else ""
    )
    await message.answer(
        "<b>Buxara Avto Magnat (Volkswagen)</b>\n"
        f"📍 {html.escape(address)}\n{phone_text}{map_text}",
        parse_mode="HTML",
    )


@router.message(Command("cancel"))
async def cancel_command(message: Message) -> None:
    """Acknowledge cancel and return the user to the Mini App entry."""
    await message.answer(
        "Amal bekor qilindi. Katalogni davom ettirish uchun tugmani bosing.",
        reply_markup=mini_app_keyboard(),
    )


@router.message(Command("help"))
async def help_command(message: Message) -> None:
    """List supported bot commands."""
    await message.answer(
        "/start — katalogni ochish\n"
        "/contact — manzil va aloqa\n"
        "/cancel — joriy amalni bekor qilish\n"
        "/help — yordam"
        + (
            "\n\nAdmin buyruqlari: /stats, /leads"
            if message.from_user and message.from_user.id in ADMIN_IDS
            else ""
        ),
        reply_markup=mini_app_keyboard(),
    )


@router.message(Command("stats"))
async def stats_command(message: Message) -> None:
    """Show a short summary to authorized Telegram admins."""
    if message.from_user is None or message.from_user.id not in ADMIN_IDS:
        await message.answer("Bu buyruq faqat adminlar uchun.")
        return
    today = datetime.now(UTC).date()
    async with SessionFactory() as session:
        users_count = await session.scalar(select(func.count(User.id))) or 0
        leads_count = await session.scalar(select(func.count(Lead.id))) or 0
        today_count = (
            await session.scalar(
                select(func.count(Lead.id)).where(
                    func.date(Lead.created_at) == today.isoformat()
                )
            )
            or 0
        )
    await message.answer(
        f"📊 Qisqa statistika\n"
        f"Foydalanuvchilar: {users_count}\n"
        f"Arizalar jami: {leads_count}\n"
        f"Bugungi arizalar: {today_count}"
    )


@router.message(Command("leads"))
async def leads_command(message: Message) -> None:
    """Show the last ten leads to authorized Telegram admins."""
    if message.from_user is None or message.from_user.id not in ADMIN_IDS:
        await message.answer("Bu buyruq faqat adminlar uchun.")
        return
    async with SessionFactory() as session:
        result = await session.execute(select(Lead).order_by(Lead.id.desc()).limit(10))
        leads = result.scalars().all()
    if not leads:
        await message.answer("Hozircha arizalar yo'q.")
        return

    lines = ["📝 <b>Oxirgi arizalar</b>"]
    for lead in leads:
        status_name = STATUS_LABELS.get(lead.status, lead.status.value)
        lines.append(
            f"#{lead.id} · {html.escape(lead.name)} · {html.escape(lead.phone)} · "
            f"{html.escape(status_name)}"
        )
    await message.answer("\n".join(lines), parse_mode="HTML")


@router.callback_query(LeadStatusCallback.filter())
async def update_lead_status(
    callback: CallbackQuery,
    callback_data: LeadStatusCallback,
) -> None:
    """Update a lead from its admin notification inline buttons."""
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Bu amal faqat adminlar uchun.", show_alert=True)
        return
    try:
        status = LeadStatus(callback_data.status)
    except ValueError:
        await callback.answer("Ariza holati noto'g'ri.", show_alert=True)
        return

    async with SessionFactory() as session:
        lead = await session.get(Lead, callback_data.lead_id)
        if lead is None:
            await callback.answer("Ariza topilmadi.", show_alert=True)
            return
        previous_status = lead.status.value
        lead.status = status
        await write_audit_entry(
            session,
            action="telegram.lead_status",
            entity="lead",
            admin_user_id=None,
            entity_id=lead.id,
            before={"status": previous_status},
            after={
                "status": status.value,
                "telegram_admin_id": callback.from_user.id,
            },
        )
        await session.commit()
        summary = (
            f"📝 <b>Ariza #{lead.id}</b>\n"
            f"Ism: {html.escape(lead.name)}\n"
            f"Telefon: {html.escape(lead.phone)}\n"
            f"Holati: <b>{html.escape(STATUS_LABELS[status])}</b>"
        )

    if isinstance(callback.message, Message):
        try:
            await callback.message.edit_text(
                summary, parse_mode="HTML", reply_markup=None
            )
        except TelegramAPIError:
            logger.exception(
                "Lead status xabari tahrirlanmadi: %s", callback_data.lead_id
            )
    await callback.answer("Ariza holati yangilandi.")


@router.message(F.text)
async def unknown_text(message: Message) -> None:
    """Offer the Mini App when the user sends an unsupported text message."""
    await message.answer(
        "Bu xabar bo'yicha yordam bera olmadim. Avtomobillar katalogini oching:",
        reply_markup=mini_app_keyboard(),
    )
