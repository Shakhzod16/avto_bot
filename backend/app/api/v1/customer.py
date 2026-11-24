"""Customer endpoints that require a verified Telegram identity."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.app.api.dependencies import get_current_customer
from backend.app.db.session import get_session
from backend.app.models import Car, Favorite, Trim, User
from backend.app.schemas.public import CarRead

router = APIRouter()
SessionDep = Annotated[AsyncSession, Depends(get_session)]
CustomerDep = Annotated[User, Depends(get_current_customer)]


@router.get("/favorites", response_model=list[CarRead])
async def list_favorites(session: SessionDep, customer: CustomerDep) -> list[Car]:
    """Return the authenticated customer's active favorite cars."""
    result = await session.execute(
        select(Car)
        .join(Favorite, Favorite.car_id == Car.id)
        .where(Favorite.user_id == customer.id, Car.is_active.is_(True))
        .options(
            selectinload(Car.trims.and_(Trim.is_active.is_(True))),
            selectinload(Car.images),
        )
        .order_by(Car.sort_order, Car.id)
    )
    return list(result.scalars().unique().all())


@router.put(
    "/favorites/{car_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
async def add_favorite(
    car_id: int,
    session: SessionDep,
    customer: CustomerDep,
) -> Response:
    """Add an active car to the authenticated customer's favorites."""
    car = await session.get(Car, car_id)
    if car is None or not car.is_active:
        raise HTTPException(status_code=404, detail="Mashina topilmadi")
    favorite = await session.get(Favorite, (customer.id, car_id))
    if favorite is None:
        session.add(Favorite(user_id=customer.id, car_id=car_id))
        await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete(
    "/favorites/{car_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
async def remove_favorite(
    car_id: int,
    session: SessionDep,
    customer: CustomerDep,
) -> Response:
    """Remove a car from the authenticated customer's favorites."""
    favorite = await session.get(Favorite, (customer.id, car_id))
    if favorite is not None:
        await session.delete(favorite)
        await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
