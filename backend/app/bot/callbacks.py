"""Typed callback payloads for admin lead actions."""

from aiogram.filters.callback_data import CallbackData


class LeadStatusCallback(CallbackData, prefix="lead_status"):
    """Lead status selected from an admin notification."""

    lead_id: int
    status: str
