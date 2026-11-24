"""Legacy import path for the inline Mini App entry button."""

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo

from backend.app.core.config import WEBAPP_URL, webapp_url_error


def main_reply_keyboard() -> InlineKeyboardMarkup | None:
    """Keep legacy handlers functional without creating a reply keyboard."""
    if webapp_url_error(WEBAPP_URL):
        return None
    return InlineKeyboardMarkup(
        inline_keyboard=[[
            InlineKeyboardButton(
                text="🚗 Katalogni ochish",
                web_app=WebAppInfo(url=WEBAPP_URL),
            )
        ]]
    )
