import os
import sqlite3
from pathlib import Path


def connect(path=None):
    path = path or os.getenv("NOTIFICATIONS_DB", "./notifications.db")
    Path(path).resolve().parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path, timeout=30)
    db.row_factory = sqlite3.Row
    return db


def initialize(path=None):
    with connect(path) as db:
        db.execute("PRAGMA journal_mode=WAL")
        db.executescript("""
            CREATE TABLE IF NOT EXISTS notifications (
                event_id TEXT PRIMARY KEY,
                recipient_id INTEGER NOT NULL,
                recipient_email TEXT NOT NULL,
                kind TEXT NOT NULL,
                title TEXT NOT NULL,
                body TEXT NOT NULL,
                project_id INTEGER NOT NULL,
                task_id INTEGER,
                created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
                read_at TEXT,
                email_sent_at TEXT,
                email_attempts INTEGER NOT NULL DEFAULT 0,
                email_next_attempt REAL NOT NULL DEFAULT 0
            );
            CREATE INDEX IF NOT EXISTS ix_notifications_recipient
                ON notifications(recipient_id, created_at);
        """)
