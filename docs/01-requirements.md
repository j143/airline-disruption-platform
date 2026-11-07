# Functional and Non-Functional Requirements

## Scope

The platform manages reservations, payments, ticketing, check-in, seat inventory, baggage, boarding, flight disruption, rebooking, refunds, and passenger notifications.

It must work during normal operations and during a major disruption where a flight is cancelled after passenger check-in and baggage loading.

## Functional requirements

### Reservation

- Create a booking containing one or more passengers and one or more flight segments.
- Assign a unique PNR to each booking.
- Retrieve booking details by PNR, booking ID, passenger contact details, or ticket number.
- Modify passenger details, contact information, special-assistance requirements, and ancillary services before departure where policy permits.
- Cancel a booking and determine refund eligibility according to fare rules.
- Maintain booking status independently from ticket, payment, check-in, and flight status.

### Ticketing and payments

- Authorize and capture payment through an external payment gateway.
- Issue one ticket per passenger per flight segment.
- Store ticket status separately from booking and payment status.
- Support refunds, partial refunds, and refund reversals where applicable.
- Ensure a retried payment request with the same idempotency key does not create a second charge.
- Compensate ancillary purchases when a flight is cancelled: extra baggage, prepaid meals, seat upgrades, and extra-legroom seats.

### Passenger profile

- Store passenger identity, contact details, travel-document metadata, frequent-flyer information, and special-assistance requirements.
- Support family or group bookings while retaining an individual passenger record.
- Protect sensitive identity and payment data; store only references, hashes, or tokenized values where appropriate.

### Check-in

- Allow eligible passengers to check in online, at a kiosk, or through an agent.
- Generate a boarding pass after successful check-in.
- Support undo check-in before the flight closes.
- Invalidate check-in and boarding passes when the associated flight instance is cancelled, diverted, or materially changed.

### Seat management

- Maintain seat inventory per flight instance.
- Support temporary seat holds with expiry.
- Prevent two passengers from permanently holding the same seat.
- Support seat changes, upgrades, paid extra-legroom seats, and family seating preferences.
- Preserve seat preferences during rebooking where an equivalent seat is available.

### Baggage

- Calculate allowance based on fare class, loyalty tier, route, and purchased ancillaries.
- Support excess-baggage purchase and payment.
- Track bag status: checked in, screened, loaded, unloaded, reconciled, transferred, or returned.
- During cancellation, generate an unload and reconciliation workflow for loaded bags.

### Flight operations

- Maintain scheduled flights and operational flight instances.
- Support delays, cancellations, diversions, aircraft changes, gate changes, and schedule revisions.
- Publish operational events to downstream systems.
- Act as the authoritative source for operational flight state.

### Boarding

- Validate boarding passes at the gate.
- Track boarding sequence and boarding status.
- Revoke boarding passes when a flight is cancelled or a passenger is moved to another flight.
- Prevent boarding after cancellation has been authoritatively published, even if a local subsystem has stale data.

### Disruption management

- Detect cancellation and create a disruption incident.
- Identify affected bookings, tickets, passengers, checked-in passengers, loaded bags, ancillaries, and onward connections.
- Notify affected passengers through email, SMS, and push notification.
- Offer rebooking options based on availability, fare rules, passenger priority, and operational constraints.
- Support voluntary acceptance of a later flight.
- Process refunds for passengers who do not accept rebooking.
- Reconcile baggage and special-assistance requirements at the destination or origin airport.

## Non-functional requirements

### Correctness

- A seat must never be permanently assigned to two passengers on the same flight instance.
- A payment must never be captured twice for the same idempotency key.
- A passenger must not receive two confirmed rebookings for the same disruption.
- A refund must not be issued twice for the same ticket and disruption.
- A passenger must not be allowed to board a cancelled flight.

### Availability and resilience

- Booking, check-in, and disruption workflows must remain available during partial downstream failures.
- Kafka unavailability must not prevent the authoritative cancellation state change from being committed.
- Redis cache loss must not cause incorrect seat allocation or lost business state.
- Notification-provider failures must be retried without blocking cancellation or rebooking.

### Consistency

- Use strong consistency for seat allocation, payment idempotency, ticket issuance, and rebooking confirmation.
- Use eventual consistency for read models, search indexes, analytics, and non-critical notifications.
- Use the transactional outbox pattern for reliable event publication.
- Consumers must tolerate duplicate events and out-of-order delivery where operationally possible.

### Performance

| Operation | Target |
|---|---|
| Flight search | p99 under 500 ms |
| Booking creation | p99 under 1 second |
| Payment authorization | p99 under 2 seconds, excluding gateway latency |
| Check-in | p99 under 1 second |
| Seat allocation | p99 under 300 ms |
| Cancellation propagation | 95% of critical downstream actions initiated within 30 seconds |
| Rebooking offer generation | p99 under 2 seconds |

These are design targets, not hard SLAs. The actual targets should be agreed with product, airport operations, and finance stakeholders.

### Scale

Initial design assumptions:

- 1,000 to 5,000 bookings per minute at peak.
- 10,000 to 50,000 flight-status events per hour during disruption periods.
- Millions of active bookings.
- Tens of millions of tickets and baggage events.
- Read-heavy traffic for flight status, PNR lookup, and seat maps.

The design should scale horizontally for stateless services and partition PostgreSQL by operational need where justified.

### Security and compliance

- Authenticate every client request.
- Authorize actions based on passenger, agent, airport staff, and operations roles.
- Encrypt data in transit and at rest.
- Use tokenization or references for payment credentials and government identity data.
- Maintain immutable audit records for cancellation, rebooking, refund, seat change, and boarding-pass revocation.
- Retain audit and financial records according to regulatory and airline-policy requirements.

### Observability

- Trace every booking, payment, rebooking, refund, and disruption workflow using correlation IDs.
- Emit domain metrics for saga progress, compensation, event lag, DLQ depth, and payment/refund reconciliation.
- Alert on stuck sagas, unpublished outbox events, duplicate-payment attempts, and failed critical notifications.
