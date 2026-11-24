"""Callback tugmalar uchun turdagi ma'lumot fabrikalari."""

from aiogram.filters.callback_data import CallbackData


class CatalogCallback(CallbackData, prefix="catalog"):
    action: str
    car_id: str = ""


class TrimCallback(CallbackData, prefix="trim"):
    car_id: str


class BudgetCallback(CallbackData, prefix="budget"):
    action: str
    min_price: int = 0
    max_price: int = 0


class FilterCallback(CallbackData, prefix="filter"):
    kind: str
    value: str


class CompareCallback(CallbackData, prefix="compare"):
    action: str
    car_id: str = ""


class CreditCallback(CallbackData, prefix="credit"):
    action: str
    car_id: str = ""
    trim_name: str = ""
    value: int = 0
    down_percent: int = 0


class LeadCallback(CallbackData, prefix="lead"):
    action: str
    car_id: str = ""
    trim_name: str = ""


class LeadStatusCallback(CallbackData, prefix="lead_status"):
    lead_id: int
    status: str


class BroadcastCallback(CallbackData, prefix="broadcast"):
    action: str
