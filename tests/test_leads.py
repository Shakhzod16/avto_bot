import asyncio
from pathlib import Path

from bot.db.database import (
    count_recent_leads,
    init_db,
    save_lead,
    update_lead_status,
)
from bot.services.leads import normalize_phone


def test_normalize_phone_plus998():
    assert normalize_phone("+998 90 123 45 67") == "+998901234567"


def test_normalize_phone_invalid():
    assert normalize_phone("+1 555 123 4567") is None


def test_save_lead_and_anti_spam_limit(tmp_path: Path):
    async def check() -> None:
        db_path = tmp_path / "leads_test.sqlite3"
        await init_db(db_path)
        for _ in range(3):
            await save_lead(
                tg_id=1001,
                name="Ali Karimov",
                phone="+998901234567",
                car_id="jetta-vs5",
                trim_name="Enjoyment",
                lead_type="callback",
                database_path=db_path,
            )
        assert await count_recent_leads(1001, database_path=db_path) == 3

    asyncio.run(check())


def test_update_lead_status(tmp_path: Path):
    async def check() -> None:
        db_path = tmp_path / "status_test.sqlite3"
        await init_db(db_path)
        lead_id = await save_lead(
            tg_id=1002,
            name="Dilnoza",
            phone="+998931112233",
            car_id="volkswagen-tiguan-l-pro",
            trim_name="R-Line",
            lead_type="test_drive",
            database_path=db_path,
        )
        assert await update_lead_status(lead_id, "contacted", db_path)

    asyncio.run(check())
