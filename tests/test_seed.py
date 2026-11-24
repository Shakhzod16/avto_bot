import asyncio
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import selectinload

from backend.app import seed
from backend.app.db.base import Base
from backend.app.models import Car, Trim


def test_catalog_seed_is_idempotent_and_includes_all_eight_cars(
    tmp_path: Path, monkeypatch
):
    async def check() -> None:
        engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'seed.db'}")
        factory = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        monkeypatch.setattr(seed, "SessionFactory", factory)

        assert await seed.seed_catalog() == 8
        assert await seed.seed_catalog() == 8

        async with factory() as session:
            assert await session.scalar(select(func.count(Car.id))) == 8
            assert await session.scalar(select(func.count(Trim.id))) == 14
            lavida = await session.scalar(
                select(Car)
                .where(Car.slug == "volkswagen-lavida-xr")
                .options(selectinload(Car.trims), selectinload(Car.images))
            )
            assert lavida is not None
            assert len(lavida.trims) == 1
            assert lavida.trims[0].price is None
            assert not lavida.images
            teramont_trim = await session.scalar(
                select(Trim).where(
                    Trim.car_id
                    == (
                        select(Car.id)
                        .where(Car.slug == "volkswagen-teramont-pro")
                        .scalar_subquery()
                    ),
                    Trim.name == "High",
                )
            )
            assert teramont_trim is not None
            teramont_trim.price = 1
            await session.commit()
        assert await seed.seed_catalog(only_if_empty=True) == 0
        async with factory() as session:
            preserved_trim = await session.scalar(
                select(Trim).where(Trim.name == "High")
            )
            assert preserved_trim is not None
            assert preserved_trim.price == 1
        await engine.dispose()

    asyncio.run(check())
