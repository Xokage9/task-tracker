import hmac
from uuid import UUID

from dotenv import load_dotenv
from flask import Flask, g, jsonify, request
from jwt import InvalidTokenError
from pydantic import BaseModel, ConfigDict, EmailStr, Field, ValidationError
from werkzeug.exceptions import HTTPException

from notifications.storage import connect, initialize
from shared.security import decode_token, secret


class Event(BaseModel):
    model_config = ConfigDict(extra="forbid")
    event_id: UUID
    recipient_id: int = Field(gt=0)
    recipient_email: EmailStr
    kind: str = Field(min_length=1, max_length=50)
    title: str = Field(min_length=1, max_length=200)
    body: str = Field(max_length=5000)
    project_id: int = Field(gt=0)
    task_id: int | None = Field(default=None, gt=0)


def create_app(db_path=None):
    load_dotenv()
    secret("JWT_SECRET")
    service_token = secret("SERVICE_TOKEN")
    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = 64 * 1024
    initialize(db_path)

    def db():
        if "db" not in g:
            g.db = connect(db_path)
        return g.db

    @app.teardown_appcontext
    def close_db(_error):
        connection = g.pop("db", None)
        if connection is not None:
            connection.close()

    @app.errorhandler(HTTPException)
    def http_error(error):
        return jsonify(detail=error.description), error.code

    @app.before_request
    def authenticate():
        if request.path == "/events":
            if not hmac.compare_digest(request.headers.get("X-Service-Token", "").encode(), service_token.encode()):
                return jsonify(detail="Forbidden"), 403
        elif request.path.startswith("/notifications"):
            scheme, _, token = request.headers.get("Authorization", "").partition(" ")
            try:
                if scheme.lower() != "bearer":
                    raise ValueError("Missing bearer token")
                g.user_id = decode_token(token)
            except (InvalidTokenError, ValueError, TypeError):
                return jsonify(detail="Нужно войти в аккаунт"), 401

    @app.get("/health")
    def health():
        db().execute("SELECT 1 FROM notifications LIMIT 1")
        return {"status": "ok", "service": "notifications"}

    @app.post("/events")
    def receive_event():
        try:
            event = Event.model_validate(request.get_json()).model_dump(mode="json")
        except ValidationError:
            return jsonify(detail="Invalid event"), 422
        connection = db()
        cursor = connection.execute("""
            INSERT INTO notifications
            (event_id, recipient_id, recipient_email, kind, title, body, project_id, task_id)
            VALUES (:event_id, :recipient_id, :recipient_email, :kind, :title, :body, :project_id, :task_id)
            ON CONFLICT(event_id) DO NOTHING
        """, event)
        connection.commit()
        return jsonify(accepted=True, duplicate=cursor.rowcount == 0), 200

    @app.get("/notifications")
    def list_notifications():
        try:
            limit = int(request.args.get("limit", "50"))
            offset = int(request.args.get("offset", "0"))
            unread = request.args.get("unread_only", "false").lower()
            if not 1 <= limit <= 200 or offset < 0 or unread not in ("true", "false"):
                raise ValueError()
        except ValueError:
            return jsonify(detail="Invalid pagination or filter"), 422
        where = "recipient_id = ?" + (" AND read_at IS NULL" if unread == "true" else "")
        rows = db().execute(f"""SELECT event_id, kind, title, body, project_id, task_id, created_at, read_at
            FROM notifications WHERE {where} ORDER BY created_at DESC, event_id DESC LIMIT ? OFFSET ?""",
            (g.user_id, limit, offset)).fetchall()
        total = db().execute(f"SELECT count(*) FROM notifications WHERE {where}", (g.user_id,)).fetchone()[0]
        unread_count = db().execute("SELECT count(*) FROM notifications WHERE recipient_id=? AND read_at IS NULL",
                                    (g.user_id,)).fetchone()[0]
        return {"items": [dict(row) for row in rows], "total": total, "unread_count": unread_count}

    @app.patch("/notifications/read-all")
    def read_all():
        db().execute("UPDATE notifications SET read_at=strftime('%Y-%m-%dT%H:%M:%fZ','now') "
                     "WHERE recipient_id=? AND read_at IS NULL", (g.user_id,))
        db().commit()
        return {"ok": True}

    @app.patch("/notifications/<event_id>/read")
    def mark_read(event_id):
        cursor = db().execute("UPDATE notifications SET read_at=COALESCE(read_at, strftime('%Y-%m-%dT%H:%M:%fZ','now')) "
                              "WHERE event_id=? AND recipient_id=?", (event_id, g.user_id))
        db().commit()
        if not cursor.rowcount:
            return jsonify(detail="Уведомление не найдено"), 404
        return {"ok": True}

    return app
