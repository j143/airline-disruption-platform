# Airline Reservation & Disruption Management Platform

A production-grade system design for an airline booking and disruption-management platform, modeled on the operational complexity of a large carrier such as IndiGo.

The project covers the complete passenger lifecycle: reservation, ticketing, payment, check-in, seat allocation, baggage, boarding, flight disruption, rebooking, refund, and recovery.

## Objective

Design a system that remains safe and recoverable when:

- Multiple passengers book or change the same seat concurrently.
- Payment requests are retried after a timeout.
- Kafka or another event backbone becomes unavailable.
- A flight is cancelled after passengers have checked in and baggage has been loaded.
- A downstream subsystem incorrectly restores an old flight status.
- A passenger is accidentally rebooked twice because the mobile app retries a timed-out request.

## Design principles

- **Separate commercial, operational, and fulfillment state.** A cancelled flight does not automatically mean every ticket is refunded; tickets may be eligible for rebooking.
- **Use the database as the source of truth.** Redis improves read latency and seat-hold coordination, but PostgreSQL constraints and transactions provide final correctness.
- **Use sagas for cross-service workflows.** Booking, payment authorization, ticket issuance, seat allocation, and rebooking are coordinated through compensating actions.
- **Use transactional outbox for reliable event publication.** Business state changes and outbound events are committed atomically; consumers deduplicate by event ID.
- **Design for at-least-once processing.** Every event consumer must be idempotent.
- **Make operations authoritative.** Flight Operations owns the canonical operational flight state; other services consume its events and maintain projections.

## Repository structure

```text
.
├── README.md
├── docs/
│   ├── 01-requirements.md
│   ├── 02-architecture.md
│   ├── 03-data-model.md
│   ├── 04-state-machines.md
│   ├── 05-event-driven-design.md
│   ├── 06-rebooking.md
│   ├── 07-financial-consistency.md
│   ├── 08-failure-recovery.md
│   ├── 09-apis.md
│   ├── 10-observability.md
│   └── 11-interview-playbook.md
└── diagrams/
    └── architecture.md
```

## Core scenario

Flight `6E-204`, Guwahati to Bengaluru, is cancelled after:

- 180 passengers are booked.
- 142 passengers have checked in.
- 96 bags have been loaded.
- 110 passengers are at the airport.
- 25 passengers have onward connections from Bengaluru.
- 12 passengers require special assistance.
- 8 passengers purchased extra-legroom seats.
- 15 passengers purchased prepaid meals.

Alternative capacity is limited:

- 1:00 PM flight: 60 available seats.
- 5:00 PM flight: 100 available seats.

The system must protect passenger safety, preserve financial correctness, prevent duplicate rebooking, reconcile baggage, and recover from partial failures.

## Key engineering decisions

| Problem | Decision |
|---|---|
| Double seat allocation | Database unique constraint on `(flight_instance_id, seat_number)` plus short-lived seat holds |
| Duplicate payment | Idempotency key stored with payment intent and result |
| Distributed booking workflow | Saga with compensating actions |
| Reliable event delivery | Transactional outbox and at-least-once consumers |
| Conflicting flight status | Flight Operations is authoritative; stale statuses are rejected using version and event sequencing |
| Duplicate rebooking | Idempotent rebooking request keyed by `(booking_id, disruption_id)` |
| Baggage reconciliation | Baggage lifecycle events and reconciliation workflow, not an immediate hard delete |
| Notification failure | Notification requests are durable events; delivery retries independently |

## Interview positioning

This is not a simple CRUD flight-booking application. The interesting problems are:

- State ownership across Booking, Ticket, Check-in, Seat, Baggage, and Flight Operations.
- Concurrent seat allocation and rebooking.
- Payment idempotency and refund compensation.
- Event ordering, retries, dead-letter queues, and eventual consistency.
- Operational recovery during an active disruption.
- Observability and auditability for an incident affecting hundreds of passengers.
