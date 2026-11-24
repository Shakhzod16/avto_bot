"""Umumiy FSM bekor qilish handleri."""

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from bot.keyboards.reply import main_reply_keyboard

router = Router(name="common")


async def cancel_and_show_menu(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(
        "Amal bekor qilindi. Asosiy menyuga qaytdingiz.",
        reply_markup=main_reply_keyboard(),
    )


@router.message(Command("cancel"))
async def cancel_command(message: Message, state: FSMContext) -> None:
    await cancel_and_show_menu(message, state)


@router.message(F.text.casefold().in_({"bekor qilish", "cancel", "/cancel"}))
async def cancel_text(message: Message, state: FSMContext) -> None:
    await cancel_and_show_menu(message, state)
