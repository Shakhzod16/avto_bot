"""Ariza va admin leadlar uchun inline klaviaturalar."""

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)

from bot.keyboards.callbacks import (
    BroadcastCallback,
    LeadCallback,
    LeadStatusCallback,
)
from bot.services.cars import get_all_cars


def lead_type_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🚘 Test-drayv",
                    callback_data=LeadCallback(action="type", trim_name="test_drive").pack(),
                )
            ],
            [
                InlineKeyboardButton(
                    text="🛒 Sotib olish",
                    callback_data=LeadCallback(action="type", trim_name="buy").pack(),
                )
            ],
            [
                InlineKeyboardButton(
                    text="📞 Qayta qo'ng'iroq",
                    callback_data=LeadCallback(action="type", trim_name="callback").pack(),
                )
            ],
        ]
    )


def lead_cars_keyboard() -> InlineKeyboardMarkup:
    rows = []
    for car in get_all_cars():
        rows.append([
            InlineKeyboardButton(
                text=f"{car['brand']} {car['model']}",
                callback_data=LeadCallback(action="car", car_id=car["id"]).pack(),
            )
        ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def lead_trims_keyboard(car_id: str) -> InlineKeyboardMarkup:
    car = next((item for item in get_all_cars() if item["id"] == car_id), None)
    rows = []
    if car:
        for trim in car["trims"]:
            rows.append([
                InlineKeyboardButton(
                    text=trim["name"],
                    callback_data=LeadCallback(
                        action="trim",
                        car_id=car_id,
                        trim_name=trim["name"],
                    ).pack(),
                )
            ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def comment_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Izohsiz davom etish",
                    callback_data=LeadCallback(action="skip_comment").pack(),
                )
            ]
        ]
    )


def lead_confirmation_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Arizani yuborish",
                    callback_data=LeadCallback(action="confirm").pack(),
                )
            ],
            [
                InlineKeyboardButton(
                    text="❌ Bekor qilish",
                    callback_data=LeadCallback(action="cancel").pack(),
                )
            ],
        ]
    )


def lead_status_keyboard(lead_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Qabul qilindi",
                    callback_data=LeadStatusCallback(
                        lead_id=lead_id,
                        status="accepted",
                    ).pack(),
                )
            ],
            [
                InlineKeyboardButton(
                    text="📞 Bog'lanildi",
                    callback_data=LeadStatusCallback(
                        lead_id=lead_id,
                        status="contacted",
                    ).pack(),
                )
            ],
            [
                InlineKeyboardButton(
                    text="❌ Bekor qilindi",
                    callback_data=LeadStatusCallback(
                        lead_id=lead_id,
                        status="cancelled",
                    ).pack(),
                )
            ],
        ]
    )


def broadcast_confirmation_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Yuborish",
                    callback_data=BroadcastCallback(action="send").pack(),
                )
            ],
            [
                InlineKeyboardButton(
                    text="❌ Bekor qilish",
                    callback_data=BroadcastCallback(action="cancel").pack(),
                )
            ],
        ]
    )
