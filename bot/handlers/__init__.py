"""Telegram bot handlerlari uchun paket."""
"""Telegram bot handlerlari."""

from aiogram import Dispatcher

from bot.handlers.common import router as common_router
from bot.handlers.leads import router as leads_router
from bot.handlers.smart import router as smart_router
from bot.handlers.start import router

__all__ = ["common_router", "leads_router", "router", "smart_router"]


def register_routers(dispatcher: Dispatcher) -> None:
    """Barcha handler routerlarini DIspatcherga ulaydi."""
    dispatcher.include_router(common_router)
    dispatcher.include_router(leads_router)
    dispatcher.include_router(smart_router)
    dispatcher.include_router(router)
