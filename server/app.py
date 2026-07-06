"""FastAPI application factory. Lifespan manages DB + APScheduler."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from server.db import close_db, get_db
from server.routes import tasks, search, results
from server.scheduler import get_scheduler
from server.service import run_task
from server.config import server_settings


def _scheduled_run(task_id: int):
    """Callback for APScheduler — run a task."""
    db = get_db()
    run_task(task_id, db=db)


@asynccontextmanager
async def lifespan(app: FastAPI):
    db = get_db()
    db.connect()

    # Init scheduler and load all enabled tasks
    mgr = get_scheduler()
    mgr.init()
    all_tasks, _ = db.list_tasks(page=1, size=9999)
    mgr.reload_all(all_tasks, _scheduled_run)

    yield

    mgr.shutdown()
    close_db()


def create_app() -> FastAPI:
    app = FastAPI(lifespan=lifespan)

    app.include_router(tasks.router)
    app.include_router(search.router)
    app.include_router(results.router)

    import os
    frontend_dist = os.path.join(os.path.dirname(__file__), "frontend", "dist")
    if os.path.isdir(frontend_dist):
        app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="frontend")

    return app
