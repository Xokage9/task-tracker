"""Local development gateway; production uses the separate Docker services."""
import os
import sys
import threading
import argparse
from contextlib import asynccontextmanager
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")
runtime = ROOT / ".runtime"
runtime.mkdir(exist_ok=True)
os.environ.setdefault("DATABASE_URL", f"sqlite:///{runtime / 'core.db'}")
os.environ.setdefault("NOTIFICATIONS_DB", str(runtime / "notifications.db"))
parser = argparse.ArgumentParser()
parser.add_argument("--port", type=int, default=int(os.getenv("PORT", "8080")))
parser.add_argument("--host", default="0.0.0.0")
args, _ = parser.parse_known_args()
port = args.port
os.environ.setdefault("CORE_URL", f"http://127.0.0.1:{port}/api")
os.environ.setdefault("NOTIFICATIONS_URL", f"http://127.0.0.1:{port}/notify")

import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.wsgi import WSGIMiddleware
from core.main import app as core_app
from core.worker import dispatch_once
from notifications.app import create_app as notifications_app
from reports.app import create_app as reports_app

stop = threading.Event()


def worker():
    while not stop.wait(1):
        try:
            dispatch_once()
        except Exception:
            import logging
            logging.exception("Local event delivery failed")


@asynccontextmanager
async def lifespan(_app):
    async with core_app.router.lifespan_context(core_app):
        thread = threading.Thread(target=worker, daemon=True)
        thread.start()
        yield
        stop.set()
        thread.join(timeout=6)


app = FastAPI(lifespan=lifespan, docs_url=None, openapi_url=None)
app.mount("/api", core_app)
app.mount("/notify", WSGIMiddleware(notifications_app()))
app.mount("/reports-api", WSGIMiddleware(reports_app()))
app.mount("/", StaticFiles(directory=ROOT / "frontend", html=True))

if __name__ == "__main__":
    uvicorn.run(app, host=args.host, port=port, log_level="info")
