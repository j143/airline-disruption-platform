# High-Level Architecture

## Start with a modular monolith

Do not begin by splitting every domain into a microservice. Start with a modular monolith organized around clear domain boundaries, then extract services only when team ownership, scaling, deployment, or availability requirements justify it.

Recommended initial modules:

- Reservation
- Ticketing
- Payment
- Check-in
- Seat Inventory
- Baggage
- Flight Operations
- Boarding
- Notification
- Rebooking and Recovery

Each module owns its tables and publishes domain events. Shared databases are allowed only where a single service owns the data; cross-module access occurs through APIs or events.

## Logical components

```text
Clients
  Mobile app / Website / Kiosk / Agent portal
            |
            v
API Gateway
  Auth, rate limiting, routing, idempotency
            |
            v
+---------------------+     +---------------------+
| Reservation Service |---->| Ticketing Service   |
+---------------------+     +---------------------+
            |                          |
            v                          v
+---------------------+     +---------------------+
| Payment Service     |     | Seat Inventory      |
+---------------------+     +---------------------+
            |                          |
            +-----------+--------------+
                        v
              Transactional Outbox
                        |
                        v
              Kafka / Event Backbone
                        |
     +------------------+------------------+
     |                  |                  |
     v                  v                  v
Check-in          Baggage            Notification
Service           Service            Service
     |                  |                  |
     v                  v                  v
Boarding          Reconciliation      Passenger channels
Service

Flight Operations
  Authoritative operational flight state
  Publishes flight.cancelled, flight.delayed, etc.
```

## Service responsibilities

| Component | Primary responsibility | Source of truth |
|---|---|---|
| Reservation Service | PNR lifecycle, booking changes, cancellation requests | Booking tables |
| Ticketing Service | Ticket issuance, ticket status, travel entitlement | Ticket tables |
| Payment Service | Authorization, capture, refund, idempotency | Payment and refund tables |
| Seat Inventory | Seat availability, holds, assignment, upgrades | Seat and assignment tables |
| Check-in Service | Check-in lifecycle and boarding-pass generation | Check-in and boarding-pass tables |
| Baggage Service | Allowance, tags, loading, unloading, reconciliation | Baggage tables |
| Flight Operations | Operational flight state, disruption decisions | Flight-instance operational tables |
| Boarding Service | Gate validation and boarding state | Boarding event tables |
| Notification Service | Delivery orchestration and provider integration | Notification request tables |
| Rebooking Service | Disruption recovery and alternative itineraries | Rebooking and recovery tables |

## Data stores

| Store | Use |
|---|---|
| PostgreSQL | Bookings, tickets, payments, seats, check-ins, baggage, rebooking, outbox, audit events |
| Redis | Seat-hold TTL, hot availability cache, rate limiting, distributed locks where appropriate |
| Kafka | Domain events, integration events, retry and dead-letter topics |
| Object storage | Boarding-pass artifacts, documents, baggage images, exports |
| Search index | Flight search, passenger lookup, rebooking-option search |
| Data warehouse | Analytics, operational reporting, finance reconciliation, disruption analysis |

## Critical rule: Redis is not authoritative

Redis may hold:

- A temporary seat hold with TTL.
- A cached seat-map projection.
- A rate-limit counter.
- A distributed lock used only as an optimization.

But the final seat assignment must be enforced in PostgreSQL using a transaction and a uniqueness constraint.

## Cancellation flow

1. Flight Operations marks the flight instance as `CANCELLED` in its authoritative store.
2. It writes a `flight.cancelled` event to the transactional outbox in the same database transaction.
3. The outbox relay publishes the event to Kafka.
4. Downstream consumers independently process the event:
   - Check-in invalidation.
   - Boarding-pass revocation.
   - Baggage unload and reconciliation.
   - Passenger notification.
   - Rebooking initiation.
   - Refund eligibility evaluation.
5. Each consumer records its processing state and is idempotent by event ID.
6. The disruption orchestrator tracks completion, exceptions, and manual intervention queues.

## Why not one distributed transaction?

A cancellation affects multiple bounded contexts and external systems. A two-phase commit across PostgreSQL, Kafka, payment gateways, airport systems, and notification providers is impractical and fragile.

Instead:

- Commit the authoritative operational state locally.
- Publish the domain event reliably through the outbox.
- Let each consumer perform its own local transaction.
- Use compensating actions and reconciliation for failures.
- Use idempotency keys to make retries safe.
