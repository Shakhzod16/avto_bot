"""Telegram notifications triggered by public API lead creation."""

from __future__ import annotations

import html
import logging

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from backend.app.bot.callbacks import LeadStatusCallback
from backend.app.bot.handlers import STATUS_LABELS
from backend.app.core.config import ADMIN_IDS
from backend.app.db.session import SessionFactory
from backend.app.models import Lead, LeadStatus

logger = logging.getLogger(__name__)
LEAD_TYPE_LABELS = {
    "test_drive": "Test-drayv",
    "buy": "Sotib olish",
    "callback": "Qayta qo'ng'iroq",
}


def _status_keyboard(lead_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Qabul qilindi",
                    callback_data=LeadStatusCallback(
                        lead_id=lead_id,
                        status=LeadStatus.ACCEPTED.value,
                    ).pack(),
                ),
                InlineKeyboardButton(
                    text="📞 Bog'lanildi",
                    callback_data=LeadStatusCallback(
                        lead_id=lead_id,
                        status=LeadStatus.CONTACTED.value,
                    ).pack(),
                ),
                InlineKeyboardButton(
                    text="❌ Bekor qilindi",
                    callback_data=LeadStatusCallback(
                        lead_id=lead_id,
                        status=LeadStatus.CANCELLED.value,
                    ).pack(),
                ),
            ]
        ]
    )


async def notify_new_lead(bot: Bot, lead_id: int) -> None:
    """Notify configured admins and the customer, without undoing a saved lead."""
    async with SessionFactory() as session:
        result = await session.execute(
            select(Lead)
            .where(Lead.id == lead_id)
            .options(
                selectinload(Lead.user),
                selectinload(Lead.car),
                selectinload(Lead.trim),
            )
        )
        lead = result.scalar_one_or_none()
        if lead is None:
            logger.error("Yangi ariza Telegram xabari uchun topilmadi: %s", lead_id)
            return

        car_name = (
            f"{lead.car.brand} {lead.car.model}"
            if lead.car is not None
            else "Tanlanmagan"
        )
        trim_name = lead.trim.name if lead.trim is not None else "Tanlanmagan"
        lead_text = (
            f"🆕 <b>Yangi ariza #{lead.id}</b>\n"
            f"Ism: {html.escape(lead.name)}\n"
            f"Telefon: {html.escape(lead.phone)}\n"
            f"Avtomobil: {html.escape(car_name)}\n"
            f"Komplektatsiya: {html.escape(trim_name)}\n"
            f"Turi: {html.escape(LEAD_TYPE_LABELS[lead.type.value])}\n"
            f"Izoh: {html.escape(lead.comment or '—')}\n"
            f"Holati: {html.escape(STATUS_LABELS[lead.status])}"
        )
        customer_tg_id = lead.user.tg_id if lead.user is not None else None
        keyboard = _status_keyboard(lead.id)

    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(
                admin_id,
                lead_text,
                parse_mode="HTML",
                reply_markup=keyboard,
            )
        except TelegramAPIError:
            logger.exception("Admin %s ga ariza xabari yuborilmadi", admin_id)

    if customer_tg_id is not None:
        try:
            await bot.send_message(
                customer_tg_id,
                "Arizangiz qabul qilindi, tez orada bog'lanamiz.",
            )
        except TelegramAPIError:
            logger.exception("Mijozga ariza tasdig'i yuborilmadi: %s", customer_tg_id)
