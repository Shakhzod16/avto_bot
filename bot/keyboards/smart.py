"""Smart bo'limlar uchun inline klaviaturalar."""

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.keyboards.callbacks import (
    BudgetCallback,
    CompareCallback,
    CreditCallback,
    FilterCallback,
)
from bot.services.cars import get_all_cars


def budget_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="300 mln gacha",
                    callback_data=BudgetCallback(action="range", max_price=300000000).pack(),
                )
            ],
            [
                InlineKeyboardButton(
                    text="300-500 mln",
                    callback_data=BudgetCallback(action="range", min_price=300000000, max_price=500000000).pack(),
                )
            ],
            [
                InlineKeyboardButton(
                    text="500-700 mln",
                    callback_data=BudgetCallback(action="range", min_price=500000000, max_price=700000000).pack(),
                )
            ],
            [
                InlineKeyboardButton(
                    text="700 mln dan",
                    callback_data=BudgetCallback(action="range", min_price=700000000, max_price=100000000000).pack(),
                )
            ],
            [
                InlineKeyboardButton(
                    text="✍️ O'z raqamimni kiriting",
                    callback_data=BudgetCallback(action="custom").pack(),
                )
            ],
        ]
    )


def filter_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="SUV", callback_data=FilterCallback(kind="body", value="SUV").pack()),
                InlineKeyboardButton(text="Sedan", callback_data=FilterCallback(kind="body", value="Sedan").pack()),
            ],
            [
                InlineKeyboardButton(text="AWD", callback_data=FilterCallback(kind="drive", value="AWD").pack()),
                InlineKeyboardButton(text="FWD", callback_data=FilterCallback(kind="drive", value="FWD").pack()),
            ],
        ]
    )


def compare_keyboard(exclude_id: str = "") -> InlineKeyboardMarkup:
    rows = []
    for car in get_all_cars():
        if car["id"] == exclude_id:
            continue
        rows.append([
            InlineKeyboardButton(
                text=f"{car['brand']} {car['model']}",
                callback_data=CompareCallback(action="pick", car_id=car["id"]).pack(),
            )
        ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def credit_cars_keyboard() -> InlineKeyboardMarkup:
    rows = []
    for car in get_all_cars():
        rows.append([
            InlineKeyboardButton(
                text=f"{car['brand']} {car['model']}",
                callback_data=CreditCallback(action="car", car_id=car["id"]).pack(),
            )
        ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def credit_trims_keyboard(car_id: str) -> InlineKeyboardMarkup:
    car = next((item for item in get_all_cars() if item["id"] == car_id), None)
    rows = []
    if car:
        for trim in car["trims"]:
            if trim["price"] is not None:
                rows.append([
                    InlineKeyboardButton(
                        text=trim["name"],
                        callback_data=CreditCallback(
                            action="trim",
                            car_id=car_id,
                            trim_name=trim["name"],
                        ).pack(),
                    )
                ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def down_payment_keyboard(car_id: str, trim_name: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[
            InlineKeyboardButton(
                text=f"{percent}%",
                callback_data=CreditCallback(
                    action="down",
                    car_id=car_id,
                    trim_name=trim_name,
                    value=percent,
                ).pack(),
            )
            for percent in (20, 30, 40, 50)
        ]]
    )


def term_keyboard(car_id: str, trim_name: str, down_percent: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[
            InlineKeyboardButton(
                text=f"{months} oy",
                callback_data=CreditCallback(
                    action="term",
                    car_id=car_id,
                    trim_name=trim_name,
                    value=months,
                    down_percent=down_percent,
                ).pack(),
            )
            for months in (12, 24, 36, 48, 60)
        ]]
    )
