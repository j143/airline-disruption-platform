from datetime import datetime
from pydantic import BaseModel, Field


class PassengerCreate(BaseModel):
    full_name: str
    special_assistance: str | None = None
    loyalty_tier: str | None = None


class BookingCreate(BaseModel):
    passengers: list[PassengerCreate] = Field(min_length=1)
    flight_instance_id: str
    fare_class: str = "ECONOMY"


class BookingResponse(BaseModel):
    booking_id: str
    pnr: str
    status: str


class SeatHoldRequest(BaseModel):
    flight_instance_id: str
    seat_number: str
    passenger_id: str


class SeatHoldResponse(BaseModel):
    assignment_id: str
    status: str
    hold_expires_at: datetime | None


class PaymentRequest(BaseModel):
    booking_id: str
    amount_minor: int = Field(gt=0)
    currency: str = "INR"


class PaymentResponse(BaseModel):
    payment_id: str
    status: str
    idempotency_key: str


class RebookingRequest(BaseModel):
    booking_id: str
    target_flight_instance_id: str
    passenger_id: str
    seat_number: str


class RebookingResponse(BaseModel):
    case_id: str
    status: str
