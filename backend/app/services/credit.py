"""Credit calculation service."""

from __future__ import annotations

import math


def calculate_credit(
    amount: int,
    initial_percent: float,
    months: int,
    annual_rate: float,
) -> dict[str, int | float]:
    """Return an approximate annuity payment and its input breakdown."""
    if amount <= 0:
        raise ValueError("Avtomobil narxi musbat bo'lishi kerak")
    if not 0 <= initial_percent <= 100:
        raise ValueError("Boshlang'ich to'lov 0-100 oralig'ida bo'lishi kerak")
    if months <= 0:
        raise ValueError("Muddat musbat bo'lishi kerak")
    if not math.isfinite(initial_percent) or not math.isfinite(annual_rate):
        raise ValueError("Foiz qiymatlari chekli son bo'lishi kerak")
    if annual_rate < 0:
        raise ValueError("Foiz stavkasi manfiy bo'lishi mumkin emas")

    initial_payment = round(amount * initial_percent / 100)
    loan_amount = amount - initial_payment
    monthly_rate = annual_rate / 100 / 12

    if loan_amount == 0:
        payment = 0
    elif monthly_rate == 0:
        payment = math.ceil(loan_amount / months)
    else:
        factor = (1 + monthly_rate) ** months
        payment = math.ceil(loan_amount * monthly_rate * factor / (factor - 1))

    return {
        "amount": amount,
        "initial_payment": initial_payment,
        "loan_amount": loan_amount,
        "initial_percent": initial_percent,
        "months": months,
        "annual_rate": annual_rate,
        "monthly_payment": payment,
    }
