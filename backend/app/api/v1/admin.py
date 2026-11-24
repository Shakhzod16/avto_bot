"""Role-protected administration API."""

from __future__ import annotations

import asyncio
import csv
import io
import json
import logging
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from typing import Annotated, Literal
from uuid import uuid4

from aiogram import Bot
from aiogram.exceptions import (
    TelegramAPIError,
    TelegramForbiddenError,
    TelegramRetryAfter,
)
from aiogram.types import (
    FSInputFile,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    WebAppInfo,
)
from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    Response,
    UploadFile,
    status,
)
from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from starlette.concurrency import run_in_threadpool
from starlette.responses import StreamingResponse

from backend.app.api.dependencies import (
    SessionDep,
    get_current_admin,
    require_admin_action,
)
from backend.app.core.config import CAR_MEDIA_DIR, WEBAPP_URL, webapp_url_error
from backend.app.core.security import hash_password
from backend.app.db.session import SessionFactory
from backend.app.models import (
    AdminUser,
    AuditLog,
    Car,
    CarImage,
    Lead,
    LeadStatus,
    LeadType,
    Setting,
    Trim,
    User,
)
from backend.app.schemas.admin import (
    AdminAccountActive,
    AdminAccountCreate,
    AdminAccountPassword,
    AdminAccountRead,
    AdminCarRead,
    AdminStats,
    AuditLogPage,
    AuditLogRead,
    BroadcastAccepted,
    BroadcastProgress,
    CarCreate,
    CarOrder,
    CarUpdate,
    ImageOrder,
    ImageRead,
    LeadAdminRead,
    LeadPage,
    LeadUpdate,
    SettingsRead,
    SettingsUpdate,
    TrimCreate,
    TrimRead,
    TrimUpdate,
    UserBlockUpdate,
    UserPage,
    UserRead,
)
from backend.app.services.audit import write_audit_entry
from backend.app.services.broadcast import BroadcastImageError, save_broadcast_image
from backend.app.services.images import ImageUploadError, save_car_image

logger = logging.getLogger(__name__)
router = APIRouter()
AdminDep = Annotated[AdminUser, Depends(get_current_admin)]
OwnerDep = Annotated[AdminUser, Depends(require_admin_action("settings.write"))]
CarDeleteOwnerDep = Annotated[AdminUser, Depends(require_admin_action("cars.delete"))]
PAGE_LIMIT = 100
CAR_IMAGE_LIMIT = 10


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def _record_file(path: str | None) -> Path | None:
    if not path:
        return None
    candidate = (CAR_MEDIA_DIR / Path(path).name).resolve()
    if candidate.parent != CAR_MEDIA_DIR.resolve():
        logger.error("Media fayli yo'li ruxsat etilgan katalogdan tashqarida")
        return None
    return candidate


def _remove_image_files(image: CarImage) -> None:
    for path in (image.path, image.thumbnail_path):
        file_path = _record_file(path)
        if file_path is None:
            continue
        try:
            file_path.unlink(missing_ok=True)
        except OSError:
            logger.exception("Avtomobil rasmi faylini o'chirib bo'lmadi")


def _remove_image_paths(path: str, thumbnail_path: str | None) -> None:
    for relative_path in (path, thumbnail_path):
        file_path = _record_file(relative_path)
        if file_path is None:
            continue
        try:
            file_path.unlink(missing_ok=True)
        except OSError:
            logger.exception("Avtomobil rasmi faylini o'chirib bo'lmadi")


async def _audit(
    session: AsyncSession,
    request: Request,
    admin: AdminUser,
    *,
    action: str,
    entity: str,
    entity_id: int | str | None,
    before: object = None,
    after: object = None,
) -> None:
    await write_audit_entry(
        session,
        action=action,
        entity=entity,
        admin_user_id=admin.id,
        entity_id=entity_id,
        before=before,
        after=after,
        ip_address=_client_ip(request),
    )


async def _get_car(session: AsyncSession, car_id: int) -> Car:
    car = await session.scalar(
        select(Car)
        .where(Car.id == car_id)
        .options(selectinload(Car.trims), selectinload(Car.images))
    )
    if car is None:
        raise HTTPException(status_code=404, detail="Avtomobil topilmadi")
    return car


def _car_snapshot(car: Car) -> dict[str, object]:
    return {
        "slug": car.slug,
        "brand": car.brand,
        "model": car.model,
        "is_active": car.is_active,
        "sort_order": car.sort_order,
    }


def _lead_filters(
    *,
    status_filter: LeadStatus | None,
    type_filter: LeadType | None,
    car_id: int | None,
    date_from: date | None,
    date_to: date | None,
    search: str | None,
) -> list:
    filters = []
    if status_filter is not None:
        filters.append(Lead.status == status_filter)
    if type_filter is not None:
        filters.append(Lead.type == type_filter)
    if car_id is not None:
        filters.append(Lead.car_id == car_id)
    if date_from is not None:
        filters.append(
            Lead.created_at >= datetime.combine(date_from, time.min, tzinfo=UTC)
        )
    if date_to is not None:
        end_exclusive = datetime.combine(
            date_to + timedelta(days=1), time.min, tzinfo=UTC
        )
        filters.append(Lead.created_at < end_exclusive)
    if search:
        term = f"%{search.strip()}%"
        filters.append(or_(Lead.name.ilike(term), Lead.phone.ilike(term)))
    return filters


async def _matching_leads(
    session: AsyncSession,
    *,
    status_filter: LeadStatus | None,
    type_filter: LeadType | None,
    car_id: int | None,
    date_from: date | None,
    date_to: date | None,
    search: str | None,
) -> list[Lead]:
    filters = _lead_filters(
        status_filter=status_filter,
        type_filter=type_filter,
        car_id=car_id,
        date_from=date_from,
        date_to=date_to,
        search=search,
    )
    result = await session.execute(
        select(Lead).where(*filters).order_by(Lead.created_at.desc(), Lead.id.desc())
    )
    return list(result.scalars().all())


@router.get("/admin/cars", response_model=list[AdminCarRead])
async def list_admin_cars(session: SessionDep, admin: AdminDep) -> list[Car]:
    del admin
    result = await session.execute(
        select(Car)
        .options(selectinload(Car.trims), selectinload(Car.images))
        .order_by(Car.sort_order, Car.id)
    )
    return list(result.scalars().unique().all())


@router.post(
    "/admin/cars", response_model=AdminCarRead, status_code=status.HTTP_201_CREATED
)
async def create_car(
    payload: CarCreate, request: Request, session: SessionDep, admin: AdminDep
) -> Car:
    car = Car(**payload.model_dump())
    session.add(car)
    try:
        await session.flush()
        await _audit(
            session,
            request,
            admin,
            action="car.create",
            entity="car",
            entity_id=car.id,
            after=_car_snapshot(car),
        )
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=409, detail="Bu slug bilan avtomobil allaqachon mavjud"
        ) from exc
    return await _get_car(session, car.id)


@router.patch("/admin/cars/{car_id}", response_model=AdminCarRead)
async def update_car(
    car_id: int,
    payload: CarUpdate,
    request: Request,
    session: SessionDep,
    admin: AdminDep,
) -> Car:
    car = await _get_car(session, car_id)
    before = _car_snapshot(car)
    changes = payload.model_dump(exclude_unset=True)
    if any(value is None and key != "description" for key, value in changes.items()):
        raise HTTPException(
            status_code=422,
            detail="Majburiy avtomobil maydonlari bo'sh bo'lishi mumkin emas",
        )
    for key, value in changes.items():
        setattr(car, key, value)
    try:
        await _audit(
            session,
            request,
            admin,
            action="car.update",
            entity="car",
            entity_id=car.id,
            before=before,
            after=_car_snapshot(car),
        )
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=409, detail="Bu slug bilan avtomobil allaqachon mavjud"
        ) from exc
    return await _get_car(session, car_id)


@router.delete("/admin/cars/{car_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_car(
    car_id: int,
    request: Request,
    session: SessionDep,
    admin: CarDeleteOwnerDep,
) -> Response:
    car = await _get_car(session, car_id)
    images = list(car.images)
    snapshot = _car_snapshot(car)
    await _audit(
        session,
        request,
        admin,
        action="car.delete",
        entity="car",
        entity_id=car.id,
        before=snapshot,
    )
    await session.delete(car)
    await session.commit()
    for image in images:
        _remove_image_files(image)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.put("/admin/cars/reorder", status_code=status.HTTP_204_NO_CONTENT)
async def reorder_cars(
    payload: CarOrder,
    request: Request,
    session: SessionDep,
    admin: AdminDep,
) -> Response:
    if len(set(payload.ids)) != len(payload.ids):
        raise HTTPException(
            status_code=422, detail="Tartibda takroriy avtomobil ID si bor"
        )
    result = await session.execute(select(Car))
    cars = result.scalars().all()
    if {car.id for car in cars} != set(payload.ids):
        raise HTTPException(
            status_code=422,
            detail="Tartib ro'yxati barcha avtomobillarni o'z ichiga olishi kerak",
        )
    old_order = {car.id: car.sort_order for car in cars}
    by_id = {car.id: car for car in cars}
    for index, car_id in enumerate(payload.ids):
        by_id[car_id].sort_order = index
    await _audit(
        session,
        request,
        admin,
        action="car.reorder",
        entity="car",
        entity_id=None,
        before=old_order,
        after={car.id: car.sort_order for car in cars},
    )
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/admin/cars/{car_id}/trims",
    response_model=TrimRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_trim(
    car_id: int,
    payload: TrimCreate,
    request: Request,
    session: SessionDep,
    admin: AdminDep,
) -> Trim:
    await _get_car(session, car_id)
    trim = Trim(car_id=car_id, **payload.model_dump())
    session.add(trim)
    try:
        await session.flush()
        await _audit(
            session,
            request,
            admin,
            action="trim.create",
            entity="trim",
            entity_id=trim.id,
            after={"car_id": car_id, "name": trim.name, "price": trim.price},
        )
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=409, detail="Bu komplektatsiya nomi allaqachon mavjud"
        ) from exc
    return trim


@router.patch("/admin/trims/{trim_id}", response_model=TrimRead)
async def update_trim(
    trim_id: int,
    payload: TrimUpdate,
    request: Request,
    session: SessionDep,
    admin: AdminDep,
) -> Trim:
    trim = await session.get(Trim, trim_id)
    if trim is None:
        raise HTTPException(status_code=404, detail="Komplektatsiya topilmadi")
    changes = payload.model_dump(exclude_unset=True)
    if any(value is None and key != "price" for key, value in changes.items()):
        raise HTTPException(
            status_code=422,
            detail="Komplektatsiya nomi va tartibi bo'sh bo'lishi mumkin emas",
        )
    before = {"name": trim.name, "price": trim.price, "sort_order": trim.sort_order}
    for key, value in changes.items():
        setattr(trim, key, value)
    await _audit(
        session,
        request,
        admin,
        action="trim.update",
        entity="trim",
        entity_id=trim.id,
        before=before,
        after={"name": trim.name, "price": trim.price, "sort_order": trim.sort_order},
    )
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=409, detail="Bu komplektatsiya nomi allaqachon mavjud"
        ) from exc
    return trim


@router.delete("/admin/trims/{trim_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_trim(
    trim_id: int,
    request: Request,
    session: SessionDep,
    admin: AdminDep,
) -> Response:
    trim = await session.get(Trim, trim_id)
    if trim is None:
        raise HTTPException(status_code=404, detail="Komplektatsiya topilmadi")
    await _audit(
        session,
        request,
        admin,
        action="trim.delete",
        entity="trim",
        entity_id=trim.id,
        before={"name": trim.name, "price": trim.price},
    )
    await session.delete(trim)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/admin/cars/{car_id}/images",
    response_model=list[ImageRead],
    status_code=status.HTTP_201_CREATED,
)
async def upload_car_images(
    car_id: int,
    request: Request,
    session: SessionDep,
    admin: AdminDep,
    files: Annotated[list[UploadFile], File()],
) -> list[CarImage]:
    car = await _get_car(session, car_id)
    if not files or len(files) > CAR_IMAGE_LIMIT:
        raise HTTPException(
            status_code=422, detail=f"Bir martada 1–{CAR_IMAGE_LIMIT} ta rasm tanlang"
        )

    stored = []
    try:
        for upload in files:
            stored.append(await save_car_image(upload))
        images = [
            CarImage(
                car_id=car.id,
                path=image.path,
                thumbnail_path=image.thumbnail_path,
                is_cover=(not car.images and index == 0),
                sort_order=len(car.images) + index,
            )
            for index, image in enumerate(stored)
        ]
        session.add_all(images)
        await session.flush()
        await _audit(
            session,
            request,
            admin,
            action="car.images_upload",
            entity="car",
            entity_id=car.id,
            after={"image_count": len(images)},
        )
        await session.commit()
        return images
    except ImageUploadError as exc:
        await session.rollback()
        for image in stored:
            _remove_image_paths(image.path, image.thumbnail_path)
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except SQLAlchemyError:
        await session.rollback()
        for image in stored:
            _remove_image_paths(image.path, image.thumbnail_path)
        raise
    finally:
        for upload in files:
            await upload.close()


@router.post("/admin/cars/{car_id}/images/{image_id}/cover", response_model=ImageRead)
async def set_cover_image(
    car_id: int,
    image_id: int,
    request: Request,
    session: SessionDep,
    admin: AdminDep,
) -> CarImage:
    images = await session.scalars(select(CarImage).where(CarImage.car_id == car_id))
    image_list = list(images)
    selected = next((image for image in image_list if image.id == image_id), None)
    if selected is None:
        raise HTTPException(status_code=404, detail="Rasm topilmadi")
    previous = next((image.id for image in image_list if image.is_cover), None)
    for image in image_list:
        image.is_cover = image.id == image_id
    await _audit(
        session,
        request,
        admin,
        action="car.image_cover",
        entity="car_image",
        entity_id=image_id,
        before={"cover_id": previous},
        after={"cover_id": image_id},
    )
    await session.commit()
    return selected


@router.put(
    "/admin/cars/{car_id}/images/reorder", status_code=status.HTTP_204_NO_CONTENT
)
async def reorder_car_images(
    car_id: int,
    payload: ImageOrder,
    request: Request,
    session: SessionDep,
    admin: AdminDep,
) -> Response:
    result = await session.scalars(select(CarImage).where(CarImage.car_id == car_id))
    images = list(result)
    by_id = {image.id: image for image in images}
    if len(set(payload.ids)) != len(payload.ids) or set(payload.ids) != set(by_id):
        raise HTTPException(
            status_code=422, detail="Rasm tartibi ushbu avtomobil rasmlariga mos emas"
        )
    previous = [image.id for image in sorted(images, key=lambda item: item.sort_order)]
    for order, image_id in enumerate(payload.ids):
        by_id[image_id].sort_order = order
    await _audit(
        session,
        request,
        admin,
        action="car.images_reorder",
        entity="car",
        entity_id=car_id,
        before=previous,
        after=payload.ids,
    )
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete(
    "/admin/cars/{car_id}/images/{image_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def delete_car_image(
    car_id: int,
    image_id: int,
    request: Request,
    session: SessionDep,
    admin: AdminDep,
) -> Response:
    image = await session.scalar(
        select(CarImage).where(CarImage.id == image_id, CarImage.car_id == car_id)
    )
    if image is None:
        raise HTTPException(status_code=404, detail="Rasm topilmadi")
    was_cover = image.is_cover
    paths = (image.path, image.thumbnail_path)
    await _audit(
        session,
        request,
        admin,
        action="car.image_delete",
        entity="car_image",
        entity_id=image.id,
        before={"path": image.path, "is_cover": was_cover},
    )
    await session.delete(image)
    await session.flush()
    if was_cover:
        replacement = await session.scalar(
            select(CarImage)
            .where(CarImage.car_id == car_id)
            .order_by(CarImage.sort_order, CarImage.id)
            .limit(1)
        )
        if replacement is not None:
            replacement.is_cover = True
    await session.commit()
    _remove_image_paths(paths[0], paths[1])
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/admin/leads", response_model=LeadPage)
async def list_admin_leads(
    session: SessionDep,
    admin: AdminDep,
    status_filter: Annotated[LeadStatus | None, Query(alias="status")] = None,
    type_filter: Annotated[LeadType | None, Query(alias="type")] = None,
    car_id: int | None = Query(default=None, gt=0),
    date_from: date | None = None,
    date_to: date | None = None,
    q: str | None = Query(default=None, max_length=120),
    limit: int = Query(default=20, ge=1, le=PAGE_LIMIT),
    offset: int = Query(default=0, ge=0),
) -> LeadPage:
    del admin
    filters = _lead_filters(
        status_filter=status_filter,
        type_filter=type_filter,
        car_id=car_id,
        date_from=date_from,
        date_to=date_to,
        search=q,
    )
    if date_from and date_to and date_from > date_to:
        raise HTTPException(
            status_code=422, detail="date_from date_to dan keyin bo'lishi mumkin emas"
        )
    total = await session.scalar(select(func.count(Lead.id)).where(*filters)) or 0
    result = await session.execute(
        select(Lead)
        .where(*filters)
        .order_by(Lead.created_at.desc(), Lead.id.desc())
        .limit(limit)
        .offset(offset)
    )
    return LeadPage(
        items=[LeadAdminRead.model_validate(lead) for lead in result.scalars().all()],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/admin/leads/export")
async def export_admin_leads(
    session: SessionDep,
    admin: AdminDep,
    status_filter: Annotated[LeadStatus | None, Query(alias="status")] = None,
    type_filter: Annotated[LeadType | None, Query(alias="type")] = None,
    car_id: int | None = Query(default=None, gt=0),
    date_from: date | None = None,
    date_to: date | None = None,
    q: str | None = Query(default=None, max_length=120),
) -> StreamingResponse:
    del admin
    leads = await _matching_leads(
        session,
        status_filter=status_filter,
        type_filter=type_filter,
        car_id=car_id,
        date_from=date_from,
        date_to=date_to,
        search=q,
    )
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(
        [
            "id",
            "name",
            "phone",
            "car_id",
            "trim_id",
            "type",
            "status",
            "comment",
            "created_at",
        ]
    )

    def safe_csv(value: object) -> str:
        text = str(value if value is not None else "")
        if text.startswith(("=", "+", "-", "@", "\t", "\r")):
            return "'" + text
        return text

    for lead in leads:
        writer.writerow(
            [
                lead.id,
                safe_csv(lead.name),
                safe_csv(lead.phone),
                lead.car_id or "",
                lead.trim_id or "",
                lead.type.value,
                lead.status.value,
                safe_csv(lead.comment),
                lead.created_at.isoformat(),
            ]
        )
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="leads.csv"'},
    )


@router.get("/admin/leads/{lead_id}", response_model=LeadAdminRead)
async def get_admin_lead(lead_id: int, session: SessionDep, admin: AdminDep) -> Lead:
    del admin
    lead = await session.get(Lead, lead_id)
    if lead is None:
        raise HTTPException(status_code=404, detail="Ariza topilmadi")
    return lead


@router.patch("/admin/leads/{lead_id}", response_model=LeadAdminRead)
async def update_admin_lead(
    lead_id: int,
    payload: LeadUpdate,
    request: Request,
    session: SessionDep,
    admin: AdminDep,
) -> Lead:
    if not payload.model_fields_set:
        raise HTTPException(status_code=422, detail="Yangilash uchun maydon ko'rsating")
    lead = await session.get(Lead, lead_id)
    if lead is None:
        raise HTTPException(status_code=404, detail="Ariza topilmadi")
    if "status" in payload.model_fields_set and payload.status is None:
        raise HTTPException(
            status_code=422, detail="Ariza holati bo'sh bo'lishi mumkin emas"
        )
    before = {"status": lead.status.value, "internal_note": lead.internal_note}
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(lead, key, value)
    await _audit(
        session,
        request,
        admin,
        action="lead.update",
        entity="lead",
        entity_id=lead.id,
        before=before,
        after={"status": lead.status.value, "internal_note": lead.internal_note},
    )
    await session.commit()
    await session.refresh(lead)
    return lead


@router.get("/admin/users", response_model=UserPage)
async def list_admin_users(
    session: SessionDep,
    admin: AdminDep,
    q: str | None = Query(default=None, max_length=120),
    is_blocked: bool | None = None,
    limit: int = Query(default=20, ge=1, le=PAGE_LIMIT),
    offset: int = Query(default=0, ge=0),
) -> UserPage:
    del admin
    filters = []
    if q:
        term = f"%{q.strip()}%"
        filters.append(
            or_(
                User.name.ilike(term), User.username.ilike(term), User.phone.ilike(term)
            )
        )
    if is_blocked is not None:
        filters.append(User.is_blocked.is_(is_blocked))
    total = await session.scalar(select(func.count(User.id)).where(*filters)) or 0
    result = await session.execute(
        select(User)
        .where(*filters)
        .order_by(User.created_at.desc(), User.id.desc())
        .limit(limit)
        .offset(offset)
    )
    return UserPage(
        items=[UserRead.model_validate(user) for user in result.scalars().all()],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.patch("/admin/users/{user_id}", response_model=UserRead)
async def update_user_block(
    user_id: int,
    payload: UserBlockUpdate,
    request: Request,
    session: SessionDep,
    admin: AdminDep,
) -> User:
    user = await session.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="Foydalanuvchi topilmadi")
    before = {"is_blocked": user.is_blocked}
    user.is_blocked = payload.is_blocked
    await _audit(
        session,
        request,
        admin,
        action="user.block" if payload.is_blocked else "user.unblock",
        entity="user",
        entity_id=user.id,
        before=before,
        after={"is_blocked": user.is_blocked},
    )
    await session.commit()
    return user


async def _broadcast_count(session: AsyncSession, segment: str) -> int:
    query = select(func.count(User.id)).where(User.tg_id.is_not(None))
    has_lead = select(Lead.id).where(Lead.user_id == User.id).exists()
    if segment == "with_leads":
        query = query.where(has_lead)
    elif segment == "without_leads":
        query = query.where(~has_lead)
    return await session.scalar(query) or 0


async def _run_broadcast(
    app,
    broadcast_id: str,
    *,
    text: str,
    segment: str,
    mini_app_button: bool,
    image_path: Path | None,
) -> None:
    progress: dict = app.state.broadcasts[broadcast_id]
    progress["status"] = "running"
    last_id = 0
    try:
        async with SessionFactory() as session:
            progress["total"] = await _broadcast_count(session, segment)
        keyboard = None
        if mini_app_button:
            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="🚗 Katalogni ochish",
                            web_app=WebAppInfo(url=WEBAPP_URL),
                        )
                    ]
                ]
            )
        while True:
            async with SessionFactory() as session:
                has_lead = select(Lead.id).where(Lead.user_id == User.id).exists()
                query = select(User.id, User.tg_id, User.is_blocked).where(
                    User.id > last_id,
                    User.tg_id.is_not(None),
                )
                if segment == "with_leads":
                    query = query.where(has_lead)
                elif segment == "without_leads":
                    query = query.where(~has_lead)
                batch = list(
                    (await session.execute(query.order_by(User.id).limit(200))).all()
                )
            if not batch:
                break

            newly_blocked: list[int] = []
            for user_id, tg_id, is_blocked in batch:
                last_id = user_id
                progress["processed"] += 1
                if is_blocked:
                    progress["blocked"] += 1
                    continue
                if tg_id is None:
                    progress["failed"] += 1
                    continue

                bot: Bot = app.state.telegram_bot
                try:
                    for retry in range(3):
                        try:
                            if image_path is not None:
                                await bot.send_photo(
                                    tg_id,
                                    FSInputFile(image_path),
                                    caption=text,
                                    reply_markup=keyboard,
                                )
                            else:
                                await bot.send_message(
                                    tg_id, text, reply_markup=keyboard
                                )
                            progress["sent"] += 1
                            break
                        except TelegramRetryAfter as exc:
                            if retry == 2:
                                raise
                            await asyncio.sleep(exc.retry_after)
                    await asyncio.sleep(1 / 25)
                except TelegramForbiddenError:
                    progress["blocked"] += 1
                    newly_blocked.append(user_id)
                except TelegramAPIError:
                    progress["failed"] += 1
                    logger.exception("Broadcast jo'natish xatosi")

            if newly_blocked:
                async with SessionFactory() as session:
                    await session.execute(
                        update(User)
                        .where(User.id.in_(newly_blocked))
                        .values(is_blocked=True)
                    )
                    await session.commit()
        progress["status"] = "completed"
    except Exception:
        logger.exception("Broadcast vazifasi bajarilmadi: %s", broadcast_id)
        progress["status"] = "failed"
        progress["error"] = "Xabar yuborish vazifasida ichki xatolik yuz berdi"
    finally:
        if image_path is not None:
            try:
                image_path.unlink(missing_ok=True)
            except OSError:
                logger.exception(
                    "Broadcast rasmi vaqtinchalik faylini o'chirib bo'lmadi"
                )


@router.post(
    "/admin/broadcast",
    response_model=BroadcastAccepted,
    status_code=status.HTTP_202_ACCEPTED,
)
async def start_broadcast(
    request: Request,
    session: SessionDep,
    admin: AdminDep,
    text: Annotated[str, Form(min_length=1, max_length=4096)],
    segment: Annotated[Literal["all", "with_leads", "without_leads"], Form()] = "all",
    mini_app_button: Annotated[bool, Form()] = False,
    image: Annotated[UploadFile | None, File()] = None,
) -> BroadcastAccepted:
    bot = getattr(request.app.state, "telegram_bot", None)
    if bot is None:
        raise HTTPException(status_code=503, detail="Telegram bot hozir mavjud emas")
    clean_text = text.strip()
    if not clean_text:
        raise HTTPException(
            status_code=422, detail="Xabar matni bo'sh bo'lmasligi kerak"
        )
    if image is not None and len(clean_text) > 1024:
        raise HTTPException(
            status_code=422,
            detail="Rasm bilan yuboriladigan matn 1024 belgidan oshmasin",
        )
    url_error = webapp_url_error(WEBAPP_URL)
    if mini_app_button and url_error:
        raise HTTPException(
            status_code=503,
            detail=f"Mini App tugmasi mavjud emas: {url_error}",
        )

    image_path = None
    if image is not None:
        try:
            image_path = await save_broadcast_image(image)
        except BroadcastImageError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        finally:
            await image.close()

    try:
        await _audit(
            session,
            request,
            admin,
            action="broadcast.start",
            entity="broadcast",
            entity_id=None,
            after={
                "segment": segment,
                "has_image": image is not None,
                "mini_app_button": mini_app_button,
            },
        )
        await session.commit()
    except Exception:
        if image_path is not None:
            try:
                image_path.unlink(missing_ok=True)
            except OSError:
                logger.exception(
                    "Broadcast rasmi vaqtinchalik faylini o'chirib bo'lmadi"
                )
        raise

    broadcast_id = uuid4().hex
    broadcasts = getattr(request.app.state, "broadcasts", None)
    if broadcasts is None:
        broadcasts = {}
        request.app.state.broadcasts = broadcasts
    if len(broadcasts) >= 100:
        completed_id = next(
            (
                key
                for key, value in broadcasts.items()
                if value["status"] in {"completed", "failed"}
            ),
            None,
        )
        if completed_id is not None:
            del broadcasts[completed_id]
    broadcasts[broadcast_id] = {
        "broadcast_id": broadcast_id,
        "status": "queued",
        "total": 0,
        "processed": 0,
        "sent": 0,
        "failed": 0,
        "blocked": 0,
        "error": None,
    }
    task = asyncio.create_task(
        _run_broadcast(
            request.app,
            broadcast_id,
            text=clean_text,
            segment=segment,
            mini_app_button=mini_app_button,
            image_path=image_path,
        ),
        name=f"broadcast-{broadcast_id}",
    )
    tasks = getattr(request.app.state, "broadcast_tasks", None)
    if tasks is None:
        tasks = set()
        request.app.state.broadcast_tasks = tasks
    tasks.add(task)
    task.add_done_callback(tasks.discard)
    return BroadcastAccepted(broadcast_id=broadcast_id)


@router.get("/admin/broadcast/{broadcast_id}", response_model=BroadcastProgress)
async def get_broadcast_progress(
    request: Request, broadcast_id: str, admin: AdminDep
) -> dict:
    del admin
    progress = getattr(request.app.state, "broadcasts", {}).get(broadcast_id)
    if progress is None:
        raise HTTPException(status_code=404, detail="Xabar yuborish vazifasi topilmadi")
    return progress


def _settings_defaults() -> dict[str, object]:
    return {
        "dealership_name": "Buxara Avto Magnat",
        "address": "Buxoro shahar, Gazli shox ko'chasi, 500-uy. Mo'ljal: «Severniy» Guliston ko'prigi yonida.",
        "phones": json.dumps(["+998553054000", "+998996284000"]),
        "instagram": "volkswagenbuxara",
        "map_link": "",
        "annual_interest_rate": "",
        "working_hours": "",
        "banner_text": "",
    }


async def _read_settings(session: AsyncSession) -> dict[str, object]:
    result = await session.execute(select(Setting.key, Setting.value))
    values = _settings_defaults()
    for key, value in result.all():
        values[key] = value
    try:
        phones = json.loads(str(values["phones"]))
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=503, detail="Telefon sozlamalari noto'g'ri"
        ) from exc
    if not isinstance(phones, list) or any(
        not isinstance(phone, str) for phone in phones
    ):
        raise HTTPException(status_code=503, detail="Telefon sozlamalari noto'g'ri")
    values["phones"] = phones
    rate = str(values["annual_interest_rate"]).strip()
    values["annual_interest_rate"] = float(rate) if rate else None
    values["map_link"] = str(values["map_link"]) or None
    values["working_hours"] = str(values["working_hours"]) or None
    values["banner_text"] = str(values["banner_text"]) or None
    return values


@router.get("/admin/settings", response_model=SettingsRead)
async def get_admin_settings(session: SessionDep, admin: AdminDep) -> dict:
    del admin
    return await _read_settings(session)


@router.put("/admin/settings", response_model=SettingsRead)
async def update_admin_settings(
    payload: SettingsUpdate,
    request: Request,
    session: SessionDep,
    admin: OwnerDep,
) -> dict:
    changes = payload.model_dump(exclude_unset=True)
    current = await _read_settings(session)
    if any(
        changes.get(key) is None
        for key in ("address", "phones", "instagram")
        if key in changes
    ):
        raise HTTPException(
            status_code=422,
            detail="Manzil, telefon va Instagram qiymati bo'sh bo'lishi mumkin emas",
        )
    after = dict(current)
    after.update(changes)
    for key, value in changes.items():
        if key == "annual_interest_rate" and value is None:
            await session.execute(delete(Setting).where(Setting.key == key))
            continue
        if key == "phones":
            stored = json.dumps(value, ensure_ascii=False)
        else:
            stored = "" if value is None else str(value)
        setting = await session.get(Setting, key)
        if setting is None:
            session.add(Setting(key=key, value=stored))
        else:
            setting.value = stored
    await _audit(
        session,
        request,
        admin,
        action="settings.update",
        entity="settings",
        entity_id=None,
        before=current,
        after=after,
    )
    await session.commit()
    return await _read_settings(session)


@router.get("/admin/stats", response_model=AdminStats)
async def get_admin_stats(session: SessionDep, admin: AdminDep) -> AdminStats:
    del admin
    now = datetime.now(UTC)
    today = now.date()
    today_start = datetime.combine(today, datetime.min.time(), tzinfo=UTC)
    week_start = now - timedelta(days=7)
    month_start = datetime.combine(
        today.replace(day=1), datetime.min.time(), tzinfo=UTC
    )
    users_total = await session.scalar(select(func.count(User.id))) or 0
    users_new = (
        await session.scalar(
            select(func.count(User.id)).where(
                User.created_at >= now - timedelta(days=30)
            )
        )
        or 0
    )
    total_leads = await session.scalar(select(func.count(Lead.id))) or 0
    leads_today = (
        await session.scalar(
            select(func.count(Lead.id)).where(Lead.created_at >= today_start)
        )
        or 0
    )
    leads_week = (
        await session.scalar(
            select(func.count(Lead.id)).where(Lead.created_at >= week_start)
        )
        or 0
    )
    leads_month = (
        await session.scalar(
            select(func.count(Lead.id)).where(Lead.created_at >= month_start)
        )
        or 0
    )
    status_result = await session.execute(
        select(Lead.status, func.count(Lead.id)).group_by(Lead.status)
    )
    leads_by_status = {status.value: count for status, count in status_result.all()}
    car_result = await session.execute(
        select(Car.brand, Car.model, func.count(Lead.id))
        .join(Lead, Lead.car_id == Car.id)
        .group_by(Car.id, Car.brand, Car.model)
        .order_by(func.count(Lead.id).desc(), Car.id)
        .limit(5)
    )
    leads_by_car = [
        {"car": f"{brand} {model}", "count": count}
        for brand, model, count in car_result.all()
    ]
    done_count = leads_by_status.get(LeadStatus.DONE.value, 0)
    chart_start = today - timedelta(days=29)
    daily_result = await session.execute(
        select(func.date(Lead.created_at), func.count(Lead.id))
        .where(
            Lead.created_at
            >= datetime.combine(chart_start, datetime.min.time(), tzinfo=UTC)
        )
        .group_by(func.date(Lead.created_at))
    )
    daily_counts = {str(day): count for day, count in daily_result.all()}
    daily_leads = [
        {
            "date": (chart_start + timedelta(days=index)).isoformat(),
            "count": daily_counts.get(
                (chart_start + timedelta(days=index)).isoformat(), 0
            ),
        }
        for index in range(30)
    ]
    return AdminStats(
        users_total=users_total,
        users_new_30d=users_new,
        leads_today=leads_today,
        leads_week=leads_week,
        leads_month=leads_month,
        leads_total=total_leads,
        leads_by_status=leads_by_status,
        leads_by_car=leads_by_car,
        conversion_new_to_done_percent=round(done_count * 100 / total_leads, 1)
        if total_leads
        else 0.0,
        daily_leads_30d=daily_leads,
    )


@router.get("/admin/audit", response_model=AuditLogPage)
async def list_audit_logs(
    session: SessionDep,
    admin: OwnerDep,
    limit: int = Query(default=25, ge=1, le=PAGE_LIMIT),
    offset: int = Query(default=0, ge=0),
) -> AuditLogPage:
    del admin
    total = await session.scalar(select(func.count(AuditLog.id))) or 0
    result = await session.execute(
        select(AuditLog)
        .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
        .limit(limit)
        .offset(offset)
    )
    return AuditLogPage(
        items=[AuditLogRead.model_validate(entry) for entry in result.scalars().all()],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/admin/admin-users", response_model=list[AdminAccountRead])
async def list_admin_accounts(session: SessionDep, admin: OwnerDep) -> list[AdminUser]:
    del admin
    result = await session.execute(
        select(AdminUser).order_by(AdminUser.created_at, AdminUser.id)
    )
    return list(result.scalars().all())


@router.post(
    "/admin/admin-users",
    response_model=AdminAccountRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_admin_account(
    payload: AdminAccountCreate,
    request: Request,
    session: SessionDep,
    admin: OwnerDep,
) -> AdminUser:
    existing = await session.scalar(
        select(AdminUser.id).where(AdminUser.username == payload.username)
    )
    if existing is not None:
        raise HTTPException(status_code=409, detail="Bu login allaqachon ishlatilgan")
    account = AdminUser(
        username=payload.username,
        password_hash=await run_in_threadpool(hash_password, payload.password),
        role=payload.role,
    )
    session.add(account)
    try:
        await session.flush()
        await _audit(
            session,
            request,
            admin,
            action="admin_user.create",
            entity="admin_user",
            entity_id=account.id,
            after={"username": account.username, "role": account.role},
        )
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=409, detail="Bu login allaqachon ishlatilgan"
        ) from exc
    await session.refresh(account)
    return account


@router.put(
    "/admin/admin-users/{admin_id}/password", status_code=status.HTTP_204_NO_CONTENT
)
async def reset_admin_account_password(
    admin_id: int,
    payload: AdminAccountPassword,
    request: Request,
    session: SessionDep,
    admin: OwnerDep,
) -> Response:
    account = await session.get(AdminUser, admin_id)
    if account is None:
        raise HTTPException(status_code=404, detail="Admin hisobi topilmadi")
    account.password_hash = await run_in_threadpool(hash_password, payload.password)
    account.refresh_token_id = None
    await _audit(
        session,
        request,
        admin,
        action="admin_user.password_reset",
        entity="admin_user",
        entity_id=account.id,
    )
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.patch("/admin/admin-users/{admin_id}", status_code=status.HTTP_204_NO_CONTENT)
async def set_admin_account_active(
    admin_id: int,
    payload: AdminAccountActive,
    request: Request,
    session: SessionDep,
    admin: OwnerDep,
) -> Response:
    account = await session.get(AdminUser, admin_id)
    if account is None:
        raise HTTPException(status_code=404, detail="Admin hisobi topilmadi")
    if account.id == admin.id and not payload.is_active:
        raise HTTPException(
            status_code=422, detail="O'zingizning hisobingizni o'chira olmaysiz"
        )
    before = {"is_active": account.is_active}
    account.is_active = payload.is_active
    if not account.is_active:
        account.refresh_token_id = None
    await _audit(
        session,
        request,
        admin,
        action="admin_user.active_update",
        entity="admin_user",
        entity_id=account.id,
        before=before,
        after={"is_active": account.is_active},
    )
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
