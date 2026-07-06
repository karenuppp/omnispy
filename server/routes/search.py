"""Manual search route — one-shot search without creating a task."""

from fastapi import APIRouter
from pydantic import BaseModel, Field

from server.db import get_db
from server.service import run_manual_search

router = APIRouter(prefix="/api", tags=["search"])


class SearchRequest(BaseModel):
    type: str = Field(pattern="^(keyword|user)$")
    keywords: str = ""
    users: str = ""
    limit: int = Field(default=20, ge=1, le=100)


@router.post("/search")
def manual_search(body: SearchRequest):
    db = get_db()
    tweets = run_manual_search(
        query_type=body.type,
        keywords=body.keywords,
        users=body.users,
        limit=body.limit,
        db=db,
    )
    return {"tweets": tweets, "count": len(tweets)}
