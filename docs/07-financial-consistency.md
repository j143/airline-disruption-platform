# Financial Consistency

## Principle

Money movement must be idempotent, auditable, and reconcilable. A refund workflow must never issue two refunds for the same original payment and disruption.

## Purchases affected by cancellation

| Purchase | Immediate action | Compensation policy |
|---|---|---|
| Original ticket | Keep ticket in `ISSUED` or mark `REFUND_PENDING` only after passenger choice | Rebooking or refund |
| Extra baggage | Keep entitlement if rebooked | Refund if passenger chooses refund or baggage cannot be transferred |
| Prepaid meal | Keep if same-day rebooking includes meal service | Refund or credit if service is not provided |
| Extra-legroom seat | Release original seat assignment | Refund or apply equivalent seat if available |
| Seat upgrade | Release original seat assignment | Refund or apply equivalent upgrade on new flight |
| Travel insurance | Preserve policy linkage | Follow insurer and policy rules |

## Refund idempotency

Create a deterministic refund idempotency key:

```text
refund:{payment_id}:{ticket_id}:{disruption_id}:{refund_type}
```

The refund table has:

```sql
idempotency_key VARCHAR(128) UNIQUE NOT NULL
```

If a retry arrives:

1. Look up the existing refund by idempotency key.
2. If it is already completed, return the existing result.
3. If it is pending, resume or reconcile it.
4. Never create a second gateway refund request.

## Refund saga

```text
Refund requested
  -> Validate ticket and payment
  -> Create refund record PENDING
  -> Call payment gateway
  -> Gateway accepts
  -> Mark refund PROCESSING
  -> Gateway confirms
  -> Mark refund COMPLETED
  -> Update ticket status
  -> Publish refund.completed
```

Compensation:

```text
Gateway timeout or unknown result
  -> Keep refund PENDING / PROCESSING
  -> Query gateway using idempotency key
  -> Reconcile result
  -> Do not issue a second refund blindly
```

## Ancillary compensation

Use separate compensation records for each ancillary item:

```text
ancillary_compensation
  compensation_id
  booking_id
  passenger_id
  item_type
  original_payment_id
  disruption_id
  action
  amount_minor
  status
  idempotency_key
```

Possible actions:

- `TRANSFER_TO_NEW_FLIGHT`
- `REFUND`
- `CREDIT`
- `WAIVE`
- `MANUAL_REVIEW`

## Financial reconciliation

Daily and event-driven reconciliation should compare:

- Payment-service records.
- Payment-gateway settlement files.
- Refund records.
- Ticket status changes.
- Ancillary compensation records.
- General-ledger or finance-system entries.

Alert when:

- A refund remains pending beyond its SLA.
- A gateway reports a refund that the platform does not recognize.
- The platform reports a refund that the gateway does not recognize.
- A refund amount does not match the eligible amount.
- Duplicate idempotency keys appear with different amounts.
