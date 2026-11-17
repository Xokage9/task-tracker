import logging
import os
import signal
import smtplib
import ssl
import threading
import time
from email.message import EmailMessage

from dotenv import load_dotenv

from notifications.storage import connect, initialize

log = logging.getLogger("mailer")
stop = threading.Event()


def send_mail(row):
    message = EmailMessage()
    message["From"] = os.environ["SMTP_FROM"]
    message["To"] = row["recipient_email"]
    message["Subject"] = row["title"]
    message["Message-ID"] = f'<{row["event_id"]}@task-tracker.local>'
    message.set_content(row["body"])
    with smtplib.SMTP(os.environ["SMTP_HOST"], int(os.getenv("SMTP_PORT", "587")), timeout=10) as smtp:
        if os.getenv("SMTP_STARTTLS", "true").lower() == "true":
            smtp.starttls(context=ssl.create_default_context())
        if os.getenv("SMTP_USER"):
            smtp.login(os.environ["SMTP_USER"], os.environ["SMTP_PASSWORD"])
        smtp.send_message(message)


def deliver_once(db_path=None, sender=send_mail):
    with connect(db_path) as db:
        db.execute("BEGIN IMMEDIATE")
        row = db.execute("SELECT * FROM notifications WHERE email_sent_at IS NULL AND email_next_attempt <= ? "
                         "ORDER BY created_at LIMIT 1", (time.time(),)).fetchone()
        if row is None:
            return False
        try:
            sender(row)
            db.execute("UPDATE notifications SET email_sent_at=strftime('%Y-%m-%dT%H:%M:%fZ','now') WHERE event_id=?",
                       (row["event_id"],))
        except (OSError, smtplib.SMTPException, ValueError):
            attempts = row["email_attempts"] + 1
            db.execute("UPDATE notifications SET email_attempts=?, email_next_attempt=? WHERE event_id=?",
                       (attempts, time.time() + min(3600, 2 ** min(attempts, 12)), row["event_id"]))
            log.warning("SMTP delivery will be retried for event %s", row["event_id"])
    return True


def main():
    load_dotenv()
    logging.basicConfig(level=logging.INFO)
    if not os.getenv("SMTP_HOST") or not os.getenv("SMTP_FROM"):
        raise RuntimeError("Set SMTP_HOST and SMTP_FROM before starting the email profile")
    initialize()
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, lambda *_: stop.set())
    while not stop.is_set():
        try:
            found = deliver_once()
        except Exception:
            log.exception("Mailer iteration failed")
            found = False
        stop.wait(0.2 if found else 3)


if __name__ == "__main__":
    main()
