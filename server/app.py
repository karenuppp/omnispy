"""FastAPI application factory. Lifespan manages DB lifecycle."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from server.db import close_db, get_db
from server.routes import tasks, search, results


@asynccontextmanager
async def lifespan(app: FastAPI):
    db = get_db()
    db.connect()
    yield
    close_db()


def create_app() -> FastAPI:
    app = FastAPI(lifespan=lifespan)

    app.include_router(tasks.router)
    app.include_router(search.router)
    app.include_router(results.router)

    # Serve frontend build if it exists
    import os
    frontend_dist = os.path.join(os.path.dirname(__file__), "frontend", "dist")
    if os.path.isdir(frontend_dist):
        app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="frontend")

    return app
