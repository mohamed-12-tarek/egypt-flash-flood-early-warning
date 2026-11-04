"""FastAPI service for the chatbot agent and LLM-written alerts.

Run (from the project root):
    uvicorn genai.chatbot_api:app --host 0.0.0.0 --port 8001

Endpoints (contract: docs/data_contract.md section 7)
    POST /chatbot/ask               {"question": "...", "history": [...optional]} -> {"answer": "...", ...}
    GET  /chatbot/alert/{city}?lang=ar|en                                          -> alert (LLM text, validated)
    GET  /chatbot/health
"""

import logging
import os
from functools import lru_cache

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from genai.alerts import generate_alert
from genai.chatbot_chain import FloodAgent
from genai.settings import MAX_QUESTION_CHARS, CITIES
from genai.tools import resolve_city

logger = logging.getLogger("chatbot_api")

app = FastAPI(title="Flood Early Warning - Chatbot Agent", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:5173,http://localhost:3000").split(",")],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


class Turn(BaseModel):
    role: str = Field(pattern="^(user|assistant)$")
    content: str = Field(max_length=MAX_QUESTION_CHARS)


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=MAX_QUESTION_CHARS)
    history: list[Turn] = Field(default_factory=list, max_length=12)


@lru_cache(maxsize=1)
def get_agent() -> FloodAgent:
    return FloodAgent()


@app.get("/chatbot/health")
def health():
    return {"status": "ok"}


@app.post("/chatbot/ask")
def ask(req: AskRequest):
    try:
        result = get_agent().ask(req.question, [t.model_dump() for t in req.history])
    except RuntimeError as exc:           # e.g. GROQ_API_KEY missing
        logger.error("Agent unavailable: %s", exc)
        raise HTTPException(status_code=503, detail="The assistant is not configured.") from exc
    return result.to_dict()


@app.get("/chatbot/alert/{city}")
def alert(city: str, lang: str = Query("ar", pattern="^(ar|en)$")):
    if not resolve_city(city):
        raise HTTPException(status_code=404, detail={"error": "unknown region", "valid_regions": CITIES})
    return generate_alert(city, lang)
