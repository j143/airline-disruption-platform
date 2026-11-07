"""Outbox relay worker.

In production, replace the console publisher with a Kafka producer. The
important invariant is that an event is marked published only after the
broker acknowledges it.
"""

import asyncio
import logging
from datetime import datetime, timezone

from sqlalchemy import select, update

from .core import SessionLocal, settings
from .models import OutboxEvent
from .outbox import event_message

logger = logging.getLogger(__name__)


async def publish_pending_events() -> int:
    published = 0
    async with SessionLocal() as session:
        result = await session.execute(
            select(OutboxEvent)
            .where(OutboxEvent.published_at.is_(None))
            .order_by(OutboxEvent.occurred_at)
            .limit(100)
        )
        events = result.scalars().all()

        for event in events:
            message = event_message(event)
            if settings.kafka_bootstrap_servers:
                # Integrate aiokafka here in a production deployment.
                logger.info("Would publish to Kafka: %s", message.decode())
            else:
                logger.info("Outbox event: %s", message.decode())

            await session.execute(
                update(OutboxEvent)
                .where(OutboxEvent.event_id == event.event_id)
                .values(published_at=datetime.now(timezone.utc))
            )
            published += 1

        await session.commit()
    return published


async def main() -> None:
    logging.basicConfig(level=logging.INFO)
    while True:
        try:
            count = await publish_pending_events()
            if count:
                logger.info("Published %d outbox events", count)
        except Exception:
            logger.exception("Outbox relay failed; will retry")
        await asyncio.sleep(2)


if __name__ == "__main__":
    asyncio.run(main())
