"""Task CRUD routes."""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from server.db import get_db
from server.service import run_task

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


class TaskCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    type: str = Field(pattern="^(keyword|user|mixed)$")
    keywords: str = ""
    users: str = ""
    schedule: str = Field(min_length=1, max_length=100)
    enabled: int = 1


class TaskUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=200)
    type: str | None = Field(None, pattern="^(keyword|user|mixed)$")
    keywords: str | None = None
    users: str | None = None
    schedule: str | None = Field(None, min_length=1, max_length=100)
    enabled: int | None = None


@router.get("")
def list_tasks(page: int = Query(1, ge=1), size: int = Query(20, ge=1, le=100)):
    db = get_db()
    tasks, total = db.list_tasks(page, size)
    return {"items": tasks, "total": total, "page": page, "size": size}


@router.post("", status_code=201)
def create_task(body: TaskCreate):
    db = get_db()
    task = db.create_task(body.model_dump())
    return task


@router.get("/{task_id}")
def get_task(task_id: int):
    db = get_db()
    task = db.get_task(task_id)
    if not task:
        raise HTTPException(404, "Task not found")
    return task


@router.put("/{task_id}")
def update_task(task_id: int, body: TaskUpdate):
    db = get_db()
    data = {k: v for k, v in body.model_dump().items() if v is not None}
    task = db.update_task(task_id, data)
    if not task:
        raise HTTPException(404, "Task not found")
    return task


@router.delete("/{task_id}")
def delete_task(task_id: int):
    db = get_db()
    if not db.delete_task(task_id):
        raise HTTPException(404, "Task not found")
    return {"ok": True}


@router.post("/{task_id}/toggle")
def toggle_task(task_id: int):
    db = get_db()
    task = db.toggle_task(task_id)
    if not task:
        raise HTTPException(404, "Task not found")
    return task


@router.post("/{task_id}/run")
def trigger_task_run(task_id: int):
    """Trigger an immediate run of the task (synchronous, returns tweets)."""
    db = get_db()
    task = db.get_task(task_id)
    if not task:
        raise HTTPException(404, "Task not found")
    tweets = run_task(task_id, db=db)
    return {"tweets": tweets, "count": len(tweets)}
