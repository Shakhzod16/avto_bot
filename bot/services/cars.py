"""Mashinalar katalogini JSON fayldan yuklash va filtrlash."""

from __future__ import annotations

import json
from pathlib import Path

DATA_PATH = Path(__file__).resolve().parents[2] / "data" / "cars.json"


def _load_cars() -> tuple[dict, ...]:
    """Mashinalar katalogini ishga tushganda bitta marta yuklaydi."""
    with DATA_PATH.open("r", encoding="utf-8") as file:
        cars = json.load(file)
    if not isinstance(cars, list):
        raise TypeError("data/cars.json ro'yxat bo'lishi kerak")
    return tuple(cars)


CARS = _load_cars()


def get_all_cars() -> tuple[dict, ...]:
    """Barcha mashinalarni qaytaradi."""
    return CARS


def get_car(car_id: str) -> dict | None:
    """ID bo'yicha mashinani yoki topilmasa None qaytaradi."""
    return next((car for car in CARS if car["id"] == car_id), None)


def search_by_budget(min: int, max: int) -> tuple[dict, ...]:
    """Minimal va maksimal narx oralig'idagi mashinalarni qaytaradi."""
    if min < 0 or max < 0:
        raise ValueError("Narxlar manfiy bo'lishi mumkin emas")
    if min > max:
        raise ValueError("Minimal narx maksimal narxdan katta bo'lishi mumkin emas")

    return tuple(
        car
        for car in CARS
        if any(
            trim["price"] is not None
            and min <= trim["price"] <= max
            for trim in car["trims"]
        )
    )


def filter_by_body_type(body_type: str) -> tuple[dict, ...]:
    """Kuzov turi bo'yicha mashinalarni qaytaradi."""
    normalized = body_type.strip().lower()
    return tuple(
        car
        for car in CARS
        if car["body_type"].lower() == normalized
    )


def filter_by_drive(drive: str) -> tuple[dict, ...]:
    """Uzatma turi bo'yicha mashinalarni qaytaradi."""
    normalized = drive.strip().lower()
    return tuple(
        car
        for car in CARS
        if car["drive"].lower() == normalized
    )


def min_price(car: dict) -> int | None:
    """Mashinaning e'lon qilingan eng arzon trim narxini qaytaradi."""
    prices = [
        trim["price"]
        for trim in car["trims"]
        if trim["price"] is not None
    ]
    return min(prices) if prices else None
