"""
main.py — FastAPI Application
==============================
Endpoints:
  POST /api/research/stream          — text-only query, returns SSE stream
  POST /api/research/stream-with-pdf — query + PDF file, returns SSE stream
  GET  /health                       — health check
"""

import base64
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
import uvicorn

from graph import run_research, run_research_with_sources
from tools.pdf_reader import read_base64

# ── App setup ─────────────────────────────────────────────────

app = FastAPI(
    title="Research Intelligence API",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Reusable SSE headers
SSE_HEADERS = {
    "Cache-Control":     "no-cache, no-transform",
    "X-Accel-Buffering": "no",
    "Connection":        "keep-alive",
}


# ── Models ────────────────────────────────────────────────────

class ResearchRequest(BaseModel):
    query: str = Field(..., min_length=10, max_length=500)


# ── Endpoints ─────────────────────────────────────────────────

@app.get("/")
async def root():
    return {"status": "ok", "message": "Research Intelligence API"}


@app.get("/health")
async def health():
    return {"status": "healthy"}


@app.post("/api/research/stream")
async def research_stream(request: ResearchRequest):
    """
    Standard text-only research endpoint.
    Streams SSE events from the 4-node LangGraph pipeline.
    """
    return StreamingResponse(
        run_research(request.query),
        media_type="text/event-stream",
        headers=SSE_HEADERS,
    )


@app.post("/api/research/stream-with-pdf")
async def research_stream_with_pdf(
    query: str = Form(..., min_length=10, max_length=500),
    file: UploadFile = File(...),
):
    """
    Research endpoint that accepts a PDF alongside the query.
    The PDF content is injected as pre-loaded sources — the Researcher
    node skips web search and feeds PDF chunks directly to the Analyst.
    """
    # Validate file type
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=422, detail="Only PDF files are accepted.")

    # Read and validate file size (max 10 MB)
    raw_bytes = await file.read()
    if len(raw_bytes) > 10 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="PDF must be under 10 MB.")

    # Extract text from PDF
    try:
        b64 = base64.b64encode(raw_bytes).decode()
        pdf_sources = read_base64(b64, filename=file.filename)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    if not pdf_sources:
        raise HTTPException(
            status_code=422,
            detail="Could not extract text from this PDF. It may be scanned or image-based."
        )

    return StreamingResponse(
        run_research_with_sources(query, pdf_sources),
        media_type="text/event-stream",
        headers=SSE_HEADERS,
    )


# ── Dev server ────────────────────────────────────────────────

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)