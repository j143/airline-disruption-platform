# Implementation

This repository now contains a runnable FastAPI implementation of the core reservation, seat, payment, cancellation, and rebooking workflows.

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
uvicorn app.main:app --reload
```

For PostgreSQL and the outbox relay:

```bash
docker compose up --build
```

## Implemented invariants

- Booking creation creates passengers and tickets in one transaction.
- Seat allocation uses a database-backed active-assignment check and emits a `seat.held` outbox event.
- Payment authorization is idempotent by `Idempotency-Key`.
- Flight cancellation updates authoritative operational state and writes `flight.cancelled` to the outbox in the same transaction.
- Rebooking is idempotent per `(booking_id, disruption_id)`.
- Rebooking holds a target seat, confirms it, reissues a ticket, and emits `rebooking.confirmed`.
- The outbox relay publishes pending events and marks them published only afterward.

## Next implementation steps

- Replace the console-based relay with `aiokafka` and partition by `aggregate_id`.
- Add independent consumers for check-in invalidation, boarding-pass revocation, baggage unload, notification, and refund eligibility.
- Add Redis-backed seat-hold caching while retaining PostgreSQL as the correctness boundary.
- Add Alembic migrations.
- Add integration tests for concurrent seat allocation and duplicate payment retries.
- Add OpenTelemetry tracing and Prometheus metrics.
