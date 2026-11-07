# Rebooking Algorithm

## Problem

There are 180 affected passengers but only 160 immediately available alternative seats:

- 1:00 PM flight: 60 seats
- 5:00 PM flight: 100 seats

The system must allocate scarce capacity fairly, safely, and without double-booking a seat.

## Allocation priorities

Use a deterministic priority score, then allocate in batches.

### Priority tiers

1. Passengers with safety, medical, or operational constraints.
2. Passengers requiring special assistance.
3. Unaccompanied minors and passengers with tight legal or humanitarian constraints.
4. Passengers with onward connections that cannot be protected on a later flight.
5. Families and groups, allocated together where possible.
6. Loyalty tier and fare-class entitlement, subject to policy.
7. Passengers who voluntarily accept a later flight.
8. Remaining passengers in a fair queue.

## Example allocation

| Group | Count | Preferred allocation |
|---|---:|---|
| Special assistance | 12 | Earlier flight where feasible |
| Connecting passengers | 25 | Earlier flight if connection can be protected |
| Families / groups | Variable | Same flight and adjacent seating where possible |
| Remaining passengers | Remainder | Split across available flights |

A practical initial allocation:

- Assign high-priority and connection-critical passengers to the 1:00 PM flight, subject to seat availability.
- Fill the remaining 1:00 PM seats with families and passengers who accept the earlier option.
- Allocate the 5:00 PM flight to remaining passengers.
- Offer voluntary later-flight options and compensation according to policy.
- Maintain a waitlist for passengers who cannot be accommodated immediately.

## Constraints

- Do not split a family across flights unless the passengers explicitly consent.
- Preserve special-assistance requirements and ensure the destination airport can support them.
- Protect onward connections only when the downstream flight can realistically be reached.
- Respect visa, travel-document, and international-transfer constraints.
- Do not allocate a paid extra-legroom seat unless inventory and fare rules permit it.
- Preserve meal and baggage entitlements or compensate them explicitly.

## Concurrency control

A passenger accepting a rebooking option performs:

1. Create or retrieve the idempotent rebooking case.
2. Begin a PostgreSQL transaction.
3. Lock or conditionally update the target seat inventory.
4. Create a seat hold with expiry.
5. Commit the hold.
6. Asynchronously complete ticket reissue, payment adjustment, notification, and check-in reset.

The final assignment uses a unique constraint:

```sql
ALTER TABLE seat_assignment
ADD CONSTRAINT uq_seat_assignment_active_seat
UNIQUE (seat_id);
```

For a given flight instance, a seat can have only one active assignment. Cancelled, expired, or released assignments must not violate this invariant; use partial indexes or status-aware constraints as appropriate.

## Preventing duplicate rebooking

```sql
INSERT INTO rebooking_case (
  case_id, booking_id, disruption_id, status, idempotency_key
)
VALUES (
  $1, $2, $3, 'INITIATED', $4
)
ON CONFLICT (booking_id, disruption_id)
DO NOTHING
RETURNING case_id;
```

If the insert conflicts, the service returns the existing case. This makes mobile-app retries safe even if the first request timed out after committing.

## Seat-hold expiry

- Hold duration: 5 to 10 minutes for passenger-selected rebooking.
- Hold duration: 30 to 60 seconds for an automated protection flow.
- On expiry, release the seat and notify the rebooking orchestrator.
- If payment succeeds after hold expiry, use a compensation workflow or revalidate inventory before finalizing.

## Fairness

Do not allocate purely by first-come-first-served. A passenger who retries fastest should not always consume the last scarce seat needed by a connecting passenger or a family.

Use:

- Priority tiers for critical passenger needs.
- Reservation windows for eligible passengers.
- Fair queuing within a tier.
- Manual operations override with audit trail.
