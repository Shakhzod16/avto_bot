"""Public API request and response schemas."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from backend.app.models.entities import LeadStatus, LeadType


class TrimRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    price: int | None


class CarImageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    path: str
    thumbnail_path: str | None
    is_cover: bool
    sort_order: int


class CarRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    slug: str
    brand: str
    model: str
    body_type: str
    engine: str
    power_hp: int
    emission: str
    drive: str
    transmission: str
    seats: int
    description: str | None
    trims: list[TrimRead] = Field(default_factory=list)
    images: list[CarImageRead] = Field(default_factory=list)


class CreditRequest(BaseModel):
    car_id: int | None = Field(default=None, gt=0)
    trim_id: int | None = Field(default=None, gt=0)
    amount: int | None = Field(default=None, gt=0)
    initial_percent: float = Field(20, ge=0, le=100)
    months: int = Field(36, gt=0, le=120)

    @model_validator(mode="after")
    def validate_price_source(self) -> CreditRequest:
        if (self.trim_id is None) == (self.amount is None):
            raise ValueError("trim_id yoki amount dan aynan bittasi kerak")
        if self.trim_id is not None and self.car_id is None:
            raise ValueError("trim_id bilan car_id ham ko'rsatilishi kerak")
        return self


class CreditResponse(BaseModel):
    amount: int
    initial_payment: int
    loan_amount: int
    initial_percent: float
    months: int
    annual_rate: float
    monthly_payment: int
    approximate: Literal[True] = True
    disclaimer: str = (
        "Bu taxminiy hisob-kitob, aniq shartlar uchun menejerga murojaat qiling."
    )


class ContactsRead(BaseModel):
    name: str
    address: str
    phones: list[str]
    instagram: str
    map_link: str | None
    telegram_url: str | None = None
    working_hours: str | None = None


class LeadCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    phone: str = Field(pattern=r"^\+998\d{9}$")
    car_id: int | None = Field(default=None, gt=0)
    trim_id: int | None = Field(default=None, gt=0)
    type: LeadType
    comment: str | None = Field(default=None, max_length=2000)

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 2:
            raise ValueError("Ism kamida 2 belgidan iborat bo'lishi kerak")
        return value

    @field_validator("phone", mode="before")
    @classmethod
    def normalize_phone(cls, value: str) -> str:
        digits = re.sub(r"\D", "", str(value))
        if digits.startswith("998") and len(digits) == 12:
            return f"+{digits}"
        return str(value).strip()

    @field_validator("comment")
    @classmethod
    def strip_comment(cls, value: str | None) -> str | None:
        return value.strip() or None if value else None

    @model_validator(mode="after")
    def require_car_for_trim(self) -> LeadCreate:
        if self.trim_id is not None and self.car_id is None:
            raise ValueError("Komplektatsiya uchun car_id ham ko'rsatilishi kerak")
        return self


class LeadRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    phone: str
    car_id: int | None
    trim_id: int | None
    type: LeadType
    status: LeadStatus
    created_at: datetime
