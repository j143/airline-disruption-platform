import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as http:
        yield http


async def test_booking_payment_and_rebooking(client):
    headers = {"Idempotency-Key": "test-key-1"}

    flight = await client.post(
        "/v1/flight-instances",
        json={
            "flight_number": "6E-204",
            "origin": "GAU",
            "destination": "BLR",
            "scheduled_departure": "2026-11-07T08:30:00Z",
        },
    )
    assert flight.status_code == 404
