from datetime import date, datetime
from enum import StrEnum
from uuid import UUID

from sqlalchemy import Date, DateTime, Enum, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class TripStatus(StrEnum):
    """Lifecycle states for a trip planning record."""

    DRAFT = "draft"
    PLANNING = "planning"
    VALIDATING = "validating"
    READY = "ready"
    BOOKING = "booking"
    BOOKED = "booked"
    FAILED = "failed"


class BookingStatus(StrEnum):
    """Lifecycle states for provider booking attempts."""

    PENDING = "pending"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"
    FAILED = "failed"


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Application user account with role metadata."""

    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(320), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str | None] = mapped_column(String(255))
    roles: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)

    trips: Mapped[list["Trip"]] = relationship(back_populates="user")


class Trip(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Durable trip planning aggregate."""

    __tablename__ = "trips"

    user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[TripStatus] = mapped_column(Enum(TripStatus), default=TripStatus.DRAFT)
    origin: Mapped[str | None] = mapped_column(String(255))
    destination: Mapped[str | None] = mapped_column(String(255))
    start_date: Mapped[date | None] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)
    requirements: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    final_plan: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    user: Mapped[User | None] = relationship(back_populates="trips")
    itineraries: Mapped[list["Itinerary"]] = relationship(back_populates="trip")
    flights: Mapped[list["Flight"]] = relationship(back_populates="trip")
    hotels: Mapped[list["Hotel"]] = relationship(back_populates="trip")
    activities: Mapped[list["Activity"]] = relationship(back_populates="trip")
    bookings: Mapped[list["Booking"]] = relationship(back_populates="trip")


class Itinerary(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Day-level itinerary generated for a trip."""

    __tablename__ = "itineraries"

    trip_id: Mapped[UUID] = mapped_column(ForeignKey("trips.id"), index=True)
    day: Mapped[int] = mapped_column(Integer, nullable=False)
    date: Mapped[date | None] = mapped_column(Date)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    items: Mapped[list[dict]] = mapped_column(JSONB, default=list, nullable=False)

    trip: Mapped[Trip] = relationship(back_populates="itineraries")


class Flight(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Flight option or booking candidate associated with a trip."""

    __tablename__ = "flights"

    trip_id: Mapped[UUID] = mapped_column(ForeignKey("trips.id"), index=True)
    provider: Mapped[str] = mapped_column(String(120), nullable=False)
    flight_number: Mapped[str | None] = mapped_column(String(80))
    origin: Mapped[str] = mapped_column(String(120), nullable=False)
    destination: Mapped[str] = mapped_column(String(120), nullable=False)
    departure_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    arrival_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    price_amount: Mapped[float | None] = mapped_column(Numeric(12, 2))
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    raw: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    trip: Mapped[Trip] = relationship(back_populates="flights")


class Hotel(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Hotel or stay option associated with a trip."""

    __tablename__ = "hotels"

    trip_id: Mapped[UUID] = mapped_column(ForeignKey("trips.id"), index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    location: Mapped[str] = mapped_column(String(255), nullable=False)
    rating: Mapped[float | None] = mapped_column(Numeric(3, 2))
    nightly_price: Mapped[float | None] = mapped_column(Numeric(12, 2))
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    raw: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    trip: Mapped[Trip] = relationship(back_populates="hotels")


class Activity(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Activity, attraction, or experience associated with a trip."""

    __tablename__ = "activities"

    trip_id: Mapped[UUID] = mapped_column(ForeignKey("trips.id"), index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str] = mapped_column(String(120), nullable=False)
    location: Mapped[str | None] = mapped_column(String(255))
    price_amount: Mapped[float | None] = mapped_column(Numeric(12, 2))
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    raw: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    trip: Mapped[Trip] = relationship(back_populates="activities")


class Booking(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Provider booking attempt for a travel component."""

    __tablename__ = "bookings"

    trip_id: Mapped[UUID] = mapped_column(ForeignKey("trips.id"), index=True)
    booking_type: Mapped[str] = mapped_column(String(80), nullable=False)
    provider: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[BookingStatus] = mapped_column(Enum(BookingStatus), default=BookingStatus.PENDING)
    confirmation_code: Mapped[str | None] = mapped_column(String(120))
    payload: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    trip: Mapped[Trip] = relationship(back_populates="bookings")


class Conversation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Stored conversation history for trip planning interactions."""

    __tablename__ = "conversations"

    trip_id: Mapped[UUID | None] = mapped_column(ForeignKey("trips.id"), index=True)
    user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"), index=True)
    messages: Mapped[list[dict]] = mapped_column(JSONB, default=list, nullable=False)


class AgentLog(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Audit log entry for agent execution."""

    __tablename__ = "agent_logs"

    trip_id: Mapped[UUID | None] = mapped_column(ForeignKey("trips.id"), index=True)
    workflow_id: Mapped[UUID | None] = mapped_column(index=True)
    agent_name: Mapped[str] = mapped_column(String(120), index=True, nullable=False)
    status: Mapped[str] = mapped_column(String(80), nullable=False)
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    input: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    output: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    error: Mapped[str | None] = mapped_column(Text)


class ExecutionGraph(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Persisted workflow graph and execution state snapshot."""

    __tablename__ = "execution_graphs"

    trip_id: Mapped[UUID | None] = mapped_column(ForeignKey("trips.id"), index=True)
    workflow_id: Mapped[UUID] = mapped_column(index=True, nullable=False)
    graph: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    state: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
