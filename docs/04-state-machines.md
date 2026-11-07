# State Machines and Ownership

## Principle

Do not collapse booking, ticket, check-in, boarding-pass, baggage, and flight state into one status field. They have different lifecycles and different authoritative owners.

| Domain | Authoritative owner | Reason |
|---|---|---|
| Booking | Reservation Service | Owns commercial reservation lifecycle |
| Ticket | Ticketing Service | Owns travel entitlement and issuance |
| Payment and refund | Payment Service | Owns money movement and idempotency |
| Seat assignment | Seat Inventory Service | Owns physical inventory correctness |
| Check-in | Check-in Service | Owns passenger fulfillment state |
| Boarding pass | Check-in / Boarding Service | Owns credential issuance and revocation |
| Baggage | Baggage Service | Owns physical baggage lifecycle |
| Flight operational status | Flight Operations | Owns real-world operational truth |
| Rebooking | Rebooking and Recovery Service | Owns disruption recovery workflow |

## Flight instance

```text
SCHEDULED
  -> DELAYED
  -> BOARDING
  -> DEPARTED
  -> ARRIVED
  -> CANCELLED
  -> DIVERTED
```

Allowed transitions:

- `SCHEDULED -> DELAYED`
- `SCHEDULED -> BOARDING`
- `SCHEDULED -> CANCELLED`
- `DELAYED -> BOARDING`
- `DELAYED -> CANCELLED`
- `BOARDING -> DEPARTED`
- `BOARDING -> CANCELLED`
- `DEPARTED -> ARRIVED`
- `DEPARTED -> DIVERTED`

`CANCELLED` is terminal for the original flight instance. A new flight instance may be created for a replacement departure; the original instance must not be silently reset to `SCHEDULED`.

## Booking

```text
DRAFT
  -> PENDING_PAYMENT
  -> CONFIRMED
  -> MODIFIED
  -> CANCELLED
  -> DISRUPTED
  -> REBOOKED
  -> REFUNDED
```

Important rule: `DISRUPTED` is a booking-level commercial state, not a replacement for ticket or flight state.

A booking can be `DISRUPTED` while its original ticket remains `ISSUED`, because the passenger may choose rebooking rather than refund.

## Ticket

```text
RESERVED
  -> ISSUED
  -> CHECKED_IN
  -> BOARDED
  -> USED
  -> CANCELLED
  -> REBOOKED
  -> REFUND_PENDING
  -> REFUNDED
```

A ticket is not automatically cancelled when the flight is cancelled. It becomes eligible for rebooking, refund, or both depending on passenger choice and fare rules.

## Check-in

```text
NOT_CHECKED_IN
  -> CHECKED_IN
  -> BOARDING_PASS_ISSUED
  -> INVALIDATED
  -> RECHECKIN_REQUIRED
```

When the flight is cancelled:

1. Mark active check-ins as `INVALIDATED`.
2. Revoke associated boarding passes.
3. Preserve the historical record for audit and baggage reconciliation.
4. Create a `RECHECKIN_REQUIRED` task when the passenger accepts a new flight.

## Boarding pass

```text
ISSUED
  -> ACTIVE
  -> REVOKED
  -> SCANNED
  -> INVALID
```

A boarding pass must be validated against the authoritative flight-instance state at scan time. A stale local cache must never permit boarding after `flight.cancelled` has been committed.

Gate validation rule:

```text
IF flight_instance.operational_status != BOARDING
   OR boarding_pass.status != ACTIVE
   OR ticket.status NOT IN (ISSUED, CHECKED_IN)
THEN
   REJECT_SCAN
```

## Baggage

```text
ACCEPTED
  -> SCREENED
  -> LOADED
  -> UNLOAD_REQUESTED
  -> UNLOADED
  -> RECONCILED
  -> TRANSFERRED
  -> RETURNED_TO_PASSENGER
```

Cancellation does not delete baggage records. It creates an unload and reconciliation workflow, because bags may already be in a container, aircraft hold, or transfer system.

## Rebooking

```text
INITIATED
  -> OPTIONS_PRESENTED
  -> PASSENGER_SELECTED
  -> SEAT_HELD
  -> PAYMENT_PENDING
  -> CONFIRMED
  -> TICKET_REISSUED
  -> CHECKIN_REQUIRED
  -> COMPLETED
  -> FAILED
  -> CANCELLED
```

The rebooking case is idempotent per `(booking_id, disruption_id)`. A retry with the same key returns the existing case rather than creating another rebooking.

## Conflict resolution

If an employee manually changes a subsystem’s flight status back to `SCHEDULED` while Flight Operations still says `CANCELLED`:

1. Flight Operations remains authoritative.
2. The local subsystem receives a `flight.cancelled` event with a monotonically increasing `status_version`.
3. A stale write attempting to move the instance backward is rejected.
4. The discrepancy is written to an audit and reconciliation queue.
5. Gate validation checks the authoritative operational status before allowing boarding.

The system must fail closed: if authoritative status cannot be verified, the gate must not board the passenger.
