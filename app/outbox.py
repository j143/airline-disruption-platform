import json
from sqlalchemy.ext.asyncio import AsyncSession

from .models import OutboxEvent


def record_event(
    session: AsyncSession,
    event_type: str,
    aggregate_type: str,
    aggregate_id: str,
    payload: dict,
) -> OutboxEvent:
    """Queue a domain event in the same transaction as the business change."""
    event = OutboxEvent(
        aggregate_type=aggregate_type,
        aggregate_id=aggregate_id,
        event_type=event_type,
        payload=payload,
    )
    session.add(event)
    return event


def event_message(event: OutboxEvent) -> bytes:
    return json.dumps(
        {
            "event_id": event.event_id,
            "event_type": event.event_type,
            "aggregate_type": event.aggregate_type,
            "aggregate_id": event.aggregate_id,
            "payload": event.payload,
            "occurred_at": event.occurred_at.isoformat(),
        },
        default=str,
    ).encode()
