# Distributed Failure and Recovery

## Scenario

- Reservation Service is healthy.
- Flight Operations Service is healthy.
- Kafka is unavailable for four minutes.
- Notification Service is healthy.
- Redis loses its cache.
- PostgreSQL remains healthy.

## Does cancellation succeed?

Yes. The cancellation must succeed.

Flight Operations commits the authoritative state change and writes `flight.cancelled` to its transactional outbox in the same PostgreSQL transaction. Kafka unavailability delays event publication; it does not invalidate the operational decision.

```text
PostgreSQL transaction:
  UPDATE flight_instance SET operational_status = 'CANCELLED'
  INSERT INTO outbox_event (...)
COMMIT
```

After Kafka recovers, the outbox relay publishes the pending event.

## Kafka outage behavior

| Concern | Behavior |
|---|---|
| Cancellation state | Committed immediately in Flight Operations database |
| Downstream actions | Delayed until event publication resumes |
| Notifications | Delayed, then delivered after recovery |
| Baggage unload | Delayed, then requested after recovery |
| Rebooking | Delayed, then initiated after recovery |
| Gate validation | Must query authoritative Flight Operations state or a highly available operational read replica |
| Audit | Records the cancellation time, event creation time, publication time, and consumer processing time |

## Redis cache loss

Redis cache loss is acceptable if Redis is not the source of truth.

- Seat availability projections are rebuilt from PostgreSQL.
- Temporary holds may be lost, but their TTL and database reconciliation prevent permanent incorrect assignment.
- Confirmed seat assignments remain valid because they are stored in PostgreSQL.
- Rate limits may reset, which is acceptable for a short period.
- Do not use Redis as the only guard against double allocation.

## Conflicting manual status change

If an employee sets a subsystem’s flight status back to `SCHEDULED` while the authoritative system says `CANCELLED`:

1. Reject the stale write using `status_version` or an event-sequence check.
2. Preserve the authoritative `CANCELLED` state.
3. Raise a data-integrity incident.
4. Notify operations and support.
5. Gate validation must reject boarding because the authoritative state is `CANCELLED`.

The system must not allow a stale subsystem to override the operational source of truth.

## Gate scan during propagation

A passenger may scan a boarding pass while cancellation is propagating.

The gate service must perform an authoritative check:

```text
GET /flight-instances/{instance_id}/operational-state
```

If the authoritative state is `CANCELLED`, reject the scan and display:

- Flight cancelled.
- Passenger should proceed to the rebooking or recovery desk.
- Baggage reconciliation instructions where applicable.

If the authoritative service is temporarily unavailable, the gate should fail closed for boarding. It may display a degraded-service message, but it must not allow boarding based solely on a stale local cache.

## Recovery workflow

1. Outbox relay resumes and publishes pending events.
2. Consumers process events idempotently.
3. The disruption orchestrator identifies incomplete actions.
4. Failed actions are retried or moved to DLQ.
5. Operations dashboard shows:
   - Affected bookings.
   - Notifications sent and pending.
   - Bags unloaded and reconciled.
   - Rebooked passengers.
   - Refunds pending and completed.
   - Manual intervention cases.
6. Finance reconciliation verifies no duplicate refunds.

## Recovery invariants

- Every affected booking has exactly one rebooking case per disruption.
- Every eligible refund has at most one completed refund per idempotency key.
- Every loaded bag has an unload or reconciliation outcome.
- Every revoked boarding pass is traceable to a cancellation event.
- Every failed notification is either retried, delivered, or explicitly marked for manual follow-up.
