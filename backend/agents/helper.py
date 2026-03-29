import asyncio
import json
import os
import re
import yaml
from typing import TypedDict, AsyncGenerator
from dotenv import load_dotenv

from langchain_groq import ChatGroq


load_dotenv()

# ── LLM Setup ────────────────────────────────────────────────
# Groq free tier models:
#   llama-3.3-70b-versatile
#   llama-3.1-8b-instant   
#   qwen/qwen3-32b
#   openai/gpt-oss-20b
#   openai/gpt-oss-120b

# def load_params():
#     with open("params.yaml", "r", encoding="utf-8") as f:
#         return yaml.safe_load(f)

# PARAMS = load_params()

# def get_llm(temperature=None, model_key="default"):
#     model_id = PARAMS["models"].get(model_key, PARAMS["models"]["writer"])
#     temp = temperature or PARAMS["models"]["temperatures"]["default"]
    
#     return ChatGroq(
#         model=model_id,
#         temperature=temp,
#         groq_api_key=os.getenv("GROQ_API_KEY"),
#         streaming=True,
#     )


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

def get_planner_llm():
    return get_llm(temperature=0.1, model="openai/gpt-oss-20b")

def get_analyst_llm():
    return get_llm(temperature=0.1, model="qwen/qwen3-32b")

def get_verifier_llm():
    return get_llm(temperature=0.1, model="openai/gpt-oss-120b")

def get_writer_llm():
    return get_llm(temperature=0.3, model="openai/gpt-oss-120b")

# ── Agent State ───────────────────────────────────────────────

class ResearchState(TypedDict):
    query: str
    sub_questions: list[str]
    raw_sources: list[dict]
    pdf_sources: list[dict]
    analysis: dict
    final_report: str
    citations: list[dict]
    event_queue: asyncio.Queue
    loop_step: int


# ── Helper ────────────────────────────────────────────────────

async def emit(queue: asyncio.Queue, event: dict):
    """Push a single SSE event into the queue."""
    await queue.put(json.dumps(event, ensure_ascii=False))
    await asyncio.sleep(0.01)


async def _stream_from_queue(queue: asyncio.Queue) -> AsyncGenerator[str, None]:
    while True:
        event = await queue.get()
        if event is None:
            break
        yield f"data: {event}\n\n"

def extract_json(text: str):
    """Extracting JSON from a text string may contain markdown"""
    try:
        match = re.search(r"(\[.*\]|\{.*\})", text, re.DOTALL)
        if match:
            return json.loads(match.group(1))
        return json.loads(text)
    except:
        return None