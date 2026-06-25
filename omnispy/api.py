"""omnispy HTTP API (FastAPI).

Single endpoint, POST /query, that wraps `omnispy.agents.router.run`.
"""

from fastapi import FastAPI
from pydantic import BaseModel

from omnispy.agents.router import run

app = FastAPI(title="omnispy")


class QueryIn(BaseModel):
    q: str


class QueryOut(BaseModel):
    answer: str


@app.post("/query", response_model=QueryOut)
def query_endpoint(body: QueryIn) -> QueryOut:
    return QueryOut(answer=run(body.q))


@app.get("/healthz")
def healthz() -> dict:
    return {"status": "ok"}