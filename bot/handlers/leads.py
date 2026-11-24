"""Lead yuborish, admin xabari va admin lead amaliyotlari."""

from __future__ import annotations

import csv
import logging
import tempfile
from datetime import datetime
from pathlib import Path

from aiogram import F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, FSInputFile, Message

from bot.db.database import (
    count_recent_leads,
    get_all_leads,
    get_all_users,
    get_last_leads,
    get_stats,
    save_lead,
    update_lead_status,
)
from bot.keyboards.callbacks import (
    BroadcastCallback,
    CatalogCallback,
    LeadCallback,
    LeadStatusCallback,
)
from bot.keyboards.leads import (
    broadcast_confirmation_keyboard,
    comment_keyboard,
    lead_cars_keyboard,
    lead_confirmation_keyboard,
    lead_status_keyboard,
    lead_trims_keyboard,
)
from bot.keyboards.reply import main_reply_keyboard
from bot.services.cars import get_car
from bot.services.leads import LEAD_TYPE_LABELS, normalize_phone
from config import ADMIN_IDS

router = Router(name="leads")
logger = logging.getLogger("bot.leads")


class LeadStates(StatesGroup):
    choosing_type = State()
    choosing_car = State()
    choosing_trim = State()
    entering_name = State()
    entering_phone = State()
    entering_comment = State()
    confirming = State()


class BroadcastStates(StatesGroup):
    entering_message = State()
    confirming = State()


def get_admin_ids() -> set[int]:
    return set(ADMIN_IDS)


def is_admin(user_id: int | None) -> bool:
    return user_id is not None and user_id in get_admin_ids()


async def start_lead_flow(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(
        "Arizani Mini App ichida qoldiring.",
        reply_markup=main_reply_keyboard(),
    )


@router.message(F.text == "📝 Ariza qoldirish")
async def lead_from_menu(message: Message, state: FSMContext) -> None:
    await start_lead_flow(message, state)


@router.callback_query(CatalogCallback.filter(F.action == "lead"))
async def lead_from_car(
    callback: CallbackQuery,
    callback_data: CatalogCallback,
    state: FSMContext,
) -> None:
    await callback.answer()
    if callback.message is None:
        return
    await state.clear()
    await callback.message.edit_text(
        "Arizani Mini App ichida qoldiring.",
        reply_markup=main_reply_keyboard(),
    )


@router.callback_query(
    LeadCallback.filter(F.action == "type"),
    LeadStates.choosing_type,
)
async def lead_choose_type(
    callback: CallbackQuery,
    callback_data: LeadCallback,
    state: FSMContext,
) -> None:
    await callback.answer()
    await state.update_data(lead_type=callback_data.trim_name)
    data = await state.get_data()
    prefilled = data.get("prefilled_car_id")

    if prefilled:
        car = get_car(prefilled)
        if car:
            await state.update_data(car_id=prefilled)
            await state.set_state(LeadStates.choosing_trim)
            if callback.message:
                await callback.message.edit_text(
                    f"<b>{car['brand']} {car['model']}</b>\n"
                    "Komplektatsiyani tanlang:",
                    parse_mode="HTML",
                    reply_markup=lead_trims_keyboard(prefilled),
                )
            return

    await state.set_state(LeadStates.choosing_car)
    if callback.message:
        await callback.message.edit_text(
            "Avtomobilni tanlang:",
            reply_markup=lead_cars_keyboard(),
        )


@router.callback_query(
    LeadCallback.filter(F.action == "car"),
    LeadStates.choosing_car,
)
async def lead_choose_car(
    callback: CallbackQuery,
    callback_data: LeadCallback,
    state: FSMContext,
) -> None:
    await callback.answer()
    car = get_car(callback_data.car_id)
    if callback.message is None or car is None:
        await callback.answer("Mashina topilmadi.", show_alert=True)
        return
    await state.update_data(car_id=callback_data.car_id)
    await state.set_state(LeadStates.choosing_trim)
    await callback.message.edit_text(
        f"<b>{car['brand']} {car['model']}</b>\n"
        "Komplektatsiyani tanlang:",
        parse_mode="HTML",
        reply_markup=lead_trims_keyboard(car["id"]),
    )


@router.callback_query(
    LeadCallback.filter(F.action == "trim"),
    LeadStates.choosing_trim,
)
async def lead_choose_trim(
    callback: CallbackQuery,
    callback_data: LeadCallback,
    state: FSMContext,
) -> None:
    await callback.answer()
    await state.update_data(trim_name=callback_data.trim_name)
    await state.set_state(LeadStates.entering_name)
    if callback.message:
        await callback.message.edit_text(
            "Ism va familiyangizni kiriting:",
        )


@router.message(LeadStates.entering_name)
async def lead_enter_name(message: Message, state: FSMContext) -> None:
    name = (message.text or "").strip()
    if len(name) < 2:
        await message.answer("Iltimos, ism va familiyangizni to'g'ri kiriting.")
        return
    await state.update_data(name=name)
    await state.set_state(LeadStates.entering_phone)
    await message.answer(
        "Telefon raqamingizni kiriting. Masalan: +998 90 123 45 67",
    )


@router.message(LeadStates.entering_phone, F.contact)
async def lead_phone_contact(message: Message, state: FSMContext) -> None:
    if message.contact is None:
        return
    phone = normalize_phone(message.contact.phone_number)
    if phone is None:
        await message.answer(
            "Telefon +998 formati bo'lishi kerak.",
        )
        return
    await state.update_data(phone=phone)
    await state.set_state(LeadStates.entering_comment)
    await message.answer(
        "Qo'shimcha izohingizni yozing.",
        reply_markup=main_reply_keyboard(),
    )
    await message.answer(
        "Izoh bo‘lmasa, tugmani bosing:",
        reply_markup=comment_keyboard(),
    )


@router.message(LeadStates.entering_phone)
async def lead_phone_manual(message: Message, state: FSMContext) -> None:
    phone = normalize_phone(message.text or "")
    if phone is None:
        await message.answer(
            "Telefon raqam noto'g'ri. Misol: +998 90 123 45 67",
        )
        return
    await state.update_data(phone=phone)
    await state.set_state(LeadStates.entering_comment)
    await message.answer(
        "Qo'shimcha izohingizni yozing.",
        reply_markup=main_reply_keyboard(),
    )
    await message.answer(
        "Izoh bo‘lmasa, tugmani bosing:",
        reply_markup=comment_keyboard(),
    )


@router.message(LeadStates.entering_comment)
async def lead_comment(message: Message, state: FSMContext) -> None:
    comment = (message.text or "").strip()
    if len(comment) > 1000:
        await message.answer("Izoh 1000 belgidan oshmasligi kerak.")
        return
    await state.update_data(comment=comment or None)
    await lead_confirm(message, state)


@router.callback_query(
    LeadCallback.filter(F.action == "skip_comment"),
)
async def lead_skip_comment(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    await callback.answer()
    await state.update_data(comment=None)
    await lead_confirm(callback.message, state)


async def lead_confirm(message: Message | None, state: FSMContext) -> None:
    if message is None:
        return
    data = await state.get_data()
    car = get_car(data["car_id"])
    if car is None:
        await message.answer("Mashina topilmadi. Iltimos, arizani qayta boshlang.")
        await state.clear()
        return

    lead_type = LEAD_TYPE_LABELS[data["lead_type"]]
    lines = [
        "📝 <b>Ariza ma'lumotlarini tekshiring</b>",
        f"Murojaat turi: <b>{lead_type}</b>",
        f"Mashina: <b>{car['brand']} {car['model']}</b>",
        f"Komplektatsiya: <b>{data['trim_name']}</b>",
        f"Ism: <b>{data['name']}</b>",
        f"Telefon: <b>{data['phone']}</b>",
        f"Izoh: <b>{data.get('comment') or 'Yo‘q'}</b>",
    ]
    await state.set_state(LeadStates.confirming)
    await message.answer(
        "\n".join(lines),
        parse_mode="HTML",
        reply_markup=lead_confirmation_keyboard(),
    )


@router.callback_query(
    LeadCallback.filter(F.action == "confirm"),
    LeadStates.confirming,
)
async def lead_confirm_send(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    await callback.answer()
    if callback.message is None or callback.from_user is None:
        return

    data = await state.get_data()
    recent = await count_recent_leads(callback.from_user.id)
    if recent >= 3:
        await callback.message.edit_text(
            "So'nggi 1 soat ichida ariza limitiga yetildi.",
        )
        await state.clear()
        return

    lead_id = await save_lead(
        tg_id=callback.from_user.id,
        name=data["name"],
        phone=data["phone"],
        car_id=data["car_id"],
        trim_name=data["trim_name"],
        lead_type=data["lead_type"],
        comment=data.get("comment"),
    )
    await state.clear()
    await callback.message.edit_text(
        "Arizangiz qabul qilindi, tez orada bog'lanamiz.",
    )

    car = get_car(data["car_id"])
    admin_text = (
        "🆕 <b>Yangi ariza</b>\n"
        f"ID: #{lead_id}\n"
        f"Turi: {LEAD_TYPE_LABELS[data['lead_type']]}\n"
        f"Mashina: {car['brand']} {car['model']} — {data['trim_name']}\n"
        f"Ism: {data['name']}\n"
        f"Telefon: {data['phone']}\n"
        f"Izoh: {data.get('comment') or 'Yo‘q'}\n"
        f"Telegram ID: <code>{callback.from_user.id}</code>"
    )
    for admin_id in get_admin_ids():
        try:
            await callback.bot.send_message(
                chat_id=admin_id,
                text=admin_text,
                parse_mode="HTML",
                reply_markup=lead_status_keyboard(lead_id),
            )
        except Exception:
            logger.exception("Admin %s ga lead xabari yuborilmadi", admin_id)


@router.callback_query(
    LeadCallback.filter(F.action == "cancel"),
    LeadStates.confirming,
)
async def lead_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.clear()
    if callback.message:
        await callback.message.edit_text("Ariza bekor qilindi.")


@router.callback_query(LeadStatusCallback.filter())
async def admin_update_lead_status(
    callback: CallbackQuery,
    callback_data: LeadStatusCallback,
) -> None:
    if not is_admin(callback.from_user.id if callback.from_user else None):
        await callback.answer("Bu amal faqat admin uchun.", show_alert=True)
        return

    changed = await update_lead_status(
        lead_id=callback_data.lead_id,
        status=callback_data.status,
    )
    if not changed:
        await callback.answer("Lead topilmadi.", show_alert=True)
        return

    labels = {
        "accepted": "✅ Qabul qilindi",
        "contacted": "📞 Bog'lanildi",
        "cancelled": "❌ Bekor qilindi",
    }
    await callback.answer(labels[callback_data.status])
    if callback.message:
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.message.reply(
            f"Lead #{callback_data.lead_id} holati: "
            f"<b>{labels[callback_data.status]}</b>",
            parse_mode="HTML",
        )


@router.message(Command("stats"))
async def admin_stats(message: Message) -> None:
    if not is_admin(message.from_user.id if message.from_user else None):
        await message.answer("Bu buyruq faqat administrator uchun.")
        return

    stats = await get_stats()
    lines = [
        "📊 <b>Bot statistikasi</b>",
        f"Foydalanuvchilar: <b>{stats['users']}</b>",
        f"Bugungi leadlar: <b>{stats['leads_today']}</b>",
        f"Hafta leadlari: <b>{stats['leads_week']}</b>",
        f"Jami leadlar: <b>{stats['leads_total']}</b>",
    ]
    if stats["popular_cars"]:
        lines.append("\n🚗 <b>Eng ko'p so'ralgan mashinalar:</b>")
        for car_id, requests in stats["popular_cars"]:
            car = get_car(car_id)
            name = f"{car['brand']} {car['model']}" if car else car_id
            lines.append(f"• {name}: {requests}")
    await message.answer("\n".join(lines), parse_mode="HTML")


@router.message(Command("leads"))
async def admin_leads(message: Message) -> None:
    if not is_admin(message.from_user.id if message.from_user else None):
        await message.answer("Bu buyruq faqat administrator uchun.")
        return

    leads = await get_last_leads(10)
    if not leads:
        await message.answer("Hozircha leadlar yo'q.")
        return

    status_labels = {
        "new": "Yangi",
        "accepted": "Qabul qilindi",
        "contacted": "Bog'lanildi",
        "cancelled": "Bekor qilindi",
    }
    chunks = ["📋 <b>Oxirgi 10 ta lead:</b>"]
    for lead in leads:
        lead_id, _tg_id, name, phone, car_id, trim_name, lead_type, _comment, status, created = lead
        car = get_car(car_id)
        car_name = f"{car['brand']} {car['model']}" if car else car_id
        chunks.append(
            f"\n#{lead_id} — <b>{status_labels.get(status, status)}</b>\n"
            f"{car_name} — {trim_name}\n"
            f"{name} | {phone}\n"
            f"Turi: {LEAD_TYPE_LABELS.get(lead_type, lead_type)} | "
            f"{created}"
        )
    await message.answer("\n".join(chunks), parse_mode="HTML")


@router.message(Command("broadcast"))
async def admin_broadcast_start(
    message: Message,
    state: FSMContext,
) -> None:
    if not is_admin(message.from_user.id if message.from_user else None):
        await message.answer("Bu buyruq faqat administrator uchun.")
        return
    await state.clear()
    await state.set_state(BroadcastStates.entering_message)
    await message.answer(
        "Barcha foydalanuvchilarga yuboriladigan xabar matnini kiriting:"
    )


@router.message(BroadcastStates.entering_message)
async def admin_broadcast_message(
    message: Message,
    state: FSMContext,
) -> None:
    text = (message.text or "").strip()
    if not text:
        await message.answer("Xabar matni bo'sh bo'lishi mumkin emas.")
        return
    if len(text) > 4000:
        await message.answer("Xabar 4000 belgidan oshmasligi kerak.")
        return
    await state.update_data(text=text)
    await state.set_state(BroadcastStates.confirming)
    await message.answer(
        "Xabarning mazmuni:\n\n"
        f"{text}\n\n"
        "Barcha foydalanuvchilarga yuborilsinmi?",
        reply_markup=broadcast_confirmation_keyboard(),
    )


@router.callback_query(
    BroadcastCallback.filter(F.action == "send"),
    BroadcastStates.confirming,
)
async def admin_broadcast_send(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    if not is_admin(callback.from_user.id if callback.from_user else None):
        await callback.answer("Bu amal faqat admin uchun.", show_alert=True)
        return
    if callback.message is None:
        return

    data = await state.get_data()
    text = data["text"]
    await state.clear()
    users = await get_all_users()
    sent = 0
    blocked = 0
    for tg_id in users:
        try:
            await callback.bot.send_message(chat_id=tg_id, text=text)
            sent += 1
        except TelegramAPIError as exc:
            blocked += 1
            logger.warning("Broadcast %s ga yuborilmadi: %s", tg_id, exc)

    await callback.message.edit_text(
        f"Broadcast tugadi.\nYuborildi: {sent}\nYuborilmadi: {blocked}"
    )


@router.callback_query(
    BroadcastCallback.filter(F.action == "cancel"),
    BroadcastStates.confirming,
)
async def admin_broadcast_cancel(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    await callback.answer()
    await state.clear()
    if callback.message:
        await callback.message.edit_text("Broadcast bekor qilindi.")


@router.message(Command("export"))
async def admin_export(message: Message) -> None:
    if not is_admin(message.from_user.id if message.from_user else None):
        await message.answer("Bu buyruq faqat administrator uchun.")
        return

    leads = await get_all_leads()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = Path(tempfile.gettempdir()) / f"buxara_leads_{timestamp}.csv"
    try:
        with path.open("w", encoding="utf-8-sig", newline="") as file:
            writer = csv.writer(file)
            writer.writerow([
                "id",
                "tg_id",
                "name",
                "phone",
                "car_id",
                "trim",
                "type",
                "comment",
                "status",
                "created_at",
            ])
            writer.writerows(leads)
        await message.answer_document(
            FSInputFile(path, filename=f"leads_{timestamp}.csv"),
            caption=f"Jami leadlar: {len(leads)}",
        )
    finally:
        path.unlink(missing_ok=True)
