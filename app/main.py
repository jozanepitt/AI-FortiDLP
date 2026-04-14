"""FastAPI entrypoint for the FortiDLP agent."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .agent.canned_queries import list_canned, run_canned
from .agent.claude_client import ClaudeAgent
from .agent.fortidlp_client import FortiDLPClient
from .config import get_settings

logger = logging.getLogger(__name__)

WEB_DIR = Path(__file__).parent / "web"


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    logging.basicConfig(level=settings.log_level)

    fortidlp = FortiDLPClient(
        base_url=settings.fortidlp_base_url,
        token=settings.fortidlp_token,
    )
    agent = ClaudeAgent(
        api_key=settings.anthropic_api_key,
        model=settings.claude_model,
    )

    app.state.fortidlp = fortidlp
    app.state.agent = agent

    try:
        yield
    finally:
        await fortidlp.aclose()


app = FastAPI(title="FortiDLP Agent", lifespan=lifespan)


class AskRequest(BaseModel):
    question: str


class AskResponse(BaseModel):
    answer: str
    trace: list[dict]


@app.get("/healthz")
async def healthz() -> dict:
    return {"status": "ok"}


@app.get("/api/canned")
async def api_canned() -> list[dict]:
    return list_canned()


@app.post("/api/ask", response_model=AskResponse)
async def api_ask(req: AskRequest) -> AskResponse:
    if not req.question.strip():
        raise HTTPException(status_code=400, detail="question must not be empty")
    result = await app.state.agent.ask(req.question, app.state.fortidlp)
    return AskResponse(**result)


@app.post("/api/canned/{canned_id}")
async def api_run_canned(canned_id: str) -> dict:
    try:
        result = await run_canned(canned_id, app.state.fortidlp)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"id": canned_id, "result": result}


# Serve the single-page UI.
if WEB_DIR.exists():
    app.mount(
        "/static",
        StaticFiles(directory=str(WEB_DIR)),
        name="static",
    )

    @app.get("/")
    async def index() -> FileResponse:
        return FileResponse(WEB_DIR / "index.html")
