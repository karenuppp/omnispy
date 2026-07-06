"""Result query routes — list runs, tweets, stats."""

from fastapi import APIRouter, HTTPException, Query

from server.db import get_db

router = APIRouter(prefix="/api", tags=["results"])


@router.get("/tasks/{task_id}/runs")
def list_runs(task_id: int, page: int = Query(1, ge=1), size: int = Query(20, ge=1, le=100)):
    db = get_db()
    task = db.get_task(task_id)
    if not task:
        raise HTTPException(404, "Task not found")
    runs, total = db.list_runs(task_id, page, size)
    return {"items": runs, "total": total, "page": page, "size": size}


@router.get("/runs/{run_id}/tweets")
def list_run_tweets(run_id: int, page: int = Query(1, ge=1), size: int = Query(20, ge=1, le=100)):
    db = get_db()
    tweets, total = db.list_tweets_by_run(run_id, page, size)
    return {"items": tweets, "total": total, "page": page, "size": size}


@router.get("/tasks/{task_id}/tweets")
def list_task_tweets(task_id: int, page: int = Query(1, ge=1), size: int = Query(20, ge=1, le=100)):
    db = get_db()
    task = db.get_task(task_id)
    if not task:
        raise HTTPException(404, "Task not found")
    tweets, total = db.list_tweets_by_task(task_id, page, size)
    return {"items": tweets, "total": total, "page": page, "size": size}


@router.get("/stats")
def get_stats():
    db = get_db()
    return db.get_stats()
