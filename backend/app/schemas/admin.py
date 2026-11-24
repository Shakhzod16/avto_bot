"""Admin API request and response schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.app.models import LeadStatus, LeadType


class AdminSchema(BaseModel):
    """Base schema that rejects unrecognized admin input."""

    model_config = ConfigDict(extra="forbid")


class CarFields(AdminSchema):
    slug: str = Field(
        min_length=1, max_length=120, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$"
    )
    brand: str = Field(min_length=1, max_length=80)
    model: str = Field(min_length=1, max_length=120)
    body_type: str = Field(min_length=1, max_length=40)
    engine: str = Field(min_length=1, max_length=40)
    power_hp: int = Field(gt=0, le=3000)
    emission: str = Field(min_length=1, max_length=40)
    drive: Literal["AWD", "FWD"]
    transmission: str = Field(min_length=1, max_length=20)
    seats: int = Field(gt=0, le=20)
    description: str | None = Field(default=None, max_length=5000)
    is_active: bool = True
    sort_order: int = Field(default=0, ge=0)


class CarCreate(CarFields):
    pass


class CarUpdate(AdminSchema):
    slug: str | None = Field(
        default=None,
        min_length=1,
        max_length=120,
        pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$",
    )
    brand: str | None = Field(default=None, min_length=1, max_length=80)
    model: str | None = Field(default=None, min_length=1, max_length=120)
    body_type: str | None = Field(default=None, min_length=1, max_length=40)
    engine: str | None = Field(default=None, min_length=1, max_length=40)
    power_hp: int | None = Field(default=None, gt=0, le=3000)
    emission: str | None = Field(default=None, min_length=1, max_length=40)
    drive: Literal["AWD", "FWD"] | None = None
    transmission: str | None = Field(default=None, min_length=1, max_length=20)
    seats: int | None = Field(default=None, gt=0, le=20)
    description: str | None = Field(default=None, max_length=5000)
    is_active: bool | None = None
    sort_order: int | None = Field(default=None, ge=0)


class TrimCreate(AdminSchema):
    name: str = Field(min_length=1, max_length=120)
    price: int | None = Field(default=None, ge=0)
    is_active: bool = True
    sort_order: int = Field(default=0, ge=0)


class TrimUpdate(AdminSchema):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    price: int | None = Field(default=None, ge=0)
    is_active: bool | None = None
    sort_order: int | None = Field(default=None, ge=0)


class TrimRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    car_id: int
    name: str
    price: int | None
    is_active: bool
    sort_order: int


class CarOrder(AdminSchema):
    ids: list[int] = Field(min_length=1, max_length=500)


class ImageOrder(AdminSchema):
    ids: list[int] = Field(min_length=1, max_length=100)


class ImageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    car_id: int
    path: str
    thumbnail_path: str | None
    is_cover: bool
    sort_order: int


class AdminCarRead(BaseModel):
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
    is_active: bool
    sort_order: int
    trims: list[TrimRead] = Field(default_factory=list)
    images: list[ImageRead] = Field(default_factory=list)


class LeadUpdate(AdminSchema):
    status: LeadStatus | None = None
    internal_note: str | None = Field(default=None, max_length=5000)


class LeadAdminRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int | None
    name: str
    phone: str
    car_id: int | None
    trim_id: int | None
    type: LeadType
    comment: str | None
    internal_note: str | None
    status: LeadStatus
    created_at: datetime
    updated_at: datetime


class LeadPage(BaseModel):
    items: list[LeadAdminRead]
    total: int
    limit: int
    offset: int


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tg_id: int | None
    name: str | None
    username: str | None
    phone: str | None
    language: str
    is_blocked: bool
    created_at: datetime


class UserPage(BaseModel):
    items: list[UserRead]
    total: int
    limit: int
    offset: int


class UserBlockUpdate(AdminSchema):
    is_blocked: bool


class SettingsUpdate(AdminSchema):
    address: str | None = Field(default=None, min_length=1, max_length=300)
    phones: list[str] | None = Field(default=None, max_length=10)
    map_link: str | None = Field(default=None, max_length=1000)
    instagram: str | None = Field(default=None, max_length=120)
    annual_interest_rate: float | None = Field(default=None, ge=0, le=100)
    working_hours: str | None = Field(default=None, max_length=300)
    banner_text: str | None = Field(default=None, max_length=1000)

    @field_validator("phones")
    @classmethod
    def validate_phones(cls, phones: list[str] | None) -> list[str] | None:
        if phones is not None and any(
            len(phone) != 13 or not phone.startswith("+998") or not phone[1:].isdigit()
            for phone in phones
        ):
            raise ValueError("Telefon raqamlari +998XXXXXXXXX formatida bo'lishi kerak")
        return phones

    @field_validator("map_link")
    @classmethod
    def validate_map_link(cls, value: str | None) -> str | None:
        if (
            value is not None
            and value
            and not value.startswith(("https://", "http://"))
        ):
            raise ValueError(
                "Xarita havolasi http:// yoki https:// bilan boshlanishi kerak"
            )
        return value


class SettingsRead(BaseModel):
    address: str
    phones: list[str]
    map_link: str | None
    instagram: str
    annual_interest_rate: float | None
    working_hours: str | None
    banner_text: str | None


class BroadcastCreate(AdminSchema):
    text: str = Field(min_length=1, max_length=4096)
    segment: Literal["all", "with_leads", "without_leads"] = "all"
    mini_app_button: bool = False


class BroadcastAccepted(BaseModel):
    broadcast_id: str
    status: Literal["queued"] = "queued"


class BroadcastProgress(BaseModel):
    broadcast_id: str
    status: Literal["queued", "running", "completed", "failed"]
    total: int
    processed: int
    sent: int
    failed: int
    blocked: int
    error: str | None = None


class AdminStats(BaseModel):
    users_total: int
    users_new_30d: int
    leads_today: int
    leads_week: int
    leads_month: int
    leads_total: int
    leads_by_status: dict[str, int]
    leads_by_car: list[dict[str, int | str]]
    conversion_new_to_done_percent: float
    daily_leads_30d: list[dict[str, int | str]]


class AuditLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    admin_user_id: int | None
    action: str
    entity: str
    entity_id: str | None
    before_json: str | None
    after_json: str | None
    ip_address: str | None
    created_at: datetime


class AuditLogPage(BaseModel):
    items: list[AuditLogRead]
    total: int
    limit: int
    offset: int


class AdminAccountCreate(AdminSchema):
    username: str = Field(min_length=3, max_length=80, pattern=r"^[A-Za-z0-9_.-]+$")
    password: str = Field(min_length=12, max_length=256)
    role: Literal["manager"] = "manager"


class AdminAccountPassword(AdminSchema):
    password: str = Field(min_length=12, max_length=256)


class AdminAccountActive(AdminSchema):
    is_active: bool


class AdminAccountRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    role: str
    is_active: bool
    created_at: datetime
