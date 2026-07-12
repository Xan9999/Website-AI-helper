"""FastAPI backend: streaming /chat endpoint plus the demo widget."""
from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse

from website_ai_helper import config, structured, vectorstore
from website_ai_helper.agent import run_chat

app = FastAPI(title="Website-AI-helper")

# Allow the widget to POST from your site's domain. Lock this to your origins
# in production (set ALLOWED_ORIGINS or edit here).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

WIDGET = Path(__file__).resolve().parent / "web" / "widget.html"


@app.on_event("startup")
def _startup() -> None:
    config.ensure_data_dir()
    structured.init_demo_db()
    vectorstore.ensure_collection(vectorstore.get_client())


@app.get("/")
def index() -> FileResponse:
    return FileResponse(WIDGET)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "collection": config.QDRANT_COLLECTION}


@app.post("/chat")
async def chat(request: Request) -> StreamingResponse:
    body = await request.json()
    message = (body.get("message") or "").strip()
    history = body.get("history") or []
    current_page = body.get("current_page")

    def event_stream():
        try:
            for event in run_chat(message, history, current_page):
                yield f"data: {json.dumps(event)}\n\n"
        except Exception as exc:
            yield f"data: {json.dumps({'type': 'error', 'message': str(exc)})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
