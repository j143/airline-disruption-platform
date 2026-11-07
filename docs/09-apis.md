# API Design

## Conventions

- Use HTTPS and OAuth 2.0 or OIDC for user and staff authentication.
- Use JSON for request and response bodies.
- Use cursor pagination for large result sets.
- Return `202 Accepted` for long-running workflows.
- Require `Idempotency-Key` for all mutating operations that may be retried.
- Return stable error codes and correlation IDs.

## Booking APIs

### Create booking

```http
POST /v1/bookings
Idempotency-Key: 7f3c...
```

Request:

```json
{
  "passengers": [
    {
      "full_name": "Janardhan Pulivarthi",
      "date_of_birth": "1990-01-01",
      "special_assistance": "WHEELCHAIR"
    }
  ],
  "segments": [
    {
      "flight_instance_id": "uuid",
      "fare_class": "ECONOMY"
    }
  ]
}
```

Response:

```json
{
  "booking_id": "uuid",
  "pnr": "ABC123",
  "status": "PENDING_PAYMENT"
}
```

### Retrieve booking

```http
GET /v1/bookings/{booking_id}
```

### Cancel booking

```http
POST /v1/bookings/{booking_id}/cancellations
Idempotency-Key: 9a2b...
```

## Payment APIs

### Authorize payment

```http
POST /v1/payments/authorize
Idempotency-Key: payment-key-123
```

### Capture payment

```http
POST /v1/payments/{payment_id}/capture
Idempotency-Key: capture-key-123
```

### Refund payment

```http
POST /v1/payments/{payment_id}/refunds
Idempotency-Key: refund-key-123
```

The service must return the same result for repeated requests using the same idempotency key.

## Check-in APIs

### Check in

```http
POST /v1/flights/{flight_instance_id}/check-in
Idempotency-Key: checkin-key-123
```

### Undo check-in

```http
POST /v1/check-ins/{check_in_id}/undo
Idempotency-Key: undo-key-123
```

### Generate boarding pass

```http
POST /v1/check-ins/{check_in_id}/boarding-pass
```

## Seat APIs

### Get seat map

```http
GET /v1/flights/{flight_instance_id}/seat-map
```

### Hold seat

```http
POST /v1/flights/{flight_instance_id}/seats/holds
Idempotency-Key: seat-hold-key-123
```

### Confirm seat

```http
POST /v1/seat-holds/{hold_id}/confirm
Idempotency-Key: seat-confirm-key-123
```

## Disruption APIs

### Cancel flight instance

```http
POST /v1/flight-instances/{instance_id}/cancellations
Idempotency-Key: cancellation-key-123
```

### Get disruption status

```http
GET /v1/disruptions/{disruption_id}
```

### List rebooking options

```http
GET /v1/disruptions/{disruption_id}/rebooking-options
```

### Accept rebooking option

```http
POST /v1/disruptions/{disruption_id}/rebooking
Idempotency-Key: rebooking-key-123
```

Request:

```json
{
  "option_id": "uuid",
  "accept_later_flight": false
}
```

Response:

```json
{
  "rebooking_case_id": "uuid",
  "status": "SEAT_HELD",
  "new_flight_instance_id": "uuid",
  "expires_at": "2026-11-07T10:35:00Z"
}
```

## Baggage APIs

### Request unload

```http
POST /v1/flights/{instance_id}/baggage/unload-requests
Idempotency-Key: unload-key-123
```

### Update baggage status

```http
PATCH /v1/baggage/{baggage_id}/status
```

## Gate validation API

### Validate boarding pass

```http
POST /v1/boarding/validate
```

Request:

```json
{
  "boarding_pass_id": "uuid",
  "gate_id": "A7",
  "scanned_at": "2026-11-07T08:31:00Z"
}
```

Response:

```json
{
  "decision": "REJECTED",
  "reason": "FLIGHT_CANCELLED",
  "authoritative_flight_status": "CANCELLED"
}
```
