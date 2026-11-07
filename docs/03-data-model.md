# Core Data Model

## Entity relationships

```text
Booking 1---N Passenger
Booking 1---N BookingSegment
BookingSegment N---1 FlightInstance
Passenger 1---N Ticket
Ticket N---1 FlightInstance
FlightInstance 1---N Seat
Seat 1---1 SeatAssignment
Passenger 1---N CheckIn
CheckIn 1---1 BoardingPass
Passenger 1---N Baggage
Payment 1---N Refund
Booking 1---N RebookingCase
```

## Important distinction

| Entity | Meaning |
|---|---|
| Flight | Scheduled route and service, for example `6E-204` Guwahati to Bengaluru |
| FlightInstance | A particular operational departure on a date, for example `6E-204` on 2026-11-07 |
| Booking | Commercial reservation containing passengers and segments |
| Ticket | Passenger travel entitlement for one flight segment |
| CheckIn | Passenger fulfillment state for a flight instance |
| BoardingPass | Credential generated after check-in |
| Baggage | Physical baggage item and its lifecycle |

## PostgreSQL schema

```sql
CREATE TABLE booking (
  booking_id UUID PRIMARY KEY,
  pnr VARCHAR(8) UNIQUE NOT NULL,
  status VARCHAR(32) NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE passenger (
  passenger_id UUID PRIMARY KEY,
  booking_id UUID NOT NULL REFERENCES booking(booking_id),
  full_name TEXT NOT NULL,
  contact_email TEXT,
  contact_phone TEXT,
  special_assistance TEXT,
  loyalty_tier TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE flight (
  flight_id UUID PRIMARY KEY,
  flight_number VARCHAR(16) NOT NULL,
  origin_airport VARCHAR(8) NOT NULL,
  destination_airport VARCHAR(8) NOT NULL
);

CREATE TABLE flight_instance (
  instance_id UUID PRIMARY KEY,
  flight_id UUID NOT NULL REFERENCES flight(flight_id),
  scheduled_departure TIMESTAMPTZ NOT NULL,
  scheduled_arrival TIMESTAMPTZ NOT NULL,
  aircraft_id VARCHAR(32),
  operational_status VARCHAR(32) NOT NULL,
  status_version BIGINT NOT NULL DEFAULT 0,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (flight_id, scheduled_departure)
);

CREATE TABLE ticket (
  ticket_id UUID PRIMARY KEY,
  booking_id UUID NOT NULL REFERENCES booking(booking_id),
  passenger_id UUID NOT NULL REFERENCES passenger(passenger_id),
  flight_instance_id UUID NOT NULL REFERENCES flight_instance(instance_id),
  fare_class VARCHAR(16) NOT NULL,
  status VARCHAR(32) NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE seat (
  seat_id UUID PRIMARY KEY,
  flight_instance_id UUID NOT NULL REFERENCES flight_instance(instance_id),
  seat_number VARCHAR(8) NOT NULL,
  seat_class VARCHAR(16) NOT NULL,
  extra_legroom BOOLEAN NOT NULL DEFAULT false,
  UNIQUE (flight_instance_id, seat_number)
);

CREATE TABLE seat_assignment (
  assignment_id UUID PRIMARY KEY,
  seat_id UUID NOT NULL REFERENCES seat(seat_id),
  passenger_id UUID NOT NULL REFERENCES passenger(passenger_id),
  ticket_id UUID NOT NULL REFERENCES ticket(ticket_id),
  status VARCHAR(32) NOT NULL,
  hold_expires_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (seat_id)
);

CREATE TABLE payment (
  payment_id UUID PRIMARY KEY,
  booking_id UUID NOT NULL REFERENCES booking(booking_id),
  idempotency_key VARCHAR(128) UNIQUE NOT NULL,
  amount_minor BIGINT NOT NULL,
  currency CHAR(3) NOT NULL,
  status VARCHAR(32) NOT NULL,
  gateway_reference VARCHAR(128),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE refund (
  refund_id UUID PRIMARY KEY,
  payment_id UUID NOT NULL REFERENCES payment(payment_id),
  ticket_id UUID REFERENCES ticket(ticket_id),
  disruption_id UUID,
  amount_minor BIGINT NOT NULL,
  currency CHAR(3) NOT NULL,
  status VARCHAR(32) NOT NULL,
  idempotency_key VARCHAR(128) UNIQUE NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE check_in (
  check_in_id UUID PRIMARY KEY,
  passenger_id UUID NOT NULL REFERENCES passenger(passenger_id),
  flight_instance_id UUID NOT NULL REFERENCES flight_instance(instance_id),
  status VARCHAR(32) NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (passenger_id, flight_instance_id)
);

CREATE TABLE boarding_pass (
  pass_id UUID PRIMARY KEY,
  check_in_id UUID NOT NULL REFERENCES check_in(check_in_id),
  sequence_number INT NOT NULL,
  status VARCHAR(32) NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  revoked_at TIMESTAMPTZ
);

CREATE TABLE baggage (
  baggage_id UUID PRIMARY KEY,
  passenger_id UUID NOT NULL REFERENCES passenger(passenger_id),
  flight_instance_id UUID NOT NULL REFERENCES flight_instance(instance_id),
  tag_number VARCHAR(32) NOT NULL,
  status VARCHAR(32) NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE rebooking_case (
  case_id UUID PRIMARY KEY,
  booking_id UUID NOT NULL REFERENCES booking(booking_id),
  disruption_id UUID NOT NULL,
  status VARCHAR(32) NOT NULL,
  selected_option_id UUID,
  idempotency_key VARCHAR(128) UNIQUE NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (booking_id, disruption_id)
);

CREATE TABLE outbox_event (
  event_id UUID PRIMARY KEY,
  aggregate_type VARCHAR(64) NOT NULL,
  aggregate_id UUID NOT NULL,
  event_type VARCHAR(96) NOT NULL,
  payload JSONB NOT NULL,
  occurred_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  published_at TIMESTAMPTZ,
  publish_attempts INT NOT NULL DEFAULT 0
);

CREATE INDEX idx_outbox_unpublished
  ON outbox_event (published_at, occurred_at)
  WHERE published_at IS NULL;
```

## Seat allocation correctness

The database constraint `UNIQUE (flight_instance_id, seat_number)` prevents two confirmed assignments for the same physical seat.

A temporary hold may be represented as:

```sql
INSERT INTO seat_assignment (
  assignment_id, seat_id, passenger_id, ticket_id, status, hold_expires_at
)
VALUES (
  $1, $2, $3, $4, 'HELD', now() + interval '10 minutes'
);
```

A background job or lazy expiration process releases expired holds. Redis can reduce repeated database reads, but it must never be the final authority for a confirmed seat assignment.

## Outbox pattern

When Flight Operations cancels a flight:

```sql
BEGIN;

UPDATE flight_instance
SET operational_status = 'CANCELLED',
    status_version = status_version + 1,
    updated_at = now()
WHERE instance_id = $1;

INSERT INTO outbox_event (
  event_id, aggregate_type, aggregate_id, event_type, payload
)
VALUES (
  $2, 'FlightInstance', $1, 'flight.cancelled', $3
);

COMMIT;
```

The outbox relay reads unpublished rows, publishes them to Kafka, and marks them published only after successful publication. Consumers deduplicate using `event_id`.
