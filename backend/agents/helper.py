import asyncio
import json
import os
from typing import TypedDict
from dotenv import load_dotenv

from langchain_groq import ChatGroq
from langchain_tavily import TavilySearch 


load_dotenv()

# ── LLM Setup ────────────────────────────────────────────────
# Groq free tier models:
#   llama-3.3-70b-versatile  → best quality for final report
#   llama-3.1-8b-instant     → fastest, great for structured JSON tasks

def get_llm(temperature: float = 0.3, model: str | None = None):
    return ChatGroq(
        model=model or os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
        temperature=temperature,
        groq_api_key=os.getenv("GROQ_API_KEY"),
        streaming=True,
    )

def get_fast_llm():
    """Cheaper/faster model for structured JSON extraction tasks."""
    return get_llm(temperature=0.1, model="llama-3.1-8b-instant")

# ── Agent State ───────────────────────────────────────────────

class ResearchState(TypedDict):
    query: str
    sub_questions: list[str]
    raw_sources: list[dict]
    analysis: dict
    final_report: str
    citations: list[dict]
    event_queue: asyncio.Queue


# ── Helper ────────────────────────────────────────────────────

async def emit(queue: asyncio.Queue, event: dict):
    """Push a single SSE event into the queue."""
    await queue.put(json.dumps(event, ensure_ascii=False))