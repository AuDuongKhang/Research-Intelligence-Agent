"""
main.py — FastAPI Application
==============================
Expose endpoint POST /api/research/stream
Client gửi query → server stream SSE events từ LangGraph graph
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
import uvicorn

from graph import run_research

# ── App Setup ────────────────────────────────────────────────

app = FastAPI(
    title="Research Intelligence API",
    description="Multi-agent research system với real-time transparency",
    version="1.0.0",
)

# CORS — cho phép Next.js frontend gọi API
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",   # Next.js dev
        "http://localhost:3001",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Request/Response Models ──────────────────────────────────

class ResearchRequest(BaseModel):
    query: str = Field(
        ...,
        min_length=10,
        max_length=500,
        description="Câu hỏi nghiên cứu",
        examples=["Tác động của AI đến thị trường lao động năm 2025"]
    )


# ── Endpoints ────────────────────────────────────────────────

@app.get("/")
async def root():
    return {"status": "ok", "message": "Research Intelligence API is running"}


@app.get("/health")
async def health():
    return {"status": "healthy"}


@app.post("/api/research/stream")
async def research_stream(request: ResearchRequest):
    """
    Main endpoint — nhận query và stream SSE events.

    SSE Event format:
        data: {"type": "thinking", "agent": "planner", "content": "..."}
        data: {"type": "tool_call", "tool": "tavily_search", ...}
        data: {"type": "result", "content": "...", "is_final": false}
        data: {"type": "artifact", "kind": "citation_list", ...}
        data: {"type": "error", "message": "..."}
    """
    if not request.query.strip():
        raise HTTPException(status_code=400, detail="Query không được để trống")

    return StreamingResponse(
        run_research(request.query),
        media_type="text/event-stream",
        headers={
            # Ngăn proxy/nginx buffer SSE — quan trọng!
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        }
    )


# ── Dev Server ───────────────────────────────────────────────

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,       # auto-reload khi code thay đổi
        log_level="info",
    )