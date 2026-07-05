#!/usr/bin/env python3
"""FastAPI backend for Lenni deal matching and borrower chat."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from chat_engine import chat_turn, opening_message  # noqa: E402
from llm_client import llm_provider, ollama_model  # noqa: E402
from match_deal import match_deal  # noqa: E402

STATIC = ROOT / "static"

app = FastAPI(
    title="Lenni Borrower API",
    description="Deal matching + conversational loan advisory for Texas borrowers.",
    version="2.0.0",
)

_origins = os.environ.get(
    "LENNI_CORS_ORIGINS",
    "http://localhost:8080,http://127.0.0.1:8080,http://localhost:8000,http://127.0.0.1:8000,http://lenni-borrower.s3-website.us-east-2.amazonaws.com,null",
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _origins if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if STATIC.is_dir():
    app.mount("/static", StaticFiles(directory=str(STATIC)), name="static")


class MatchRequest(BaseModel):
    text: str = Field(..., min_length=3, description="Listing URL or plain-English deal description")
    metro: Optional[str] = Field(None, description="Optional Texas metro override")
    use_llm: bool = Field(True, description="Use OpenAI when OPENAI_API_KEY is set")


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, description="Borrower message")
    session_id: Optional[str] = Field(None, description="Session ID from prior turn")
    reset: bool = Field(False, description="Reset session and start over")


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "service": "lenni-borrower-api",
        "llm_provider": llm_provider(),
        "ollama_model": ollama_model() if llm_provider() == "ollama" else None,
    }


@app.get("/")
def chat_page():
    chat_html = STATIC / "chat.html"
    if chat_html.is_file():
        return FileResponse(chat_html)
    return {"message": "Lenni API running. POST /api/chat or GET /static/chat.html"}


@app.post("/api/match")
def api_match(req: MatchRequest) -> dict:
    try:
        return match_deal(req.text, metro=req.metro, use_llm=req.use_llm)
    except Exception as exc:
        raise HTTPException(500, f"Match failed: {exc}") from exc


@app.get("/api/match")
def api_match_get(text: str, metro: Optional[str] = None, use_llm: bool = True) -> dict:
    if len(text.strip()) < 3:
        raise HTTPException(400, "text parameter required (min 3 chars)")
    return match_deal(text, metro=metro, use_llm=use_llm)


@app.get("/api/chat/opening")
def api_chat_opening() -> dict:
    return {"reply": opening_message(), "provider": llm_provider()}


@app.post("/api/chat")
def api_chat(req: ChatRequest) -> dict:
    try:
        return chat_turn(req.message, session_id=req.session_id, reset=req.reset)
    except Exception as exc:
        raise HTTPException(500, f"Chat failed: {exc}") from exc
