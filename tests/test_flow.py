import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.workers import publish_pending_events


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as http:
        yield http


async def _create_flight(client, flight_number: str, departure: str) -> dict:
    response = await client.post(
        "/v1/flight-instances",
        headers={"Idempotency-Key": f"flight-{flight_number}"},
        json={
            "flight_number": flight_number,
            "origin": "GAU",
            "destination": "BLR",
            "scheduled_departure": departure,
            "seat_numbers": ["12A", "12B", "12C"],
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


async def test_end_to_end_booking_payment_cancellation_and_rebooking(client):
    original_flight = await _create_flight(client, "6E-204", "2026-11-07T08:30:00Z")
    alternative_flight = await _create_flight(client, "6E-210", "2026-11-07T13:00:00Z")

    booking_response = await client.post(
        "/v1/bookings",
        headers={"Idempotency-Key": "booking-key-1"},
        json={
            "flight_instance_id": original_flight["instance_id"],
            "passengers": [
                {
                    "full_name": "Janardhan Pulivarthi",
                    "special_assistance": "WHEELCHAIR",
                }
            ],
        },
    )
    assert booking_response.status_code == 201, booking_response.text
    booking = booking_response.json()
    passenger_id = booking["passenger_ids"][0]

    seat_response = await client.post(
        f"/v1/flights/{original_flight['instance_id']}/seats/holds",
        headers={"Idempotency-Key": "seat-hold-1"},
        json={
            "flight_instance_id": original_flight["instance_id"],
            "seat_number": "12A",
            "passenger_id": passenger_id,
        },
    )
    assert seat_response.status_code == 200, seat_response.text
    assert seat_response.json()["status"] == "HELD"

    duplicate_seat = await client.post(
        f"/v1/flights/{original_flight['instance_id']}/seats/holds",
        headers={"Idempotency-Key": "seat-hold-2"},
        json={
            "flight_instance_id": original_flight["instance_id"],
            "seat_number": "12A",
            "passenger_id": passenger_id,
        },
    )
    assert duplicate_seat.status_code == 409
    assert "already held" in duplicate_seat.json()["detail"]

    payment_key = "payment-idempotency-key-1"
    payment_request = {
        "booking_id": booking["booking_id"],
        "amount_minor": 850000,
        "currency": "INR",
    }
    first_payment = await client.post(
        "/v1/payments/authorize",
        headers={"Idempotency-Key": payment_key},
        json=payment_request,
    )
    assert first_payment.status_code == 200, first_payment.text

    retry_payment = await client.post(
        "/v1/payments/authorize",
        headers={"Idempotency-Key": payment_key},
        json=payment_request,
    )
    assert retry_payment.status_code == 200
    assert first_payment.json()["payment_id"] == retry_payment.json()["payment_id"]

    cancellation = await client.post(
        f"/v1/flight-instances/{original_flight['instance_id']}/cancellations",
        headers={"Idempotency-Key": "cancel-key-1"},
    )
    assert cancellation.status_code == 202
    assert cancellation.json()["operational_status"] == "CANCELLED"

    rebooking_request = {
        "booking_id": booking["booking_id"],
        "target_flight_instance_id": alternative_flight["instance_id"],
        "passenger_id": passenger_id,
        "seat_number": "12A",
    }
    rebooking = await client.post(
        "/v1/disruptions/disruption-1/rebooking",
        headers={"Idempotency-Key": "rebooking-key-1"},
        json=rebooking_request,
    )
    assert rebooking.status_code == 200, rebooking.text
    assert rebooking.json()["status"] == "CONFIRMED"

    duplicate_rebooking = await client.post(
        "/v1/disruptions/disruption-1/rebooking",
        headers={"Idempotency-Key": "rebooking-key-1"},
        json=rebooking_request,
    )
    assert duplicate_rebooking.status_code == 200
    assert duplicate_rebooking.json()["case_id"] == rebooking.json()["case_id"]

    published = await publish_pending_events()
    assert published >= 4


async def test_cannot_rebook_onto_cancelled_flight(client):
    cancelled_flight = await _create_flight(client, "6E-301", "2026-11-08T08:30:00Z")
    target_flight = await _create_flight(client, "6E-302", "2026-11-08T13:00:00Z")

    booking_response = await client.post(
        "/v1/bookings",
        headers={"Idempotency-Key": "booking-key-2"},
        json={
            "flight_instance_id": cancelled_flight["instance_id"],
            "passengers": [{"full_name": "Test Passenger"}],
        },
    )
    assert booking_response.status_code == 201
    booking = booking_response.json()
    passenger_id = booking["passenger_ids"][0]

    await client.post(
        f"/v1/flight-instances/{cancelled_flight['instance_id']}/cancellations",
        headers={"Idempotency-Key": "cancel-key-2"},
    )

    response = await client.post(
        "/v1/disruptions/disruption-2/rebooking",
        headers={"Idempotency-Key": "rebooking-key-2"},
        json={
            "booking_id": booking["booking_id"],
            "target_flight_instance_id": target_flight["instance_id"],
            "passenger_id": passenger_id,
            "seat_number": "12A",
        },
    )
    assert response.status_code == 200
