"""Asosiy bot handlerlari."""

from pathlib import Path

from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, FSInputFile, Message, ReplyKeyboardRemove

from bot.db.database import save_user
from bot.keyboards.callbacks import CatalogCallback, TrimCallback
from bot.keyboards.inline import (
    car_keyboard,
    catalog_keyboard,
    trims_keyboard,
)
from bot.keyboards.reply import main_reply_keyboard
from bot.services.cars import get_car
from bot.utils.format import format_price, render_car_card

router = Router(name="core")


@router.message(CommandStart())
async def command_start(message: Message) -> None:
    """Foydalanuvchini bazaga saqlaydi va asosiy menyuni ko'rsatadi."""
    full_name = message.from_user.full_name if message.from_user else "hurmatli mijoz"
    await save_user(
        tg_id=message.from_user.id,
        name=message.from_user.full_name,
    )
    await message.answer(
        " ",
        reply_markup=ReplyKeyboardRemove(remove_keyboard=True),
    )
    await message.answer(
        f"Assalomu alaykum, {full_name}! 👋\n"
        "Buxara Avto Magnat rasmiy Volkswagen dileriga xush kelibsiz.",
        reply_markup=main_reply_keyboard(),
    )


@router.message(F.text == "🚗 Avtomobillar")
async def show_catalog(message: Message) -> None:
    await message.answer(
        "Katalog, taqqoslash va boshqa xizmatlar Mini App ichida.",
        reply_markup=main_reply_keyboard(),
    )


@router.callback_query(CatalogCallback.filter(F.action == "back"))
async def back_to_catalog(callback: CallbackQuery) -> None:
    """Katalogga qaytadi va mavjud xabarni tahrirlaydi."""
    await callback.answer()
    if callback.message is None:
        return
    await callback.message.edit_text(
        "Quyidagi mashinalardan birini tanlang:",
        reply_markup=catalog_keyboard(),
    )


@router.callback_query(CatalogCallback.filter(F.action == "car"))
async def show_car(
    callback: CallbackQuery,
    callback_data: CatalogCallback,
) -> None:
    """Tanlangan mashina kartasini ko'rsatadi."""
    await callback.answer()
    car = get_car(callback_data.car_id)
    if callback.message is None or car is None:
        await callback.answer("Mashina topilmadi.", show_alert=True)
        return

    card = render_car_card(car)
    photo = car.get("photo")

    if photo:
        photo_path = Path(__file__).resolve().parents[2] / photo
        if photo_path.is_file():
            await callback.message.delete()
            await callback.message.answer_photo(
                photo=FSInputFile(photo_path),
                caption=card,
                parse_mode="HTML",
                reply_markup=car_keyboard(car["id"]),
            )
            return

        await callback.message.edit_text(
            card,
            parse_mode="HTML",
            reply_markup=car_keyboard(car["id"]),
        )
        return

    await callback.message.edit_text(
        card,
        parse_mode="HTML",
        reply_markup=car_keyboard(car["id"]),
    )


@router.callback_query(TrimCallback.filter())
async def show_trims(
    callback: CallbackQuery,
    callback_data: TrimCallback,
) -> None:
    """Mashina komplektatsiyalari va narxlarini ko'rsatadi."""
    await callback.answer()
    car = get_car(callback_data.car_id)
    if callback.message is None or car is None:
        await callback.answer("Mashina topilmadi.", show_alert=True)
        return

    lines = [
        f"🧩 <b>{car['brand']} {car['model']} - komplektatsiyalar</b>",
        "Narxlar QQSni o'z ichiga oladi.",
        "",
    ]
    for trim in car["trims"]:
        lines.append(f"• <b>{trim['name']}</b>: {format_price(trim['price'])}")

    await callback.message.edit_text(
        "\n".join(lines),
        parse_mode="HTML",
        reply_markup=trims_keyboard(car["id"]),
    )


@router.message(F.text == "📍 Manzil va aloqa")
async def show_contact(message: Message) -> None:
    await message.answer(
        "Manzil va aloqa ma'lumotlarini Mini App ichidan ko'ring.",
        reply_markup=main_reply_keyboard(),
    )


@router.message(F.text == "🏠 Asosiy menyu")
async def show_main_menu(message: Message) -> None:
    await message.answer(
        "🏠 Asosiy menyu:",
        reply_markup=main_reply_keyboard(),
    )


@router.message()
async def unknown_message(message: Message, state: FSMContext) -> None:
    """Noma'lum matn yoki media uchun yordamchi javob yuboradi."""
    if await state.get_state() is not None:
        return
    await message.answer(
        "Bunday buyruqni aniqlay olmadim. "
        "Iltimos, quyidagi menyudan kerakli bo'limni tanlang.",
        reply_markup=main_reply_keyboard(),
    )
