import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from .core import settings
from .models import Booking, FlightInstance, Passenger, Payment, RebookingCase, Seat, SeatAssignment, Ticket
from .outbox import record_event


def generate_pnr() -> str:
    return "".join(secrets.choice("ABCDEFGHJKLMNPQRSTUVWXYZ23456789") for _ in range(6))


async def create_flight_instance(
    session: AsyncSession,
    flight_number: str,
    origin: str,
    destination: str,
    scheduled_departure: datetime,
    seat_numbers: list[str],
) -> FlightInstance:
    instance = FlightInstance(
        flight_number=flight_number,
        origin=origin,
        destination=destination,
        scheduled_departure=scheduled_departure,
        operational_status="SCHEDULED",
    )
    session.add(instance)
    await session.flush()

    for seat_number in seat_numbers:
        session.add(
            Seat(
                flight_instance_id=instance.instance_id,
                seat_number=seat_number,
                seat_class="ECONOMY",
            )
        )

    record_event(
        session,
        "flight_instance.created",
        "FlightInstance",
        instance.instance_id,
        {
            "flight_number": flight_number,
            "origin": origin,
            "destination": destination,
            "seat_numbers": seat_numbers,
        },
    )
    await session.commit()
    return instance


async def create_booking(
    session: AsyncSession,
    flight_instance_id: str,
    passengers: list[dict],
    fare_class: str = "ECONOMY",
) -> tuple[Booking, list[str]]:
    instance = await session.get(FlightInstance, flight_instance_id)
    if instance is None:
        raise ValueError("flight instance not found")
    if instance.operational_status == "CANCELLED":
        raise ValueError("cannot book a cancelled flight")

    booking = Booking(pnr=generate_pnr(), status="CONFIRMED")
    session.add(booking)
    await session.flush()

    passenger_ids: list[str] = []
    for item in passengers:
        passenger = Passenger(
            booking_id=booking.booking_id,
            full_name=item["full_name"],
            special_assistance=item.get("special_assistance"),
            loyalty_tier=item.get("loyalty_tier"),
        )
        session.add(passenger)
        await session.flush()
        passenger_ids.append(passenger.passenger_id)

        session.add(
            Ticket(
                booking_id=booking.booking_id,
                passenger_id=passenger.passenger_id,
                flight_instance_id=flight_instance_id,
                fare_class=fare_class,
                status="RESERVED",
            )
        )

    record_event(
        session,
        "booking.created",
        "Booking",
        booking.booking_id,
        {
            "pnr": booking.pnr,
            "flight_instance_id": flight_instance_id,
            "passenger_ids": passenger_ids,
        },
    )
    await session.commit()
    return booking, passenger_ids


async def hold_seat(
    session: AsyncSession,
    flight_instance_id: str,
    seat_number: str,
    passenger_id: str,
) -> SeatAssignment:
    result = await session.execute(
        select(Seat).where(
            Seat.flight_instance_id == flight_instance_id,
            Seat.seat_number == seat_number,
        )
    )
    seat = result.scalar_one_or_none()
    if seat is None:
        raise ValueError("seat not found")

    active = await session.execute(
        select(SeatAssignment).where(
            SeatAssignment.seat_id == seat.seat_id,
            SeatAssignment.status.in_(["HELD", "CONFIRMED"]),
        )
    )
    existing = active.scalar_one_or_none()
    if existing is not None:
        if existing.status == "HELD" and existing.hold_expires_at and existing.hold_expires_at < datetime.now(timezone.utc):
            existing.status = "RELEASED"
            await session.flush()
        else:
            raise ValueError("seat already held or assigned")

    assignment = SeatAssignment(
        seat_id=seat.seat_id,
        passenger_id=passenger_id,
        status="HELD",
        hold_expires_at=datetime.now(timezone.utc) + timedelta(seconds=settings.seat_hold_seconds),
    )
    session.add(assignment)

    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        raise ValueError("seat allocation conflict") from exc

    record_event(
        session,
        "seat.held",
        "SeatAssignment",
        assignment.assignment_id,
        {
            "flight_instance_id": flight_instance_id,
            "seat_number": seat_number,
            "passenger_id": passenger_id,
        },
    )
    await session.commit()
    return assignment


async def authorize_payment(
    session: AsyncSession,
    booking_id: str,
    idempotency_key: str,
    amount_minor: int,
    currency: str = "INR",
) -> Payment:
    result = await session.execute(
        select(Payment).where(Payment.idempotency_key == idempotency_key)
    )
    existing = result.scalar_one_or_none()
    if existing is not None:
        return existing

    payment = Payment(
        booking_id=booking_id,
        idempotency_key=idempotency_key,
        amount_minor=amount_minor,
        currency=currency,
        status="AUTHORIZED",
    )
    session.add(payment)

    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        result = await session.execute(
            select(Payment).where(Payment.idempotency_key == idempotency_key)
        )
        existing = result.scalar_one_or_none()
        if existing is None:
            raise ValueError("payment idempotency conflict") from exc
        return existing

    record_event(
        session,
        "payment.authorized",
        "Payment",
        payment.payment_id,
        {"booking_id": booking_id, "amount_minor": amount_minor, "currency": currency},
    )
    await session.commit()
    return payment


async def cancel_flight(session: AsyncSession, instance_id: str) -> FlightInstance:
    instance = await session.get(FlightInstance, instance_id)
    if instance is None:
        raise ValueError("flight instance not found")
    if instance.operational_status == "CANCELLED":
        return instance

    instance.operational_status = "CANCELLED"
    instance.status_version += 1

    record_event(
        session,
        "flight.cancelled",
        "FlightInstance",
        instance.instance_id,
        {
            "flight_number": instance.flight_number,
            "status_version": instance.status_version,
        },
    )
    await session.commit()
    return instance


async def accept_rebooking(
    session: AsyncSession,
    booking_id: str,
    disruption_id: str,
    target_flight_instance_id: str,
    passenger_id: str,
    seat_number: str,
) -> RebookingCase:
    idempotency_key = f"rebooking:{booking_id}:{disruption_id}"

    result = await session.execute(
        select(RebookingCase).where(RebookingCase.idempotency_key == idempotency_key)
    )
    existing = result.scalar_one_or_none()
    if existing is not None:
        return existing

    target = await session.get(FlightInstance, target_flight_instance_id)
    if target is None or target.operational_status == "CANCELLED":
        raise ValueError("target flight is unavailable")

    case = RebookingCase(
        booking_id=booking_id,
        disruption_id=disruption_id,
        status="SEAT_HELD",
        idempotency_key=idempotency_key,
    )
    session.add(case)

    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        result = await session.execute(
            select(RebookingCase).where(RebookingCase.idempotency_key == idempotency_key)
        )
        existing = result.scalar_one_or_none()
        if existing is None:
            raise ValueError("rebooking conflict") from exc
        return existing

    assignment = await hold_seat(session, target_flight_instance_id, seat_number, passenger_id)
    assignment.status = "CONFIRMED"

    result = await session.execute(
        select(Ticket).where(
            Ticket.booking_id == booking_id,
            Ticket.passenger_id == passenger_id,
        )
    )
    original_ticket = result.scalar_one_or_none()
    if original_ticket is not None:
        original_ticket.status = "REBOOKED"

    new_ticket = Ticket(
        booking_id=booking_id,
        passenger_id=passenger_id,
        flight_instance_id=target_flight_instance_id,
        fare_class=original_ticket.fare_class if original_ticket else "ECONOMY",
        status="ISSUED",
    )
    session.add(new_ticket)
    await session.flush()

    assignment.ticket_id = new_ticket.ticket_id
    case.status = "CONFIRMED"

    record_event(
        session,
        "rebooking.confirmed",
        "RebookingCase",
        case.case_id,
        {
            "booking_id": booking_id,
            "disruption_id": disruption_id,
            "new_flight_instance_id": target_flight_instance_id,
            "seat_number": seat_number,
        },
    )
    await session.commit()
    return case
