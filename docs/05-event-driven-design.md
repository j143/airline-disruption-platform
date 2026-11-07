# Event-Driven Architecture

## Event categories

| Category | Examples |
|---|---|
| Operational | `flight.delayed`, `flight.cancelled`, `flight.diverted`, `aircraft.changed` |
| Commercial | `booking.created`, `booking.cancelled`, `ticket.issued`, `ticket.rebooked` |
| Fulfillment | `checkin.completed`, `boardingpass.issued`, `boardingpass.revoked` |
| Baggage | `baggage.checked_in`, `baggage.loaded`, `baggage.unload_requested`, `baggage.reconciled` |
| Financial | `payment.authorized`, `payment.captured`, `refund.requested`, `refund.completed` |
| Recovery | `disruption.created`, `rebooking.initiated`, `rebooking.confirmed`, `notification.requested` |

## Cancellation event fan-out

```text
flight.cancelled
  |
  +-- checkin.invalidated
  |
  +-- boardingpass.revoked
  |
  +-- baggage.unload.requested
  |
  +-- passenger.notification.requested
  |
  +-- rebooking.initiated
  |
  +-- ancillary.compensation.requested
  |
  +-- refund.eligibility.evaluated
```

## Kafka topics

| Topic | Producer | Consumers |
|---|---|---|
| `flight-operations.events` | Flight Operations | Check-in, Baggage, Rebooking, Notification, Analytics |
| `reservation.events` | Reservation | Ticketing, Analytics, Search |
| `ticketing.events` | Ticketing | Check-in, Boarding, Rebooking, Finance |
| `payment.events` | Payment | Ticketing, Finance, Reconciliation |
| `seat-inventory.events` | Seat Inventory | Reservation, Check-in, Rebooking |
| `baggage.events` | Baggage | Airport systems, Reconciliation, Analytics |
| `notification.requests` | Any domain service | Notification Service |
| `notification.delivery.events` | Notification Service | Analytics, Support |
| `rebooking.events` | Rebooking | Reservation, Ticketing, Seat Inventory, Payment |
| `dead-letter.<source-topic>` | Consumer error handler | Operations and support tooling |

## Transactional outbox

```text
Business transaction
  |
  +-- Update flight_instance
  +-- Insert outbox_event
  |
  v
Same PostgreSQL transaction commits
  |
  v
Outbox relay reads unpublished events
  |
  v
Publish to Kafka
  |
  v
Mark event published
```

Rules:

- Never publish directly from the request path and assume success.
- Never update business state and publish to Kafka in separate non-atomic operations.
- Use at-least-once delivery.
- Consumers must deduplicate by `event_id`.
- Preserve event ordering per aggregate where required; for example, all events for one `flight_instance_id` should use the same partition key.

## Consumer isolation

A failure in one consumer must not block the others.

Use independent consumer groups and independent retry policies:

```text
flight.cancelled
  |
  +-- checkin-invalidation-consumer
  +-- boarding-revocation-consumer
  +-- baggage-unload-consumer
  +-- notification-consumer
  +-- rebooking-consumer
  +-- finance-compensation-consumer
```

If notification delivery fails, it retries independently. It must not prevent baggage unload requests or rebooking initiation.

## Retry policy

| Failure type | Strategy |
|---|---|
| Transient network or broker error | Exponential backoff with jitter |
| Downstream service unavailable | Retry with bounded attempts, then park in retry topic |
| Poison message | Route to DLQ after configured attempts |
| Business-rule rejection | Do not blindly retry; send to exception queue for review |
| Partial saga failure | Execute compensation or mark saga as awaiting recovery |

Example:

- Immediate retry: 3 attempts
- Delayed retry: 1 minute, 5 minutes, 15 minutes, 1 hour
- DLQ: after final retry or on non-retryable validation error
- Operations alert: DLQ depth greater than zero for critical topics

## Idempotency

Every mutating workflow needs an idempotency key:

| Workflow | Key |
|---|---|
| Payment | Client-supplied idempotency key |
| Refund | `(ticket_id, disruption_id, refund_type)` |
| Rebooking | `(booking_id, disruption_id)` |
| Seat assignment | `(ticket_id, flight_instance_id)` |
| Check-in | `(passenger_id, flight_instance_id)` |
| Notification | `(recipient_id, event_id, channel)` |
| Baggage unload | `(baggage_id, disruption_id)` |

The API gateway may reject duplicate requests early, but the owning service must still enforce idempotency in its database. Gateway-level deduplication is an optimization, not the correctness mechanism.
