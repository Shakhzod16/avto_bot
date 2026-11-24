"""Public catalog, credit, contacts and lead endpoints."""

from __future__ import annotations

import json
import logging
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import and_, func, or_, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.sql.elements import ColumnElement

from backend.app.api.dependencies import get_current_customer
from backend.app.bot.notifications import notify_new_lead
from backend.app.db.session import get_session
from backend.app.models import Car, Lead, LeadStatus, Setting, Trim, User
from backend.app.schemas.public import (
    CarRead,
    ContactsRead,
    CreditRequest,
    CreditResponse,
    LeadCreate,
    LeadRead,
)
from backend.app.services.credit import calculate_credit
from backend.app.services.rate_limit import lead_rate_limiter

logger = logging.getLogger(__name__)
router = APIRouter()
SessionDep = Annotated[AsyncSession, Depends(get_session)]
SortOption = Literal["recommended", "price_asc", "price_desc", "name_asc", "name_desc"]


async def _car_query_options(session: AsyncSession, query):
    result = await session.execute(query)
    return result.scalars().unique().all()


@router.get("/cars", response_model=list[CarRead])
async def list_cars(
    session: SessionDep,
    body_type: str | None = Query(default=None, max_length=40),
    drive: Literal["AWD", "FWD"] | None = None,
    price_min: int | None = Query(default=None, ge=0),
    price_max: int | None = Query(default=None, ge=0),
    q: str | None = Query(default=None, min_length=1, max_length=120),
    sort: SortOption = "recommended",
) -> list[Car]:
    """List active cars with optional type, drive, text and price filters."""
    if price_min is not None and price_max is not None and price_min > price_max:
        raise HTTPException(
            status_code=422,
            detail="price_min qiymati price_max dan katta bo'lmasligi kerak",
        )

    query = (
        select(Car)
        .where(Car.is_active.is_(True))
        .options(
            selectinload(Car.trims.and_(Trim.is_active.is_(True))),
            selectinload(Car.images),
        )
    )
    if body_type:
        query = query.where(func.lower(Car.body_type) == body_type.strip().lower())
    if drive:
        query = query.where(Car.drive == drive)
    if q:
        search = f"%{q.strip()}%"
        query = query.where(
            or_(
                Car.brand.ilike(search),
                Car.model.ilike(search),
                Car.engine.ilike(search),
            )
        )
    if price_min is not None or price_max is not None:
        price_conditions: list[ColumnElement[bool]] = [
            Trim.is_active.is_(True),
            Trim.price.is_not(None),
        ]
        if price_min is not None:
            price_conditions.append(Trim.price >= price_min)
        if price_max is not None:
            price_conditions.append(Trim.price <= price_max)
        query = query.where(Car.trims.any(and_(*price_conditions)))

    min_price = (
        select(func.min(Trim.price))
        .where(Trim.car_id == Car.id, Trim.is_active.is_(True))
        .correlate(Car)
        .scalar_subquery()
    )
    if sort == "price_asc":
        query = query.order_by(min_price.asc().nulls_last(), Car.sort_order, Car.id)
    elif sort == "price_desc":
        query = query.order_by(min_price.desc().nulls_last(), Car.sort_order, Car.id)
    elif sort == "name_asc":
        query = query.order_by(Car.brand, Car.model, Car.id)
    elif sort == "name_desc":
        query = query.order_by(Car.brand.desc(), Car.model.desc(), Car.id)
    else:
        query = query.order_by(Car.sort_order, Car.id)

    return await _car_query_options(session, query)


@router.get("/cars/compare", response_model=list[CarRead])
async def compare_cars(
    session: SessionDep,
    ids: str = Query(min_length=3, max_length=32),
) -> list[Car]:
    """Return two or three active cars in the requested ID order."""
    try:
        car_ids = [int(value.strip()) for value in ids.split(",")]
    except ValueError as exc:
        raise HTTPException(
            status_code=422, detail="ids faqat butun sonlardan iborat bo'lishi kerak"
        ) from exc
    if not 2 <= len(car_ids) <= 3:
        raise HTTPException(
            status_code=422, detail="Taqqoslash uchun 2 yoki 3 ta mashina tanlang"
        )
    if len(set(car_ids)) != len(car_ids):
        raise HTTPException(
            status_code=422, detail="Bir mashinani takror tanlab bo'lmaydi"
        )

    query = (
        select(Car)
        .where(Car.id.in_(car_ids), Car.is_active.is_(True))
        .options(
            selectinload(Car.trims.and_(Trim.is_active.is_(True))),
            selectinload(Car.images),
        )
    )
    cars = await _car_query_options(session, query)
    if len(cars) != len(car_ids):
        raise HTTPException(
            status_code=404, detail="Tanlangan mashinalardan biri topilmadi"
        )
    by_id = {car.id: car for car in cars}
    return [by_id[car_id] for car_id in car_ids]


@router.get("/cars/{slug}", response_model=CarRead)
async def get_car(slug: str, session: SessionDep) -> Car:
    """Return an active car and its trims and images."""
    query = (
        select(Car)
        .where(Car.slug == slug, Car.is_active.is_(True))
        .options(
            selectinload(Car.trims.and_(Trim.is_active.is_(True))),
            selectinload(Car.images),
        )
    )
    result = await session.execute(query)
    car = result.scalar_one_or_none()
    if car is None:
        raise HTTPException(status_code=404, detail="Mashina topilmadi")
    return car


@router.post("/credit/calculate", response_model=CreditResponse)
async def calculate_credit_endpoint(
    payload: CreditRequest,
    session: SessionDep,
) -> CreditResponse:
    """Calculate an approximate annuity credit payment."""
    amount: int
    if payload.trim_id is not None:
        result = await session.execute(
            select(Trim).where(
                Trim.id == payload.trim_id,
                Trim.car_id == payload.car_id,
                Trim.is_active.is_(True),
            )
        )
        trim = result.scalar_one_or_none()
        if trim is None:
            raise HTTPException(status_code=404, detail="Komplektatsiya topilmadi")
        if trim.price is None:
            raise HTTPException(
                status_code=422,
                detail="Bu komplektatsiya narxi keyinroq e'lon qilinadi",
            )
        amount = trim.price
    else:
        if payload.amount is None:
            raise HTTPException(
                status_code=422, detail="Narx miqdori ko'rsatilishi kerak"
            )
        amount = payload.amount

    rate_result = await session.execute(
        select(Setting.value).where(Setting.key == "annual_interest_rate")
    )
    raw_rate = rate_result.scalar_one_or_none()
    if raw_rate is None:
        raise HTTPException(
            status_code=503,
            detail="Kredit foiz stavkasi hali sozlanmagan",
        )
    try:
        annual_rate = float(raw_rate)
    except ValueError as exc:
        logger.exception("annual_interest_rate sozlamasi raqam emas")
        raise HTTPException(
            status_code=503,
            detail="Kredit foiz stavkasi noto'g'ri sozlangan",
        ) from exc

    try:
        calculation = calculate_credit(
            amount=amount,
            initial_percent=payload.initial_percent,
            months=payload.months,
            annual_rate=annual_rate,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return CreditResponse(
        amount=int(calculation["amount"]),
        initial_payment=int(calculation["initial_payment"]),
        loan_amount=int(calculation["loan_amount"]),
        initial_percent=float(calculation["initial_percent"]),
        months=int(calculation["months"]),
        annual_rate=float(calculation["annual_rate"]),
        monthly_payment=int(calculation["monthly_payment"]),
    )


@router.get("/contacts", response_model=ContactsRead)
async def get_contacts(request: Request, session: SessionDep) -> ContactsRead:
    """Return public contact data from database settings."""
    result = await session.execute(select(Setting.key, Setting.value))
    values: dict[str, str] = {key: value for key, value in result.all()}
    try:
        phones = json.loads(values.get("phones", "[]"))
    except json.JSONDecodeError as exc:
        logger.exception("phones setting JSON formati noto'g'ri")
        raise HTTPException(
            status_code=503, detail="Aloqa sozlamalari noto'g'ri"
        ) from exc

    required = ("dealership_name", "address", "instagram")
    if any(not values.get(key) for key in required) or not isinstance(phones, list):
        raise HTTPException(status_code=503, detail="Aloqa ma'lumotlari sozlanmagan")

    telegram_username = getattr(request.app.state, "telegram_bot_username", None)
    telegram_url = (
        f"https://t.me/{telegram_username}"
        if isinstance(telegram_username, str) and telegram_username
        else None
    )
    return ContactsRead(
        name=values["dealership_name"],
        address=values["address"],
        phones=phones,
        instagram=values["instagram"],
        map_link=values.get("map_link") or None,
        telegram_url=telegram_url,
        working_hours=values.get("working_hours") or None,
    )


@router.post("/leads", response_model=LeadRead, status_code=status.HTTP_201_CREATED)
async def create_lead(
    payload: LeadCreate,
    request: Request,
    session: SessionDep,
    current_user: Annotated[User, Depends(get_current_customer)],
) -> Lead:
    """Validate, rate-limit and save a public customer lead."""
    if payload.car_id is not None:
        car_result = await session.execute(
            select(Car).where(Car.id == payload.car_id, Car.is_active.is_(True))
        )
        if car_result.scalar_one_or_none() is None:
            raise HTTPException(status_code=404, detail="Mashina topilmadi")

    if payload.trim_id is not None:
        trim_result = await session.execute(
            select(Trim).where(
                Trim.id == payload.trim_id,
                Trim.car_id == payload.car_id,
                Trim.is_active.is_(True),
            )
        )
        if trim_result.scalar_one_or_none() is None:
            raise HTTPException(status_code=404, detail="Komplektatsiya topilmadi")

    ip_address = request.client.host if request.client else "unknown"
    if not await lead_rate_limiter.allow(ip_address, current_user.id):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Bir soat ichida bitta foydalanuvchi yoki IP manzildan 3 ta ariza yuborish mumkin",
        )

    lead = Lead(
        user_id=current_user.id,
        name=payload.name,
        phone=payload.phone,
        car_id=payload.car_id,
        trim_id=payload.trim_id,
        type=payload.type,
        comment=payload.comment,
        status=LeadStatus.NEW,
    )
    current_user.name = payload.name
    current_user.phone = payload.phone
    session.add(lead)
    await session.commit()
    await session.refresh(lead)
    bot = getattr(request.app.state, "telegram_bot", None)
    if bot is not None:
        try:
            await notify_new_lead(bot, lead.id)
        except SQLAlchemyError:
            logger.exception(
                "Ariza saqlandi, ammo Telegram xabarnomasi uchun DB so'rovi bajarilmadi: %s",
                lead.id,
            )
    return lead
