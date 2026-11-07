# Interview Playbook

## Opening

Start by clarifying scope rather than drawing microservices immediately.

Possible clarifying questions:

- Is this a domestic carrier, international carrier, or both?
- What is the expected booking volume and peak concurrency?
- Do we own payment processing or integrate with a gateway?
- Do we integrate directly with airport Departure Control Systems and baggage systems?
- What are the rebooking policies for fare classes and loyalty tiers?
- Is real-time seat-map accuracy a hard requirement?
- What is the tolerance for eventual consistency in notifications and analytics?
- What are the regulatory, data-residency, and financial-audit requirements?
- Should the system support interline partners and codeshare flights?

## Functional requirements

State the core capabilities:

- Booking and PNR lifecycle.
- Passenger and travel-document management.
- Payment, ticket issuance, refunds, and ancillaries.
- Seat inventory and assignment.
- Check-in and boarding-pass lifecycle.
- Baggage allowance, tracking, and reconciliation.
- Flight operations and disruption management.
- Rebooking, notification, and recovery.

## Non-functional requirements

Prioritize:

- Correctness under concurrency.
- Financial idempotency.
- Operational availability during disruption.
- Event reliability and recoverability.
- Auditability.
- Security and privacy.
- Read scalability.
- Clear ownership boundaries.

## Capacity estimate

Use explicit assumptions:

- Assume 10 million monthly bookings.
- Assume 400,000 bookings per day.
- Assume peak booking rate of 5,000 per minute.
- Assume 50,000 flight-status events per hour during major disruption.
- Assume 10 million active passenger profiles.
- Assume 100 million historical tickets.

Then derive storage, read/write QPS, Kafka throughput, and database partitioning needs. State that these are assumptions and validate them with product and operations stakeholders.

## Core entities

Explain the distinction between:

- Flight: scheduled route and service.
- Flight instance: a specific dated departure.
- Booking: commercial reservation.
- Ticket: passenger travel entitlement.
- Check-in: fulfillment state.
- Boarding pass: credential.
- Baggage: physical item lifecycle.

## Architecture narrative

Say:

> I would start with a modular monolith with clear domain boundaries. Reservation, Ticketing, Payment, Seat Inventory, Check-in, Baggage, Flight Operations, Boarding, Notification, and Rebooking are separate modules with owned data. I would extract services only where ownership, scaling, availability, or deployment needs justify it.

## Deep dive: seat allocation

- Use PostgreSQL as the final authority.
- Use a unique constraint on `(flight_instance_id, seat_number)` for confirmed assignment.
- Use short-lived holds for user selection.
- Use Redis only for a fast availability projection and TTL-based hold coordination.
- Handle expired holds through a reconciler.
- Prevent overselling with transactional conditional updates.

## Deep dive: payment idempotency

- Client sends an idempotency key.
- Payment service stores the key and result.
- Repeated requests return the original result.
- Gateway calls use the same key where supported.
- Unknown gateway outcomes are reconciled by querying the gateway.
- Refunds use a deterministic idempotency key.

## Deep dive: cancellation

- Flight Operations commits `CANCELLED` and writes `flight.cancelled` to the outbox.
- Outbox relay publishes to Kafka.
- Independent consumers invalidate check-ins, revoke boarding passes, request baggage unload, initiate rebooking, request notifications, and evaluate refunds.
- Each consumer is idempotent.
- Failures do not block other consumers.
- Gate validation checks authoritative operational state.

## Deep dive: rebooking

- Create one idempotent rebooking case per booking and disruption.
- Prioritize special assistance, connections, families, and policy entitlements.
- Allocate seats transactionally with unique constraints.
- Preserve family grouping where possible.
- Offer voluntary later flights when capacity is insufficient.
- Use a waitlist for unallocated passengers.

## Deep dive: Kafka outage

- Cancellation succeeds because the authoritative state and outbox event are committed locally.
- Downstream actions are delayed.
- Outbox relay publishes after Kafka recovery.
- Consumers process events idempotently.
- Gate validation must not rely on stale cache data.

## Strong closing statement

> The system separates commercial state, operational state, and fulfillment state. It uses PostgreSQL for correctness, Redis only as an optimization, sagas for cross-domain workflows, and transactional outbox for reliable event delivery. Every retry path is idempotent, and every disruption action is observable, auditable, and recoverable.
