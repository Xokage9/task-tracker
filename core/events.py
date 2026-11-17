from uuid import uuid4

from sqlalchemy import select

from core.models import Membership, OutboxEvent, User


def notify_project(db, project_id: int, kind: str, title: str, body: str, task_id=None):
    recipients = db.scalars(select(User).join(Membership).where(Membership.project_id == project_id)).all()
    for user in recipients:
        event_id = str(uuid4())
        db.add(OutboxEvent(id=event_id, payload={
            "event_id": event_id, "recipient_id": user.id, "recipient_email": user.email,
            "kind": kind, "title": title[:200], "body": body[:5000],
            "project_id": project_id, "task_id": task_id,
        }))
