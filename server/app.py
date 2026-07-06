"""FastAPI application factory. Lifespan manages DB lifecycle."""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from server.db import close_db, get_db
from server.routes import tasks


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    db = get_db()
    db.connect()
    yield
    # Shutdown
    close_db()


def create_app() -> FastAPI:
    app = FastAPI(lifespan=lifespan)

    # REST API routes
    app.include_router(tasks.router)

    return app
