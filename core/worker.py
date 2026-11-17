import logging
import os
import signal
import threading
from datetime import timedelta

import httpx
from sqlalchemy import select

from core.database import SessionLocal
from core.models import OutboxEvent, utcnow
from shared.security import secret

log = logging.getLogger("outbox")
stop = threading.Event()


def dispatch_once(session_factory=SessionLocal, client=None):
    owns_client = client is None
    client = client or httpx.Client(timeout=5, trust_env=False)
    processed = 0
    try:
        with session_factory() as db:
            events = db.scalars(select(OutboxEvent).where(
                OutboxEvent.delivered_at.is_(None), OutboxEvent.next_attempt_at <= utcnow(),
            ).order_by(OutboxEvent.next_attempt_at).limit(25).with_for_update(skip_locked=True)).all()
            for event in events:
                try:
                    response = client.post(os.getenv("NOTIFICATIONS_URL", "http://notifications:5000") + "/events",
                                           json=event.payload, headers={"X-Service-Token": secret("SERVICE_TOKEN")})
                    response.raise_for_status()
                    event.delivered_at = utcnow()
                    event.last_error = None
                except (httpx.HTTPError, OSError) as exc:
                    event.attempts += 1
                    event.last_error = type(exc).__name__
                    event.next_attempt_at = utcnow() + timedelta(seconds=min(300, 2 ** min(event.attempts, 9)))
                    log.warning("Delivery retry for event %s (%s)", event.id, event.last_error)
                processed += 1
            db.commit()
    finally:
        if owns_client:
            client.close()
    return processed


def run_loop(stop_event):
    while not stop_event.is_set():
        try:
            count = dispatch_once()
        except Exception:
            log.exception("Outbox iteration failed")
            count = 0
        stop_event.wait(0.2 if count else 2)


def main():
    logging.basicConfig(level=logging.INFO)
    secret("SERVICE_TOKEN")
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, lambda *_: stop.set())
    run_loop(stop)


if __name__ == "__main__":
    main()
