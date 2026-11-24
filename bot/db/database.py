"""Aiogsqlite orqali foydalanuvchilar va so'rovlar jadvalini boshqarish."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import aiosqlite

from config import DATABASE_PATH


async def get_connection(database_path: str | Path | None = None) -> aiosqlite.Connection:
    """Yangi SQLite ulanishini ochadi."""
    path = Path(database_path) if database_path is not None else DATABASE_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    return await aiosqlite.connect(path)


async def init_db(database_path: str | Path | None = None) -> None:
    """Kerakli jadvallarni yaratadi."""
    connection = await get_connection(database_path)
    try:
        await connection.execute("PRAGMA foreign_keys = ON")
        await connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                tg_id INTEGER PRIMARY KEY,
                name TEXT,
                phone TEXT,
                language TEXT NOT NULL DEFAULT 'uz',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS leads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tg_id INTEGER NOT NULL,
                name TEXT,
                phone TEXT,
                car_id TEXT,
                trim TEXT,
                type TEXT NOT NULL CHECK(type IN ('test_drive', 'buy', 'callback')),
                comment TEXT,
                status TEXT NOT NULL DEFAULT 'new',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(tg_id) REFERENCES users(tg_id)
            );

            CREATE INDEX IF NOT EXISTS idx_leads_tg_id ON leads(tg_id);
            CREATE INDEX IF NOT EXISTS idx_leads_status ON leads(status);
            """
        )
        await connection.commit()
    finally:
        await connection.close()


async def save_user(
    tg_id: int,
    name: str | None,
    phone: str | None = None,
    language: str = "uz",
    database_path: str | Path | None = None,
) -> None:
    """Foydalanuvchini qo'shadi yoki mavjud ma'lumotlarini yangilaydi."""
    connection = await get_connection(database_path)
    try:
        await connection.execute(
            """
            INSERT INTO users (tg_id, name, phone, language)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(tg_id) DO UPDATE SET
                name = excluded.name,
                phone = COALESCE(excluded.phone, users.phone),
                language = excluded.language
            """,
            (tg_id, name, phone, language),
        )
        await connection.commit()
    finally:
        await connection.close()


async def save_lead(
    tg_id: int,
    name: str,
    phone: str,
    car_id: str,
    trim_name: str,
    lead_type: str,
    comment: str | None = None,
    database_path: str | Path | None = None,
) -> int:
    """Yangi arizani saqlaydi va ID qaytaradi."""
    connection = await get_connection(database_path)
    try:
        cursor = await connection.execute(
            """
            INSERT INTO leads (
                tg_id, name, phone, car_id, trim, type, comment, status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, 'new')
            """,
            (tg_id, name, phone, car_id, trim_name, lead_type, comment),
        )
        await connection.commit()
        return int(cursor.lastrowid)
    finally:
        await connection.close()


async def count_recent_leads(
    tg_id: int,
    hours: int = 1,
    database_path: str | Path | None = None,
) -> int:
    """Foydalanuvchining oxirgi soatlardagi arizalar sonini qaytaradi."""
    connection = await get_connection(database_path)
    try:
        threshold = (datetime.now(UTC) - timedelta(hours=hours)).strftime(
            "%Y-%m-%d %H:%M:%S"
        )
        cursor = await connection.execute(
            "SELECT COUNT(*) FROM leads WHERE tg_id = ? AND created_at >= ?",
            (tg_id, threshold),
        )
        row = await cursor.fetchone()
        return int(row[0]) if row else 0
    finally:
        await connection.close()


async def update_lead_status(
    lead_id: int,
    status: str,
    database_path: str | Path | None = None,
) -> bool:
    """Lead holatini yangilaydi."""
    if status not in {"new", "accepted", "contacted", "cancelled"}:
        raise ValueError("Noto'g'ri lead status")

    connection = await get_connection(database_path)
    try:
        cursor = await connection.execute(
            "UPDATE leads SET status = ? WHERE id = ?",
            (status, lead_id),
        )
        await connection.commit()
        return cursor.rowcount > 0
    finally:
        await connection.close()


async def get_stats(database_path: str | Path | None = None) -> dict:
    """Foydalanuvchilar, leadlar va eng ko'p so'ralgan mashinalar."""
    connection = await get_connection(database_path)
    try:
        now = datetime.now(UTC)
        today = now.strftime("%Y-%m-%d")
        week_start = (now - timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S")

        async def scalar(query: str, parameters: tuple = ()) -> int:
            cursor = await connection.execute(query, parameters)
            row = await cursor.fetchone()
            return int(row[0]) if row else 0

        users = await scalar("SELECT COUNT(*) FROM users")
        leads_today = await scalar(
            "SELECT COUNT(*) FROM leads WHERE substr(created_at, 1, 10) = ?",
            (today,),
        )
        leads_week = await scalar(
            "SELECT COUNT(*) FROM leads WHERE created_at >= ?",
            (week_start,),
        )
        leads_total = await scalar("SELECT COUNT(*) FROM leads")

        cursor = await connection.execute(
            """
            SELECT car_id, COUNT(*) AS requests
            FROM leads
            WHERE car_id IS NOT NULL
            GROUP BY car_id
            ORDER BY requests DESC, car_id ASC
            LIMIT 5
            """
        )
        popular_cars = await cursor.fetchall()
        return {
            "users": users,
            "leads_today": leads_today,
            "leads_week": leads_week,
            "leads_total": leads_total,
            "popular_cars": popular_cars,
        }
    finally:
        await connection.close()


async def get_last_leads(
    limit: int = 10,
    database_path: str | Path | None = None,
) -> list[tuple]:
    """Oxirgi leadlarni qaytaradi."""
    connection = await get_connection(database_path)
    try:
        cursor = await connection.execute(
            """
            SELECT id, tg_id, name, phone, car_id, trim, type, comment,
                   status, created_at
            FROM leads
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        )
        return await cursor.fetchall()
    finally:
        await connection.close()


async def get_all_users(database_path: str | Path | None = None) -> list[int]:
    """Broadcast uchun barcha tg_id larni qaytaradi."""
    connection = await get_connection(database_path)
    try:
        cursor = await connection.execute("SELECT tg_id FROM users")
        return [int(row[0]) for row in await cursor.fetchall()]
    finally:
        await connection.close()


async def get_all_leads(database_path: str | Path | None = None) -> list[tuple]:
    """CSV eksporti uchun barcha leadlarni qaytaradi."""
    connection = await get_connection(database_path)
    try:
        cursor = await connection.execute(
            """
            SELECT id, tg_id, name, phone, car_id, trim, type, comment,
                   status, created_at
            FROM leads
            ORDER BY id DESC
            """
        )
        return await cursor.fetchall()
    finally:
        await connection.close()
