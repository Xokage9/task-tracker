import os
from datetime import date, timedelta
from uuid import uuid4

import httpx
import pytest
from sqlalchemy import select
from webtest import TestApp

from core.database import SessionLocal
from core.models import OutboxEvent, utcnow
from core.worker import dispatch_once
from notifications.app import create_app as notifications_app
from notifications.storage import connect
from notifications.worker import deliver_once
from reports.app import aggregate, create_app as reports_app
from shared.security import issue_token


@pytest.fixture
def inbox(tmp_path):
    path = str(tmp_path / "notifications.db")
    app = notifications_app(path)
    return app.test_client(), path


def event(recipient=1, **extra):
    return {"event_id":str(uuid4()),"recipient_id":recipient,"recipient_email":"user@example.com",
            "kind":"task.created","title":"Новая задача","body":"Написать API","project_id":1,"task_id":1,**extra}


def test_inbox_auth_isolation_and_idempotency(inbox):
    client, _ = inbox
    data = event()
    service = {"X-Service-Token":os.environ["SERVICE_TOKEN"]}
    headers = {"Authorization":"Bearer "+issue_token(1)}
    other = {"Authorization":"Bearer "+issue_token(2)}
    assert client.post("/events",json=data).status_code==403
    assert client.post("/events",json={**data,"recipient_id":-1},headers=service).status_code==422
    assert client.post("/events",json=data,headers=service).json["duplicate"] is False
    assert client.post("/events",json=data,headers=service).json["duplicate"] is True
    assert client.get("/notifications").status_code==401
    assert client.get("/notifications",headers=other).json["total"]==0
    assert client.get("/notifications",headers=headers).json["unread_count"]==1
    assert client.patch(f'/notifications/{data["event_id"]}/read',headers=other).status_code==404
    assert client.patch(f'/notifications/{data["event_id"]}/read',headers=headers).status_code==200
    assert client.get("/notifications?unread_only=true",headers=headers).json["total"]==0
    client.post("/events",json=event(),headers=service)
    assert client.patch("/notifications/read-all",headers=headers).status_code==200
    assert client.get("/notifications",headers=headers).json["unread_count"]==0
    assert client.get("/notifications?limit=500",headers=headers).status_code==422


def test_outbox_retry_then_real_inbox_delivery(client, owner, project, inbox):
    response = client.post("/tasks",headers=owner[1],json={"project_id":project["id"],"title":"Очередь"})
    assert response.status_code==201
    failing = httpx.Client(transport=httpx.MockTransport(lambda req:httpx.Response(503)))
    assert dispatch_once(client=failing)==1
    with SessionLocal() as db:
        row = db.scalar(select(OutboxEvent))
        assert row.attempts==1 and row.delivered_at is None and row.last_error=="HTTPStatusError"
        payload = row.payload
        row.next_attempt_at=utcnow()-timedelta(seconds=1)
        db.commit()
    flask, _ = inbox
    def receive(request):
        result = flask.post("/events",data=request.content,content_type="application/json",headers={"X-Service-Token":request.headers["X-Service-Token"]})
        return httpx.Response(result.status_code,json=result.json)
    working = httpx.Client(transport=httpx.MockTransport(receive))
    assert dispatch_once(client=working)==1
    assert dispatch_once(client=working)==0
    # Replay after an ambiguous network outcome must not duplicate the notification.
    assert flask.post("/events",json=payload,headers={"X-Service-Token":os.environ["SERVICE_TOKEN"]}).json["duplicate"] is True
    headers={"Authorization":"Bearer "+issue_token(owner[0]["id"])}
    assert flask.get("/notifications",headers=headers).json["total"]==1
    with SessionLocal() as db:
        assert db.scalar(select(OutboxEvent)).delivered_at is not None
    failing.close();working.close()


def test_email_queue_retry_and_delivery(inbox):
    client, path = inbox
    data=event()
    client.post("/events",json=data,headers={"X-Service-Token":os.environ["SERVICE_TOKEN"]})
    def fail(_row):
        raise OSError("SMTP unavailable")
    assert deliver_once(path,sender=fail)
    with connect(path) as db:
        row=db.execute("SELECT * FROM notifications").fetchone()
        assert row["email_attempts"]==1 and row["email_sent_at"] is None
        db.execute("UPDATE notifications SET email_next_attempt=0")
    sent=[]
    assert deliver_once(path,sender=lambda row:sent.append(row["recipient_email"]))
    assert sent==["user@example.com"]
    assert not deliver_once(path,sender=lambda row:sent.append(row["recipient_email"]))


def test_reports_authorization_csv_and_counts(client, owner, project):
    first=client.post("/tasks",headers=owner[1],json={"project_id":project["id"],"title":"=SUM(A1:A2)","due_date":"2020-01-01"})
    assert first.status_code==201
    client.post("/tasks",headers=owner[1],json={"project_id":project["id"],"title":"Готовая задача","status":"done","priority":"high","due_date":"2020-01-01"})
    report = TestApp(reports_app(fetcher=lambda pid,auth:client.get(f"/projects/{pid}/report-data",headers={"Authorization":auth})))
    path=f'/reports/projects/{project["id"]}'
    report.get(path,status=401)
    report.get(path,headers={"Authorization":"Bearer invalid"},status=401)
    headers=owner[1]
    data=report.get(path,headers=headers).json
    assert data["total"]==2 and data["completion_percent"]==50 and data["overdue"]==1
    csv=report.get(path+".csv",headers=headers)
    assert csv.content_type=="text/csv"
    assert "'=SUM(A1:A2)" in csv.text and "Готовая задача" in csv.text
    report.post(path,headers=headers,status=405)
    unavailable=TestApp(reports_app(fetcher=lambda *_:httpx.Response(503,request=httpx.Request("GET","http://core"))))
    unavailable.get(path,headers=headers,status=503)


def test_empty_report():
    data=aggregate({"project":{"id":1},"tasks":[]},today=date(2026,1,1))
    assert data["completion_percent"]==0 and data["overdue"]==0 and data["workload"]==[]


def test_jwt_expiry_and_algorithm():
    import jwt
    from jwt import InvalidTokenError
    from shared.security import decode_token
    assert decode_token(issue_token(10))==10
    claims=jwt.decode(issue_token(10),options={"verify_signature":False})
    for updates,algorithm in [({"exp":1},"HS256"),({"aud":"another-app"},"HS256"),({},"HS384")]:
        token=jwt.encode({**claims,**updates},os.environ["JWT_SECRET"],algorithm=algorithm)
        with pytest.raises(InvalidTokenError):
            decode_token(token)
