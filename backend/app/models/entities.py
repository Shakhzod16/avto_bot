"""SQLAlchemy models for dealership catalog, customers and leads."""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy import (
    Enum as SAEnum,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.db.base import Base


class LeadType(str, Enum):
    """Supported customer request types."""

    TEST_DRIVE = "test_drive"
    BUY = "buy"
    CALLBACK = "callback"


class LeadStatus(str, Enum):
    """Lead workflow statuses."""

    NEW = "new"
    ACCEPTED = "accepted"
    CONTACTED = "contacted"
    CANCELLED = "cancelled"
    DONE = "done"


class User(Base):
    """Telegram or Mini App customer."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tg_id: Mapped[int | None] = mapped_column(Integer, unique=True, index=True)
    name: Mapped[str | None] = mapped_column(String(120))
    username: Mapped[str | None] = mapped_column(String(64))
    phone: Mapped[str | None] = mapped_column(String(16), index=True)
    language: Mapped[str] = mapped_column(String(8), default="uz", server_default="uz")
    is_blocked: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )

    leads: Mapped[list[Lead]] = relationship(back_populates="user")
    favorites: Mapped[list[Favorite]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class Car(Base):
    """Vehicle catalog item."""

    __tablename__ = "cars"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    brand: Mapped[str] = mapped_column(String(80))
    model: Mapped[str] = mapped_column(String(120))
    body_type: Mapped[str] = mapped_column(String(40), index=True)
    engine: Mapped[str] = mapped_column(String(40))
    power_hp: Mapped[int] = mapped_column(Integer)
    emission: Mapped[str] = mapped_column(String(40))
    drive: Mapped[str] = mapped_column(String(8), index=True)
    transmission: Mapped[str] = mapped_column(String(20))
    seats: Mapped[int] = mapped_column(Integer)
    description: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1")
    sort_order: Mapped[int] = mapped_column(Integer, default=0, server_default="0")

    trims: Mapped[list[Trim]] = relationship(
        back_populates="car",
        cascade="all, delete-orphan",
        order_by="Trim.sort_order",
    )
    images: Mapped[list[CarImage]] = relationship(
        back_populates="car",
        cascade="all, delete-orphan",
        order_by="CarImage.sort_order",
    )


class Trim(Base):
    """Vehicle trim and its integer price in so'm."""

    __tablename__ = "trims"
    __table_args__ = (
        UniqueConstraint("car_id", "name", name="uq_trims_car_name"),
        CheckConstraint(
            "price IS NULL OR price >= 0", name="ck_trims_price_nonnegative"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    car_id: Mapped[int] = mapped_column(
        ForeignKey("cars.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(120))
    price: Mapped[int | None] = mapped_column(Integer)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1")
    sort_order: Mapped[int] = mapped_column(Integer, default=0, server_default="0")

    car: Mapped[Car] = relationship(back_populates="trims")


class CarImage(Base):
    """Original, display and thumbnail paths for a car image."""

    __tablename__ = "car_images"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    car_id: Mapped[int] = mapped_column(
        ForeignKey("cars.id", ondelete="CASCADE"), index=True
    )
    path: Mapped[str] = mapped_column(String(500))
    thumbnail_path: Mapped[str | None] = mapped_column(String(500))
    is_cover: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    sort_order: Mapped[int] = mapped_column(Integer, default=0, server_default="0")

    car: Mapped[Car] = relationship(back_populates="images")


class Lead(Base):
    """Customer contact request."""

    __tablename__ = "leads"
    __table_args__ = (Index("ix_leads_status_created_at", "status", "created_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    name: Mapped[str] = mapped_column(String(120))
    phone: Mapped[str] = mapped_column(String(16), index=True)
    car_id: Mapped[int | None] = mapped_column(
        ForeignKey("cars.id", ondelete="SET NULL"), index=True
    )
    trim_id: Mapped[int | None] = mapped_column(
        ForeignKey("trims.id", ondelete="SET NULL"), index=True
    )
    type: Mapped[LeadType] = mapped_column(
        SAEnum(
            LeadType,
            name="lead_type",
            values_callable=lambda enum: [item.value for item in enum],
        ),
        index=True,
    )
    comment: Mapped[str | None] = mapped_column(Text)
    internal_note: Mapped[str | None] = mapped_column(Text)
    status: Mapped[LeadStatus] = mapped_column(
        SAEnum(
            LeadStatus,
            name="lead_status",
            values_callable=lambda enum: [item.value for item in enum],
        ),
        default=LeadStatus.NEW,
        server_default=LeadStatus.NEW.value,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    user: Mapped[User | None] = relationship(back_populates="leads")
    car: Mapped[Car | None] = relationship()
    trim: Mapped[Trim | None] = relationship()


class Favorite(Base):
    """A car saved by a customer."""

    __tablename__ = "favorites"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    car_id: Mapped[int] = mapped_column(
        ForeignKey("cars.id", ondelete="CASCADE"), primary_key=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    user: Mapped[User] = relationship(back_populates="favorites")
    car: Mapped[Car] = relationship()


class Setting(Base):
    """Key/value application setting."""

    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(120), primary_key=True)
    value: Mapped[str] = mapped_column(Text)


class AdminUser(Base):
    """Separate admin panel login."""

    __tablename__ = "admin_users"
    __table_args__ = (
        CheckConstraint("role IN ('owner', 'manager')", name="ck_admin_users_role"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(
        String(20), default="manager", server_default="manager"
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1")
    failed_login_attempts: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0"
    )
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    refresh_token_id: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class AuditLog(Base):
    """Admin action history."""

    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    admin_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("admin_users.id", ondelete="SET NULL"), index=True
    )
    action: Mapped[str] = mapped_column(String(80))
    entity: Mapped[str] = mapped_column(String(80))
    entity_id: Mapped[str | None] = mapped_column(String(80))
    before_json: Mapped[str | None] = mapped_column(Text)
    after_json: Mapped[str | None] = mapped_column(Text)
    ip_address: Mapped[str | None] = mapped_column(String(45))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
