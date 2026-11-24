"""Backend maintenance commands."""

import argparse
import asyncio

from backend.app.api.v1.auth import bootstrap_owner
from backend.app.db.session import SessionFactory
from backend.app.main import initialize_database


async def _create_owner() -> None:
    await initialize_database()
    async with SessionFactory() as session:
        owner = await bootstrap_owner(session)
    print(f"Owner admin yaratildi: {owner.username}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Buxara Avto Magnat backend commands")
    parser.add_argument("command", choices=["create-owner"])
    args = parser.parse_args()
    if args.command == "create-owner":
        asyncio.run(_create_owner())


if __name__ == "__main__":
    main()
