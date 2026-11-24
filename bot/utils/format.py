"""Xabarlar uchun narx va mashina kartasini formatlash."""

from __future__ import annotations


def format_price(price: int | None) -> str:
    """Narxni bo'shliqlar bilan va so'm bilan qaytaradi."""
    if price is None:
        return "Narxi keyinroq e'lon qilinadi"
    return f"{price:,}".replace(",", " ") + " so'm"


def render_car_card(car: dict) -> str:
    """Mashina ma'lumotlarini qulay o'zbekcha Telegram matniga aylantiradi."""
    name = f"{car['brand']} {car['model']}"
    lines = [
        f"🚗 <b>{name}</b>",
        f"🔹 Turi: {car['body_type']}",
        f"🔧 Dvigatel: {car['engine']}",
        f"⚡ Quvvati: {car['power_hp']} o.k.",
        f"🌿 Standart: {car['emission']}",
        f"🦾 Uzatma: {car['drive']}",
        f"⚙️ Avtomat: {car['transmission']}",
        f"👥 O'rindiqlar: {car['seats']}",
        "",
        "💰 <b>Komplektatsiyalar va narxlar (QQS bilan):</b>",
    ]

    for trim in car["trims"]:
        lines.append(f"• {trim['name']}: {format_price(trim['price'])}")

    return "\n".join(lines)
