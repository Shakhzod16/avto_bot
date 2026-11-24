"""Kredit va narx bilan bog'liq hisoblashlar."""

from __future__ import annotations

import math


def calculate_monthly_payment(
    price: int,
    down_payment_percent: int,
    term_months: int,
    annual_interest_rate: float,
) -> dict[str, float | int]:
    """Annuitet formulasi bo'yicha taxminiy kredit to'lovini hisoblaydi."""
    if price < 0:
        raise ValueError("Narx manfiy bo'lishi mumkin emas")
    if down_payment_percent < 0 or down_payment_percent >= 100:
        raise ValueError("Boshlang'ich to'lov 0-100% oralig'ida bo'lishi kerak")
    if term_months <= 0:
        raise ValueError("Muddat musbat bo'lishi kerak")
    if annual_interest_rate < 0:
        raise ValueError("Yillik foiz manfiy bo'lishi mumkin emas")

    down_payment = round(price * down_payment_percent / 100)
    loan_amount = price - down_payment
    monthly_rate = annual_interest_rate / 100 / 12

    if loan_amount == 0:
        monthly_payment = 0
    elif monthly_rate == 0:
        monthly_payment = loan_amount / term_months
    else:
        factor = (1 + monthly_rate) ** term_months
        monthly_payment = loan_amount * monthly_rate * factor / (factor - 1)

    return {
        "down_payment": down_payment,
        "loan_amount": loan_amount,
        "monthly_payment": math.ceil(monthly_payment),
    }


def get_price_range(car: dict) -> tuple[int | None, int | None]:
    """Mashina trimlarining minimal va maksimal narxini qaytaradi."""
    prices = [trim["price"] for trim in car["trims"] if trim["price"] is not None]
    return (min(prices), max(prices)) if prices else (None, None)
