from contextlib import asynccontextmanager
import os
import threading

from fastapi import FastAPI, HTTPException
from sqlalchemy import text

from core.database import Base, SessionLocal, engine
from core.routers import projects, tasks, users
from shared.security import secret


@asynccontextmanager
async def lifespan(_app):
    secret("JWT_SECRET")
    secret("SERVICE_TOKEN")
    Base.metadata.create_all(engine)
    stopped = threading.Event()
    thread = None
    if os.getenv("OUTBOX_EMBEDDED", "false").lower() == "true":
        from core.worker import run_loop
        thread = threading.Thread(target=run_loop, args=(stopped,), daemon=True, name="outbox")
        thread.start()
    try:
        yield
    finally:
        stopped.set()
        if thread:
            thread.join(timeout=7)


app = FastAPI(title="Task Tracker", version="1.0.0", lifespan=lifespan,
              root_path=os.getenv("ROOT_PATH", ""), redoc_url=None)
app.include_router(users.router)
app.include_router(projects.router)
app.include_router(tasks.router)


@app.get("/health", tags=["system"])
def health():
    try:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
    except Exception:
        raise HTTPException(503, "Database unavailable")
    return {"status": "ok", "service": "core"}
