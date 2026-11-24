"""Narx, filter, taqqoslash va kredit handlerlari."""

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from bot.keyboards.callbacks import (
    BudgetCallback,
    CompareCallback,
    CreditCallback,
    FilterCallback,
)
from bot.keyboards.reply import main_reply_keyboard
from bot.keyboards.smart import (
    compare_keyboard,
    credit_trims_keyboard,
    down_payment_keyboard,
    filter_keyboard,
    term_keyboard,
)
from bot.services.calculations import calculate_monthly_payment, get_price_range
from bot.services.cars import (
    filter_by_body_type,
    filter_by_drive,
    get_all_cars,
    get_car,
    search_by_budget,
)
from bot.utils.format import format_price
from config import ANNUAL_INTEREST_RATE

router = Router(name="smart")


class BudgetStates(StatesGroup):
    waiting_custom_budget = State()


class CompareStates(StatesGroup):
    waiting_first = State()
    waiting_second = State()


class CreditStates(StatesGroup):
    waiting_down_payment = State()
    waiting_term = State()


def format_result_cars(cars: tuple[dict, ...]) -> str:
    if not cars:
        return "Tanlangan shartlarga mos mashina topilmadi."

    lines = ["🚗 <b>Topilgan mashinalar:</b>", ""]
    for car in cars:
        minimum, maximum = get_price_range(car)
        if minimum is None:
            continue
        price_text = (
            format_price(minimum)
            if minimum == maximum
            else f"{format_price(minimum)} — {format_price(maximum)}"
        )
        lines.append(f"• <b>{car['brand']} {car['model']}</b>: {price_text}")

    unpriced = [car for car in cars if get_price_range(car)[0] is None]
    if unpriced:
        lines.extend(["", "ℹ️ <b>Hozir narxi belgilanmagan:</b>"])
        for car in unpriced:
            lines.append(
                f"• {car['brand']} {car['model']} — "
                "Narxi keyinroq e'lon qilinadi"
            )
    return "\n".join(lines)


@router.message(F.text == "💰 Narx bo'yicha qidirish")
async def budget_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(
        "Narx bo'yicha qidiruv Mini App ichida mavjud.",
        reply_markup=main_reply_keyboard(),
    )


@router.callback_query(BudgetCallback.filter(F.action == "custom"))
async def budget_custom(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.set_state(BudgetStates.waiting_custom_budget)
    if callback.message:
        await callback.message.edit_text(
            "Maksimal byudjetingizni so'mda kiriting.\n"
            "Masalan: 300000000 yoki 300 mln",
        )


@router.message(BudgetStates.waiting_custom_budget)
async def budget_custom_value(message: Message, state: FSMContext) -> None:
    raw = (message.text or "").lower().replace(" ", "").replace("\u00a0", "")
    multiplier = 1_000_000 if "mln" in raw else 1
    digits = "".join(character for character in raw if character.isdigit())
    if not digits:
        await message.answer("Iltimos, son kiriting. Masalan: 300 mln.")
        return

    maximum = int(digits) * multiplier
    cars = search_by_budget(0, maximum)
    await state.clear()
    await message.answer(
        format_result_cars(cars),
        parse_mode="HTML",
        reply_markup=filter_keyboard(),
    )


@router.callback_query(BudgetCallback.filter(F.action == "range"))
async def budget_range(
    callback: CallbackQuery,
    callback_data: BudgetCallback,
    state: FSMContext,
) -> None:
    await callback.answer()
    await state.clear()
    cars = search_by_budget(callback_data.min_price, callback_data.max_price)
    if callback.message:
        await callback.message.edit_text(
            format_result_cars(cars),
            parse_mode="HTML",
            reply_markup=filter_keyboard(),
        )


@router.callback_query(FilterCallback.filter())
async def apply_filter(
    callback: CallbackQuery,
    callback_data: FilterCallback,
) -> None:
    await callback.answer()
    if callback_data.kind == "body":
        if callback_data.value == "SUV":
            cars = tuple(
                car for car in get_all_cars()
                if car["body_type"].upper().endswith("SUV")
            )
        else:
            cars = filter_by_body_type("D-sedan") + filter_by_body_type("C-sedan")
    else:
        drive = "To'liq uzatma (AWD)" if callback_data.value == "AWD" else "Old uzatma (FWD)"
        cars = filter_by_drive(drive)

    if callback.message:
        await callback.message.edit_text(
            format_result_cars(cars),
            parse_mode="HTML",
            reply_markup=filter_keyboard(),
        )


@router.message(F.text == "⚖️ Taqqoslash")
async def compare_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(
        "Avtomobillarni Mini App ichida taqqoslashingiz mumkin.",
        reply_markup=main_reply_keyboard(),
    )


@router.callback_query(
    CompareCallback.filter(F.action == "pick"),
    CompareStates.waiting_first,
)
async def compare_first(
    callback: CallbackQuery,
    callback_data: CompareCallback,
    state: FSMContext,
) -> None:
    await callback.answer()
    await state.update_data(first_id=callback_data.car_id)
    await state.set_state(CompareStates.waiting_second)
    if callback.message:
        await callback.message.edit_text(
            "Endi ikkinchi mashinani tanlang:",
            reply_markup=compare_keyboard(exclude_id=callback_data.car_id),
        )


@router.callback_query(
    CompareCallback.filter(F.action == "pick"),
    CompareStates.waiting_second,
)
async def compare_second(
    callback: CallbackQuery,
    callback_data: CompareCallback,
    state: FSMContext,
) -> None:
    await callback.answer()
    data = await state.get_data()
    if callback_data.car_id == data["first_id"]:
        await callback.answer("Bir xil mashinani tanlab bo'lmaydi.", show_alert=True)
        return

    first = get_car(data["first_id"])
    second = get_car(callback_data.car_id)
    if callback.message is None or first is None or second is None:
        await callback.answer("Mashina topilmadi.", show_alert=True)
        return

    def row(label: str, left: str, right: str) -> str:
        return f"{label}: <b>{left}</b>  |  <b>{right}</b>"

    first_min, first_max = get_price_range(first)
    second_min, second_max = get_price_range(second)

    def range_text(minimum: int | None, maximum: int | None) -> str:
        if minimum is None:
            return "Narxi keyinroq e'lon qilinadi"
        if minimum == maximum:
            return format_price(minimum)
        return f"{format_price(minimum)} - {format_price(maximum)}"

    text = "\n".join([
        "⚖️ <b>Mashinalarni taqqoslash</b>",
        (
            f"<b>{first['brand']} {first['model']}</b>  |  "
            f"<b>{second['brand']} {second['model']}</b>"
        ),
        "",
        row("Dvigatel", first["engine"], second["engine"]),
        row("Quvvati", f"{first['power_hp']} o.k.", f"{second['power_hp']} o.k."),
        row("Uzatma", first["drive"], second["drive"]),
        row("Transmissiya", first["transmission"], second["transmission"]),
        row("O'rindiqlar", str(first["seats"]), str(second["seats"])),
        row("Narx", range_text(first_min, first_max), range_text(second_min, second_max)),
    ])
    await state.clear()
    await callback.message.edit_text(text, parse_mode="HTML")


@router.message(F.text == "🧮 Kredit kalkulyatori")
async def credit_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(
        "Kredit kalkulyatori Mini App ichida mavjud.",
        reply_markup=main_reply_keyboard(),
    )


@router.callback_query(CreditCallback.filter(F.action == "car"))
async def credit_car(
    callback: CallbackQuery,
    callback_data: CreditCallback,
) -> None:
    await callback.answer()
    car = get_car(callback_data.car_id)
    if callback.message is None or car is None:
        await callback.answer("Mashina topilmadi.", show_alert=True)
        return
    await callback.message.edit_text(
        f"<b>{car['brand']} {car['model']}</b>\n"
        "Komplektatsiyani tanlang:",
        parse_mode="HTML",
        reply_markup=credit_trims_keyboard(car["id"]),
    )


@router.callback_query(CreditCallback.filter(F.action == "trim"))
async def credit_trim(
    callback: CallbackQuery,
    callback_data: CreditCallback,
) -> None:
    await callback.answer()
    car = get_car(callback_data.car_id)
    if callback.message is None or car is None:
        await callback.answer("Mashina topilmadi.", show_alert=True)
        return
    await callback.message.edit_text(
        f"{car['brand']} {car['model']} — {callback_data.trim_name}\n"
        "Boshlang'ich to'lov foizini tanlang:",
        reply_markup=down_payment_keyboard(callback_data.car_id, callback_data.trim_name),
    )


@router.callback_query(CreditCallback.filter(F.action == "down"))
async def credit_down(
    callback: CallbackQuery,
    callback_data: CreditCallback,
) -> None:
    await callback.answer()
    if callback.message:
        await callback.message.edit_text(
            "Kredit muddatini tanlang:",
            reply_markup=term_keyboard(
                callback_data.car_id,
                callback_data.trim_name,
                callback_data.value,
            ),
        )


@router.callback_query(CreditCallback.filter(F.action == "term"))
async def credit_result(
    callback: CallbackQuery,
    callback_data: CreditCallback,
) -> None:
    await callback.answer()
    car = get_car(callback_data.car_id)
    if callback.message is None or car is None:
        await callback.answer("Mashina topilmadi.", show_alert=True)
        return

    trim = next(
        (item for item in car["trims"] if item["name"] == callback_data.trim_name),
        None,
    )
    if trim is None or trim["price"] is None:
        await callback.answer("Bu komplektatsiya narxi hozir belgilanmagan.", show_alert=True)
        return

    annual_rate = ANNUAL_INTEREST_RATE
    result = calculate_monthly_payment(
        price=trim["price"],
        down_payment_percent=callback_data.down_percent,
        term_months=callback_data.value,
        annual_interest_rate=annual_rate,
    )

    text = (
        f"🧮 <b>{car['brand']} {car['model']} — {trim['name']}</b>\n"
        f"Avtomobil narxi: {format_price(trim['price'])}\n"
        f"Boshlang'ich to'lov ({callback_data.down_percent}%): "
        f"{format_price(result['down_payment'])}\n"
        f"Kredit summasi: {format_price(result['loan_amount'])}\n"
        f"Yillik foiz (taxminiy): {annual_rate:g}%\n"
        f"Muddat: {callback_data.value} oy\n"
        f"💳 Taxminiy oylik to'lov: "
        f"<b>{format_price(result['monthly_payment'])}</b>\n\n"
        "Bu taxminiy hisob-kitob, aniq shartlar uchun menejerga "
        "murojaat qiling."
    )
    await callback.message.edit_text(text, parse_mode="HTML")
