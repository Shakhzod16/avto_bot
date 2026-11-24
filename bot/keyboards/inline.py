"""Mashinalar katalogi uchun inline klaviaturalar."""

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.keyboards.callbacks import CatalogCallback, TrimCallback
from bot.services.cars import get_all_cars


def catalog_keyboard() -> InlineKeyboardMarkup:
    """Sakkiz mashinani alohida tugmalarda ko'rsatadi."""
    buttons = [
        [
            InlineKeyboardButton(
                text=f"{car['brand']} {car['model']}",
                callback_data=CatalogCallback(
                    action="car",
                    car_id=car["id"],
                ).pack(),
            )
        ]
        for car in get_all_cars()
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def car_keyboard(car_id: str) -> InlineKeyboardMarkup:
    """Tanlangan mashina uchun amallar tugmalarini qaytaradi."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Komplektatsiyalar",
                    callback_data=TrimCallback(car_id=car_id).pack(),
                )
            ],
            [
                InlineKeyboardButton(
                    text="📝 Ariza qoldirish",
                    callback_data=CatalogCallback(
                        action="lead",
                        car_id=car_id,
                    ).pack(),
                )
            ],
            [
                InlineKeyboardButton(
                    text="◀️ Orqaga",
                    callback_data=CatalogCallback(action="back").pack(),
                )
            ],
        ]
    )


def trims_keyboard(car_id: str) -> InlineKeyboardMarkup:
    """Komplektatsiyalar xabari uchun orqaga tugmasini qaytaradi."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="◀️ Mashina kartasiga qaytish",
                    callback_data=CatalogCallback(
                        action="car",
                        car_id=car_id,
                    ).pack(),
                )
            ]
        ]
    )
