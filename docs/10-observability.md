# Observability and Operations

## Traceability

Every request should carry:

- `trace_id`
- `span_id`
- `booking_id`
- `passenger_id`
- `flight_instance_id`
- `disruption_id`
- `idempotency_key`

Propagate these identifiers through API calls, Kafka headers, database audit records, and downstream service logs.

## Golden signals

| Signal | What to monitor |
|---|---|
| Latency | API p50, p95, p99 by endpoint |
| Traffic | Requests per second by endpoint and client type |
| Errors | HTTP 5xx, validation failures, gateway failures, consumer failures |
| Saturation | Database connections, Kafka consumer lag, CPU, memory, queue depth |

## Business metrics

| Metric | Alert condition |
|---|---|
| `disruption_active_count` | Unexpected increase |
| `outbox_unpublished_events` | Sustained growth |
| `outbox_publish_lag_seconds` | Above threshold |
| `consumer_lag_seconds` | Above threshold |
| `dlq_message_count` | Greater than zero for critical topics |
| `saga_stuck_count` | Greater than zero beyond timeout |
| `duplicate_payment_attempts` | Sudden increase |
| `refund_pending_age_seconds` | Above financial SLA |
| `boarding_rejections_due_to_cancellation` | Expected during cancellation; investigate anomalies |
| `notification_delivery_failure_rate` | Above threshold |
| `baggage_unreconciled_count` | Above threshold after cancellation |

## Alerts

### Critical

- Flight cancellation committed but outbox events are not publishing.
- Payment captured but ticket issuance repeatedly fails.
- Refund marked completed but gateway reconciliation fails.
- Gate is accepting boarding passes for a cancelled flight.
- Rebooking case exists but no ticket reissue after SLA.
- DLQ contains critical financial or safety-related events.

### High

- Notification delivery failure rate exceeds threshold.
- Kafka consumer lag exceeds threshold.
- Seat-hold cleanup job is failing.
- Baggage reconciliation backlog grows.
- Manual flight-status override conflicts with authoritative state.

## Audit events

Store immutable audit records for:

- Flight cancellation and status overrides.
- Booking modification and cancellation.
- Ticket issuance, reissue, and cancellation.
- Payment authorization, capture, refund, and reversal.
- Seat hold, assignment, release, and upgrade.
- Check-in and boarding-pass revocation.
- Baggage unload and reconciliation.
- Rebooking selection and confirmation.
- Manual operations override.

Each audit record should include actor, reason, before-state, after-state, correlation ID, and timestamp.

## Runbook

When Kafka is unavailable:

1. Confirm PostgreSQL is healthy.
2. Confirm Flight Operations has committed the cancellation.
3. Verify outbox backlog and publication attempts.
4. Ensure gate validation uses the authoritative operational state.
5. Pause non-critical batch consumers if needed to preserve capacity.
6. After Kafka recovery, monitor consumer lag and DLQ depth.
7. Reconcile notifications, baggage, refunds, and rebooking cases.
8. Publish an incident timeline using audit events.
