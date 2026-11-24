"""Idempotently seed the dealership catalog from data/cars.json."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
from pathlib import Path
from typing import Any

from sqlalchemy import func, select

from backend.app.core.config import PROJECT_ROOT
from backend.app.db.session import SessionFactory
from backend.app.models import Car, Setting, Trim

logger = logging.getLogger(__name__)
CAR_DATA_PATH = PROJECT_ROOT / "data" / "cars.json"
DEFAULT_SETTINGS = {
    "dealership_name": "Buxara Avto Magnat",
    "address": "Buxoro shahar, Gazli shox ko'chasi, 500-uy. Mo'ljal: «Severniy» Guliston ko'prigi yonida.",
    "phones": json.dumps(["+998553054000", "+998996284000"]),
    "instagram": "volkswagenbuxara",
    "map_link": "",
    "working_hours": "",
}


def _load_cars(path: Path = CAR_DATA_PATH) -> list[dict[str, Any]]:
    try:
        content = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Avtomobil katalogini o'qib bo'lmadi: {path}") from exc
    if not isinstance(content, list) or not content:
        raise RuntimeError(f"Avtomobil katalogi bo'sh yoki noto'g'ri: {path}")
    return content


async def seed_catalog(*, only_if_empty: bool = False) -> int:
    """Insert or update catalog cars and trims without deleting admin-created data."""
    cars = _load_cars()
    slugs = [item.get("id") for item in cars]
    if any(not isinstance(slug, str) or not slug for slug in slugs) or len(
        set(slugs)
    ) != len(slugs):
        raise RuntimeError("cars.json faylida id lar bo'sh yoki takrorlangan")

    async with SessionFactory() as session:
        existing_count = await session.scalar(select(func.count(Car.id))) or 0
        if only_if_empty and existing_count:
            logger.info(
                "Mavjud katalog topildi; avtomobil ma'lumotlari o'zgartirilmadi"
            )
            return 0
        for index, item in enumerate(cars):
            drive_text = str(item["drive"])
            drive = "AWD" if "AWD" in drive_text else "FWD"
            car = await session.scalar(select(Car).where(Car.slug == item["id"]))
            car_fields = {
                "slug": item["id"],
                "brand": item["brand"],
                "model": item["model"],
                "body_type": item["body_type"],
                "engine": item["engine"],
                "power_hp": item["power_hp"],
                "emission": item["emission"],
                "drive": drive,
                "transmission": item["transmission"],
                "seats": item["seats"],
                "is_active": True,
                "sort_order": index,
            }
            if car is None:
                car = Car(**car_fields)
                session.add(car)
                await session.flush()
            else:
                for field, value in car_fields.items():
                    setattr(car, field, value)

            for trim_index, trim_data in enumerate(item["trims"]):
                trim = await session.scalar(
                    select(Trim).where(
                        Trim.car_id == car.id,
                        Trim.name == trim_data["name"],
                    )
                )
                if trim is None:
                    session.add(
                        Trim(
                            car_id=car.id,
                            name=trim_data["name"],
                            price=trim_data["price"],
                            is_active=True,
                            sort_order=trim_index,
                        )
                    )
                else:
                    trim.price = trim_data["price"]
                    trim.is_active = True
                    trim.sort_order = trim_index

        for key, value in DEFAULT_SETTINGS.items():
            if await session.get(Setting, key) is None:
                session.add(Setting(key=key, value=value))
        await session.commit()
    logger.info("Katalog seed qilindi: %s ta avtomobil", len(cars))
    return len(cars)


def main() -> None:
    """Run the seed command."""
    parser = argparse.ArgumentParser(description="Seed the dealership car catalog")
    parser.add_argument(
        "--if-empty",
        action="store_true",
        help="Skip catalog updates when at least one car already exists",
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    count = asyncio.run(seed_catalog(only_if_empty=args.if_empty))
    if count:
        print(f"{count} ta avtomobil katalogga yuklandi.")
    else:
        print("Mavjud katalog o'zgartirilmadi.")


if __name__ == "__main__":
    main()
