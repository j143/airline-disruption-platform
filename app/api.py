from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.ext.asyncio import AsyncSession

from .core import get_session
from .schemas import (
    BookingCreate,
    BookingResponse,
    FlightInstanceCreate,
    FlightInstanceResponse,
    PaymentRequest,
    PaymentResponse,
    RebookingRequest,
    RebookingResponse,
    SeatHoldRequest,
    SeatHoldResponse,
)
from .services import (
    accept_rebooking,
    authorize_payment,
    cancel_flight,
    create_booking,
    create_flight_instance,
    hold_seat,
)

router = APIRouter()


@router.post("/v1/flight-instances", response_model=FlightInstanceResponse, status_code=201)
async def create_flight_instance_api(
    request: FlightInstanceCreate,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    session: AsyncSession = Depends(get_session),
):
    instance = await create_flight_instance(
        session,
        request.flight_number,
        request.origin,
        request.destination,
        request.scheduled_departure,
        request.seat_numbers,
    )
    return FlightInstanceResponse(
        instance_id=instance.instance_id,
        flight_number=instance.flight_number,
        operational_status=instance.operational_status,
        seat_numbers=request.seat_numbers,
    )


@router.post("/v1/bookings", response_model=BookingResponse, status_code=201)
async def create_booking_api(
    request: BookingCreate,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    session: AsyncSession = Depends(get_session),
):
    try:
        booking, passenger_ids = await create_booking(
            session,
            request.flight_instance_id,
            [item.model_dump() for item in request.passengers],
            request.fare_class,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return BookingResponse(
        booking_id=booking.booking_id,
        pnr=booking.pnr,
        status=booking.status,
        passenger_ids=passenger_ids,
    )


@router.post("/v1/flights/{flight_instance_id}/seats/holds", response_model=SeatHoldResponse)
async def hold_seat_api(
    flight_instance_id: str,
    request: SeatHoldRequest,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    session: AsyncSession = Depends(get_session),
):
    try:
        assignment = await hold_seat(
            session,
            flight_instance_id,
            request.seat_number,
            request.passenger_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return SeatHoldResponse(
        assignment_id=assignment.assignment_id,
        status=assignment.status,
        hold_expires_at=assignment.hold_expires_at,
    )


@router.post("/v1/payments/authorize", response_model=PaymentResponse)
async def authorize_payment_api(
    request: PaymentRequest,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    session: AsyncSession = Depends(get_session),
):
    payment = await authorize_payment(
        session,
        request.booking_id,
        idempotency_key,
        request.amount_minor,
        request.currency,
    )
    return PaymentResponse(
        payment_id=payment.payment_id,
        status=payment.status,
        idempotency_key=payment.idempotency_key,
    )


@router.post("/v1/flight-instances/{instance_id}/cancellations", status_code=202)
async def cancel_flight_api(
    instance_id: str,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    session: AsyncSession = Depends(get_session),
):
    try:
        instance = await cancel_flight(session, instance_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {
        "instance_id": instance.instance_id,
        "operational_status": instance.operational_status,
        "status_version": instance.status_version,
    }


@router.post("/v1/disruptions/{disruption_id}/rebooking", response_model=RebookingResponse)
async def accept_rebooking_api(
    disruption_id: str,
    request: RebookingRequest,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    session: AsyncSession = Depends(get_session),
):
    try:
        case = await accept_rebooking(
            session,
            request.booking_id,
            disruption_id,
            request.target_flight_instance_id,
            request.passenger_id,
            request.seat_number,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return RebookingResponse(case_id=case.case_id, status=case.status)
