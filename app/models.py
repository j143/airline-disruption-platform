import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from .core import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def new_id() -> str:
    return str(uuid.uuid4())


class Booking(Base):
    __tablename__ = "booking"

    booking_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    pnr: Mapped[str] = mapped_column(String(8), unique=True, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="CONFIRMED")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Passenger(Base):
    __tablename__ = "passenger"

    passenger_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    booking_id: Mapped[str] = mapped_column(ForeignKey("booking.booking_id"), nullable=False)
    full_name: Mapped[str] = mapped_column(Text, nullable=False)
    special_assistance: Mapped[str | None] = mapped_column(Text)
    loyalty_tier: Mapped[str | None] = mapped_column(String(32))


class FlightInstance(Base):
    __tablename__ = "flight_instance"

    instance_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    flight_number: Mapped[str] = mapped_column(String(16), nullable=False)
    origin: Mapped[str] = mapped_column(String(8), nullable=False)
    destination: Mapped[str] = mapped_column(String(8), nullable=False)
    scheduled_departure: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    operational_status: Mapped[str] = mapped_column(String(32), nullable=False, default="SCHEDULED")
    status_version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class Seat(Base):
    __tablename__ = "seat"

    seat_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    flight_instance_id: Mapped[str] = mapped_column(ForeignKey("flight_instance.instance_id"), nullable=False)
    seat_number: Mapped[str] = mapped_column(String(8), nullable=False)
    seat_class: Mapped[str] = mapped_column(String(16), nullable=False, default="ECONOMY")
    extra_legroom: Mapped[bool] = mapped_column(Boolean, default=False)

    __table_args__ = (
        UniqueConstraint("flight_instance_id", "seat_number", name="uq_seat_instance_number"),
    )


class SeatAssignment(Base):
    __tablename__ = "seat_assignment"

    assignment_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    seat_id: Mapped[str] = mapped_column(ForeignKey("seat.seat_id"), nullable=False)
    passenger_id: Mapped[str] = mapped_column(ForeignKey("passenger.passenger_id"), nullable=False)
    ticket_id: Mapped[str | None] = mapped_column(ForeignKey("ticket.ticket_id"))
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    hold_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Ticket(Base):
    __tablename__ = "ticket"

    ticket_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    booking_id: Mapped[str] = mapped_column(ForeignKey("booking.booking_id"), nullable=False)
    passenger_id: Mapped[str] = mapped_column(ForeignKey("passenger.passenger_id"), nullable=False)
    flight_instance_id: Mapped[str] = mapped_column(ForeignKey("flight_instance.instance_id"), nullable=False)
    fare_class: Mapped[str] = mapped_column(String(16), nullable=False, default="ECONOMY")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="RESERVED")


class Payment(Base):
    __tablename__ = "payment"

    payment_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    booking_id: Mapped[str] = mapped_column(ForeignKey("booking.booking_id"), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    amount_minor: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="INR")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="AUTHORIZED")


class CheckIn(Base):
    __tablename__ = "check_in"

    check_in_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    passenger_id: Mapped[str] = mapped_column(ForeignKey("passenger.passenger_id"), nullable=False)
    flight_instance_id: Mapped[str] = mapped_column(ForeignKey("flight_instance.instance_id"), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="CHECKED_IN")

    __table_args__ = (
        UniqueConstraint("passenger_id", "flight_instance_id", name="uq_checkin_passenger_flight"),
    )


class RebookingCase(Base):
    __tablename__ = "rebooking_case"

    case_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    booking_id: Mapped[str] = mapped_column(ForeignKey("booking.booking_id"), nullable=False)
    disruption_id: Mapped[str] = mapped_column(String(36), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="INITIATED")
    selected_option_id: Mapped[str | None] = mapped_column(String(36))
    idempotency_key: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)

    __table_args__ = (
        UniqueConstraint("booking_id", "disruption_id", name="uq_rebooking_booking_disruption"),
    )


class OutboxEvent(Base):
    __tablename__ = "outbox_event"

    event_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    aggregate_type: Mapped[str] = mapped_column(String(64), nullable=False)
    aggregate_id: Mapped[str] = mapped_column(String(36), nullable=False)
    event_type: Mapped[str] = mapped_column(String(96), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON().with_variant(JSONB, "postgresql"), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
