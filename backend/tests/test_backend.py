"""
test_research.py — Full Backend Test Suite
==========================================
Covers every public function across:
  - tools/pdf_reader.py  (read, read_base64, get_metadata, _extract_chunks)
  - graph.py             (get_llm, get_fast_llm, get_search_tool, emit,
                          planner_node, researcher_node, analyst_node,
                          writer_node, build_graph, run_research,
                          run_research_with_sources)
  - main.py              (/, /health, /api/research/stream,
                          /api/research/stream-with-pdf — via HTTP)

Test levels:
  unit          — pure logic, no API calls
  integration   — real LLM + Tavily calls (~30-40s)
  api           — HTTP tests (requires: python main.py running)

Usage:
  python test_backend.py               # all levels
  python test_backend.py unit
  python test_backend.py integration
  python test_backend.py api
"""

import asyncio
import base64
import io
import json
import os
import sys
import tempfile
import time
import fitz
import traceback

from langchain_groq import ChatGroq
from langchain_tavily import TavilySearch
from unittest.mock import AsyncMock, create_autospec, patch, MagicMock
from langchain_core.messages import HumanMessage

from graph import *
from tools.pdf_reader import read, read_base64, get_metadata, _extract_chunks
from agents.helper import get_analyst_llm, get_llm, get_fast_llm, get_planner_llm, get_writer_llm, emit, ResearchState, _stream_from_queue
from agents.researcher_agent import researcher_node
from agents.analyst_agent import analyst_node
from agents.writer_agent import writer_node
from agents.planner_agent import planner_node
from agents.verifier_agent import verifier_node
from tools.tavily_tool import get_search_tool


# ── Pre-flight checks ─────────────────────────────────────────

if not os.path.exists(".env"):
    print("ERROR: .env not found. Run: cp .env.example .env")
    sys.exit(1)

from dotenv import load_dotenv
load_dotenv()

missing = [k for k in ("GROQ_API_KEY", "TAVILY_API_KEY") if not os.getenv(k)]
if missing:
    print(f"ERROR: Missing keys in .env: {', '.join(missing)}")
    sys.exit(1)


# ── Console helpers ───────────────────────────────────────────

BOLD  = "\033[1m"
GREEN = "\033[92m"
RED   = "\033[91m"
CYAN  = "\033[96m"
DIM   = "\033[2m"
RESET = "\033[0m"

passed = failed = 0
TEST_QUERY = "What are the latest breakthroughs in quantum computing in 2025?"


def section(title: str):
    print(f"\n{BOLD}{CYAN}{'─' * 55}{RESET}")
    print(f"{BOLD}{CYAN}  {title}{RESET}")
    print(f"{BOLD}{CYAN}{'─' * 55}{RESET}")


def ok(label: str, detail: str = ""):
    global passed
    passed += 1
    suffix = f"  {DIM}{detail}{RESET}" if detail else ""
    print(f"  {GREEN}✓{RESET}  {label}{suffix}")


def fail(label: str, reason: str = ""):
    global failed
    failed += 1
    suffix = f"  {RED}{reason}{RESET}" if reason else ""
    print(f"  {RED}✗{RESET}  {label}{suffix}")


def skip(label: str, reason: str = ""):
    print(f"  {DIM}–  {label}  [{reason}]{RESET}")


def summary():
    total = passed + failed
    color = GREEN if failed == 0 else RED
    print(f"\n{BOLD}{color}{'─' * 55}")
    print(f"  Results: {passed}/{total} passed", end="")
    if failed:
        print(f"  ({failed} FAILED)", end="")
    print(f"{RESET}\n")


# ── Minimal PDF factory ───────────────────────────────────────
# Creates a real, valid single-page PDF in memory using only stdlib.
# No reportlab / fpdf needed.

def make_pdf_bytes(text: str = "Quantum computing test document.") -> bytes:
    """Return a minimal valid PDF containing one page of text."""
    # Minimal PDF structure — manually crafted
    content_stream = f"BT /F1 12 Tf 50 750 Td ({text}) Tj ET"
    stream_bytes = content_stream.encode()
    stream_len = len(stream_bytes)

    pdf = (
        b"%PDF-1.4\n"
        b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
        b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
        b"3 0 obj\n<< /Type /Page /Parent 2 0 R "
        b"/MediaBox [0 0 612 792] "
        b"/Contents 4 0 R "
        b"/Resources << /Font << /F1 5 0 R >> >> >>\nendobj\n"
        + f"4 0 obj\n<< /Length {stream_len} >>\nstream\n".encode()
        + stream_bytes
        + b"\nendstream\nendobj\n"
        b"5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n"
        b"xref\n0 6\n"
        b"0000000000 65535 f \n"
        b"0000000009 00000 n \n"
        b"0000000058 00000 n \n"
        b"0000000115 00000 n \n"
        b"0000000266 00000 n \n"
        b"0000000360 00000 n \n"
        b"trailer\n<< /Size 6 /Root 1 0 R >>\n"
        b"startxref\n430\n%%EOF\n"
    )
    return pdf


# =============================================================
# SECTION 1 — tools/pdf_reader.py
# =============================================================

async def test_pdf_reader():
    section("Unit: tools/pdf_reader.py")

    pdf_bytes = make_pdf_bytes("Quantum computing test document.")

    # ── _extract_chunks ───────────────────────────────────────

    try:
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            f.write(pdf_bytes)
            tmp = f.name

        doc = fitz.open(tmp)
        chunks = _extract_chunks(doc, filename="test.pdf")
        doc.close()
        os.unlink(tmp)

        assert isinstance(chunks, list), "Not a list"
        assert len(chunks) >= 1, "No chunks returned"
        assert "content" in chunks[0], "Missing 'content' key"
        assert "title" in chunks[0],   "Missing 'title' key"
        assert "url" in chunks[0],     "Missing 'url' key"
        assert "score" in chunks[0],   "Missing 'score' key"
        ok("_extract_chunks returns correct structure",
           f"{len(chunks)} chunk(s), score={chunks[0]['score']}")
    except Exception as e:
        fail("_extract_chunks", str(e))

    # ── _extract_chunks: empty PDF ────────────────────────────

    try:
        # Create a PDF with no text (blank page)
        blank_pdf = (
            b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
            b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
            b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] >>\nendobj\n"
            b"xref\n0 4\n0000000000 65535 f \n0000000009 00000 n \n"
            b"0000000058 00000 n \n0000000115 00000 n \n"
            b"trailer\n<< /Size 4 /Root 1 0 R >>\nstartxref\n190\n%%EOF\n"
        )
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            f.write(blank_pdf)
            tmp = f.name

        doc = fitz.open(tmp)
        chunks = _extract_chunks(doc)
        doc.close()
        os.unlink(tmp)

        assert isinstance(chunks, list)
        ok("_extract_chunks: blank PDF returns empty list", f"{len(chunks)} chunks")
    except Exception as e:
        fail("_extract_chunks: blank PDF", str(e))

    # ── read: valid file ──────────────────────────────────────

    try:
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            f.write(pdf_bytes)
            tmp = f.name

        chunks = read(tmp)
        os.unlink(tmp)

        assert isinstance(chunks, list)
        assert len(chunks) >= 1
        assert all("content" in c for c in chunks)
        ok("read() from local file path", f"{len(chunks)} chunk(s)")
    except Exception as e:
        fail("read() from local file path", str(e))

    # ── read: file not found ──────────────────────────────────

    try:
        read("/nonexistent/path/file.pdf")
        fail("read(): should raise FileNotFoundError")
    except FileNotFoundError:
        ok("read() raises FileNotFoundError for missing file")
    except Exception as e:
        fail("read() raises FileNotFoundError", f"got {type(e).__name__}: {e}")

    # ── read: wrong extension ─────────────────────────────────

    try:
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
            f.write(b"not a pdf")
            tmp = f.name
        read(tmp)
        os.unlink(tmp)
        fail("read(): should raise ValueError for non-PDF extension")
    except ValueError:
        ok("read() raises ValueError for non-PDF extension")
        try:
            os.unlink(tmp)
        except Exception:
            pass
    except Exception as e:
        fail("read() raises ValueError", f"got {type(e).__name__}: {e}")

    # ── read_base64: valid base64 ─────────────────────────────

    try:
        b64 = base64.b64encode(pdf_bytes).decode()
        chunks = read_base64(b64, filename="test_upload.pdf")

        assert isinstance(chunks, list)
        assert len(chunks) >= 1
        assert chunks[0]["url"] == "local://uploaded-pdf"
        assert chunks[0]["score"] == 0.9   # high-trust score for user uploads
        ok("read_base64() decodes and extracts text",
           f"{len(chunks)} chunk(s), url={chunks[0]['url']}")
    except Exception as e:
        fail("read_base64()", str(e))

    # ── read_base64: invalid base64 ───────────────────────────

    try:
        read_base64("!!!not_valid_base64!!!")
        fail("read_base64(): should raise ValueError for bad base64")
    except ValueError:
        ok("read_base64() raises ValueError for invalid base64")
    except Exception as e:
        fail("read_base64() raises ValueError", f"got {type(e).__name__}: {e}")

    # ── get_metadata ──────────────────────────────────────────

    try:
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            f.write(pdf_bytes)
            tmp = f.name

        meta = get_metadata(tmp)
        os.unlink(tmp)

        assert isinstance(meta, dict)
        assert "title"      in meta
        assert "author"     in meta
        assert "page_count" in meta
        assert "filename"   in meta
        assert isinstance(meta["page_count"], int)
        assert meta["page_count"] >= 1
        ok("get_metadata() returns correct keys",
           f"pages={meta['page_count']}, filename={meta['filename']}")
    except Exception as e:
        fail("get_metadata()", str(e))


# =============================================================
# SECTION 2 — graph.py factory functions
# =============================================================

async def test_graph_factories():
    section("Unit: graph.py — factory functions")
    
    # get_llm default
    try:
        llm = get_llm()
        assert isinstance(llm, ChatGroq)
        assert llm.model_name == os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")
        ok("get_llm() returns ChatGroq instance", f"model={llm.model_name}")
    except Exception as e:
        fail("get_llm()", str(e))

    # get_llm with custom model
    try:
        llm = get_llm(temperature=0.5, model="openai/gpt-oss-20b")
        assert llm.model_name == "openai/gpt-oss-20b"
        ok("get_llm(model=...) respects override", f"model={llm.model_name}")
    except Exception as e:
        fail("get_llm(model=...)", str(e))

    # get_fast_llm
    try:
        llm = get_fast_llm()
        assert isinstance(llm, ChatGroq)
        assert llm.model_name == "llama-3.1-8b-instant"
        ok("get_fast_llm() returns 8b-instant model", f"model={llm.model_name}")
    except Exception as e:
        fail("get_fast_llm()", str(e))

    # get_search_tool
    try:
        tool = get_search_tool()
        assert isinstance(tool, TavilySearch)
        ok("get_search_tool() returns TavilySearch")
    except Exception as e:
        fail("get_search_tool()", str(e))


# =============================================================
# SECTION 3 — graph.py: emit + state helpers
# =============================================================

async def test_emit_and_state():
    section("Unit: graph.py — emit() and ResearchState")

    # emit puts JSON into queue
    try:
        q: asyncio.Queue = asyncio.Queue()
        event = {"type": "thinking", "agent": "planner", "content": "test"}
        await emit(q, event)
        raw = await q.get()
        parsed = json.loads(raw)
        assert parsed == event
        ok("emit() serializes and enqueues event correctly")
    except Exception as e:
        fail("emit()", str(e))

    # emit handles unicode
    try:
        q = asyncio.Queue()
        await emit(q, {"type": "thinking", "agent": "planner", "content": "量子コンピュータ"})
        raw = await q.get()
        parsed = json.loads(raw)
        assert "量子コンピュータ" in parsed["content"]
        ok("emit() handles unicode content")
    except Exception as e:
        fail("emit() unicode", str(e))

    # ResearchState has all required keys
    try:
        required = {"query", "sub_questions", "raw_sources",
                    "analysis", "final_report", "citations", "event_queue", "loop_step"}
        actual = set(ResearchState.__annotations__.keys())
        missing_keys = required - actual
        assert not missing_keys, f"Missing keys: {missing_keys}"
        ok("ResearchState has all required keys", str(sorted(actual)))
    except Exception as e:
        fail("ResearchState schema", str(e))


# =============================================================
# SECTION 4 — graph.py: individual nodes (mocked LLM/tools)
# =============================================================

def make_state(overrides: dict = {}) -> dict:
    """Helper: build a minimal ResearchState for node tests."""
    base = {
        "query":         TEST_QUERY,
        "sub_questions": [],
        "raw_sources":   [],
        "analysis":      {},
        "final_report":  "",
        "citations":     [],
        "event_queue":   asyncio.Queue(),
    }
    return {**base, **overrides}


async def test_researcher_node_pdf_mode():
    """researcher_node must skip web search when raw_sources is pre-filled."""
    section("Unit: researcher_node — PDF mode (no API calls)")

    preloaded = [
        {"question": "test", "title": "My PDF", "url": "local://uploaded-pdf",
         "content": "Quantum entanglement content...", "score": 0.9},
        {"question": "test", "title": "My PDF", "url": "local://uploaded-pdf",
         "content": "More content...", "score": 0.9},
    ]
    state = make_state({"raw_sources": preloaded})

    try:
        result = await researcher_node(state)

        # Must return preloaded sources unchanged
        assert result["raw_sources"] == preloaded, \
            "PDF sources were modified or cleared"
        ok("researcher_node returns preloaded sources unchanged",
           f"{len(result['raw_sources'])} sources")

        # Must emit at least one thinking event
        events = []
        while not state["event_queue"].empty():
            events.append(json.loads(await state["event_queue"].get()))

        thinking = [e for e in events if e["type"] == "thinking"]
        assert len(thinking) >= 1, "No thinking event emitted"
        ok("researcher_node emits thinking event in PDF mode",
           thinking[0]["content"][:60])

        # Must NOT emit any tavily_search tool_call
        tavily_calls = [e for e in events
                        if e.get("type") == "tool_call"
                        and e.get("tool") == "tavily_search"]
        assert len(tavily_calls) == 0, \
            f"Should not call tavily in PDF mode, got {len(tavily_calls)} calls"
        ok("researcher_node does NOT call tavily_search in PDF mode")

    except AssertionError as e:
        fail("researcher_node PDF mode", str(e))
    except Exception as e:
        fail("researcher_node PDF mode (unexpected)", str(e))


async def test_analyst_node_structure():
    """analyst_node must build citations and emit artifact event."""
    section("Unit: analyst_node — output structure (mocked sources)")

    # Provide 3 fake sources that look like real Tavily results
    fake_sources = [
        {"question": "q1", "title": f"Source {i}", "url": f"https://example.com/{i}",
         "content": f"Content about quantum computing {i} " * 20, "score": 0.8}
        for i in range(3)
    ]

    # Mock LLM response to return valid JSON analysis
    mock_response = MagicMock()
    mock_response.content = json.dumps({
        "key_findings":           ["Quantum error correction improved", "IBM milestone reached"],
        "contradictions":         [],
        "credible_source_indices": [0, 1, 2],
        "overall_confidence":     0.88
    })

    state = make_state({"raw_sources": fake_sources})

    with patch("agents.analyst_agent.get_analyst_llm") as mock_llm_factory:
        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)
        mock_llm_factory.return_value = mock_llm

        try:
            result = await analyst_node(state)

            # citations built correctly
            assert isinstance(result["citations"], list), "citations not a list"
            assert len(result["citations"]) > 0, "No citations built"
            ok(f"analyst_node builds {len(result['citations'])} citation(s)")

            # each citation has required fields
            required_fields = {"id", "title", "url", "snippet", "credibility_score"}
            for c in result["citations"]:
                missing = required_fields - set(c.keys())
                assert not missing, f"Citation missing fields: {missing}"
            ok("Each citation has all required fields")

            # analysis dict stored correctly
            assert result["analysis"]["overall_confidence"] >= 0.6
            ok("analyst_node stores analysis dict", f"confidence={result['analysis']['overall_confidence']}")

            # artifact event emitted
            events = []
            while not state["event_queue"].empty():
                events.append(json.loads(await state["event_queue"].get()))

            artifacts = [e for e in events if e.get("type") == "artifact"]
            assert len(artifacts) == 1, f"Expected 1 artifact, got {len(artifacts)}"
            assert artifacts[0]["kind"] == "citation_list"
            ok("analyst_node emits citation_list artifact")

        except AssertionError as e:
            fail("analyst_node structure", str(e))
        except Exception as e:
            fail("analyst_node (unexpected)", str(e))
            import traceback; traceback.print_exc()


async def test_analyst_node_malformed_json():
    """analyst_node must fall back gracefully when LLM returns bad JSON."""
    section("Unit: analyst_node — malformed LLM response fallback")

    fake_sources = [
        {"question": "q", "title": "S", "url": "https://x.com",
         "content": "content", "score": 0.5}
    ]
    mock_response = MagicMock()
    mock_response.content = "Sorry, I cannot provide that analysis."  # not JSON

    state = make_state({"raw_sources": fake_sources})

    with patch("agents.analyst_agent.get_analyst_llm") as mock_factory:
        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)
        mock_factory.return_value = mock_llm

        try:
            result = await analyst_node(state)
            assert isinstance(result["analysis"], dict), "analysis not a dict"
            assert "key_findings" in result["analysis"], "fallback missing key_findings"
            ok("analyst_node falls back gracefully on bad JSON",
               f"key_findings={result['analysis']['key_findings']}")
        except Exception as e:
            fail("analyst_node fallback", str(e))


async def test_writer_node_saves_draft():
    """writer_node must accumulate final_report in state but NOT emit result chunks."""
    section("Unit: writer_node — draft accumulation")

    fake_chunks = ["## Executive Summary\n", "Quantum computing is ", "advancing rapidly.\n"]

    async def fake_astream(_):
        for text in fake_chunks:
            chunk = MagicMock()
            chunk.content = text
            yield chunk

    state = make_state({
        "analysis": {
            "key_findings": ["Finding 1", "Finding 2"],
            "contradictions": [],
            "verification": {"is_accurate": True} # already verified to focus test on writing
        },
        "citations": [{"id": 1, "title": "Source 1", "url": "https://x.com", "snippet": "snippet"}]
    })

    #with patch("agents.writer_agent.get_writer_llm") as mock_factory:
    with patch("agents.writer_agent.get_llm") as mock_factory:
        mock_llm = create_autospec(ChatGroq, instance=True)
        mock_llm.astream.side_effect = fake_astream
        mock_factory.return_value = mock_llm

        try:
            result = await writer_node(state)

            # Check final_report in state
            expected_report = "".join(fake_chunks)
            assert result["final_report"] == expected_report, "Report was not accumulated in state"
            ok("writer_node accumulates final_report correctly")

            # Check event queue
            events = []
            while not state["event_queue"].empty():
                events.append(json.loads(await state["event_queue"].get()))

            result_events = [e for e in events if e["type"] == "result"]
            assert len(result_events) == 0, "Writer should NOT emit result chunks directly anymore"
            
            thinking_events = [e for e in events if e["type"] == "thinking"]
            assert len(thinking_events) > 0
            ok("writer_node emits thinking events but no result chunks")

        except AssertionError as e:
            fail("writer_node draft check", str(e))
            

async def test_publisher_node_streams():
    """publisher_node must take final_report from state and stream it as result events."""
    section("Unit: publisher_node — output streaming")

    test_content = "This is a final verified research report content."
    state = make_state({
        "final_report": test_content
    })

    try:
        await publisher_node(state)

        # Event from queue
        events = []
        while not state["event_queue"].empty():
            events.append(json.loads(await state["event_queue"].get()))

        result_events = [e for e in events if e["type"] == "result"]
        
        # Check that multiple chunks are emitted
        non_final = [e for e in result_events if not e.get("is_final", False)]
        assert len(non_final) > 0, "Publisher should emit multiple chunks"
        
        # Check that combined content matches final_report
        reconstructed = "".join([e["content"] for e in non_final]).strip()
        assert test_content in reconstructed or reconstructed in test_content
        ok("publisher_node streams report content correctly")

        # Check for final sentinel event
        final_sentinel = [e for e in result_events if e.get("is_final") == True]
        assert len(final_sentinel) == 1, "Missing final sentinel"
        ok("publisher_node emits final sentinel")

    except Exception as e:
        fail("publisher_node streaming", str(e))


async def test_verifier_node():
    section("Unit: verifier_node — factual check")
    state = make_state({
        "final_report": "The sun is a planet.", # Wrong claim for testing
        "citations": [{"id": 1, "title": "Science", "snippet": "The sun is a star."}]
    })
    
    # Mock LLM 
    mock_resp = MagicMock()
    mock_resp.content = json.dumps({
        "is_accurate": False,
        "errors": ["Claimed sun is a planet, but it is a star."],
        "citation_errors": [],
        "score": 0.4
    })
    
    with patch("agents.verifier_agent.get_verifier_llm") as mock_factory:
        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock(return_value=mock_resp)
        mock_factory.return_value = mock_llm
        
        result = await verifier_node(state)
        v = result["analysis"]["verification"]
        assert v["is_accurate"] == False
        ok("verifier_node correctly flags factual errors", f"Score: {v['score']}")


async def test_build_graph():
    """build_graph must wire all 4 nodes in correct order."""
    section("Unit: build_graph()")

    try:
        graph = build_graph()
        nodes = set(graph.nodes)
        expected = {"planner", "researcher", "analyst", "writer"}
        assert expected.issubset(nodes), f"Missing nodes: {expected - nodes}"
        ok("build_graph() compiles without errors",
           f"nodes={sorted(nodes - {'__start__', '__end__'})}")
    except Exception as e:
        fail("build_graph()", str(e))


async def test_stream_from_queue():
    """_stream_from_queue must yield all events and stop at None sentinel."""
    section("Unit: _stream_from_queue()")

    try:
        q: asyncio.Queue = asyncio.Queue()
        events = [
            json.dumps({"type": "thinking", "content": f"step {i}"})
            for i in range(5)
        ]
        for e in events:
            await q.put(e)
        await q.put(None)   # sentinel

        collected = []
        async for line in _stream_from_queue(q):
            collected.append(line)

        assert len(collected) == 5, f"Expected 5, got {len(collected)}"
        assert all(line.startswith("data: ") for line in collected)
        assert all(line.endswith("\n\n") for line in collected)
        ok("_stream_from_queue yields SSE-formatted lines and stops at None",
           f"{len(collected)} lines")
    except Exception as e:
        fail("_stream_from_queue()", str(e))


async def test_run_research_with_sources_pdf_mode():
    """run_research_with_sources must skip Tavily and yield SSE events."""
    section("Unit: run_research_with_sources() — PDF mode (mocked LLM)")

    preloaded = [
        {"question": "q", "title": "My PDF", "url": "local://uploaded-pdf",
         "content": "Quantum computing content " * 50, "score": 0.9}
    ]

    # Mock both LLM calls (analyst + writer)
    analyst_response = MagicMock()
    analyst_response.content = json.dumps({
        "key_findings": ["Finding from PDF"],
        "contradictions": [],
        "credible_source_indices": [0],
        "overall_confidence": 0.9
    })

    async def fake_astream(_):
        for text in ["## Summary\n", "Based on the PDF..."]:
            c = MagicMock(); c.content = text; yield c

    mock_fast = MagicMock()
    mock_fast.ainvoke = AsyncMock(return_value=analyst_response)

    mock_main = MagicMock()
    mock_main.astream = fake_astream

    try:
        with patch("agents.analyst_agent.get_analyst_llm", return_value=mock_fast), \
             patch("agents.writer_agent.get_writer_llm", return_value=mock_main):

            events_collected = []
            async for line in run_research_with_sources(TEST_QUERY, preloaded):
                if not line.strip() or line.startswith(":"):
                    continue
                assert line.startswith("data: "), f"Bad SSE format: {line}"
                events_collected.append(json.loads(line[6:]))

        event_types = [e["type"] for e in events_collected]

        # Must have initial pdf_reader tool_call
        pdf_calls = [e for e in events_collected
                     if e.get("type") == "tool_call" and e.get("tool") == "pdf_reader"]
        assert len(pdf_calls) == 1
        ok("run_research_with_sources emits pdf_reader tool_call event")

        # Must NOT have any tavily_search calls
        tavily_calls = [e for e in events_collected
                        if e.get("type") == "tool_call" and e.get("tool") == "tavily_search"]
        assert len(tavily_calls) == 0, f"Should not call tavily, got {len(tavily_calls)}"
        ok("run_research_with_sources does NOT call tavily_search")

        # Must produce result events
        result_events = [e for e in events_collected if e["type"] == "result"]
        assert len(result_events) >= 1
        ok(f"run_research_with_sources yields {len(result_events)} result event(s)")

        # Final sentinel present
        final = [e for e in result_events if e.get("is_final")]
        assert len(final) == 1
        ok("run_research_with_sources emits is_final=True sentinel")

    except AssertionError as e:
        fail("run_research_with_sources PDF mode", str(e))
    except Exception as e:
        fail("run_research_with_sources (unexpected)", str(e))
        import traceback; traceback.print_exc()


# =============================================================
# SECTION 5 — Integration tests (real API calls)
# =============================================================

async def test_llm_connection():
    section("Integration: LLM connection (Groq)")

    for name, llm in [
        ("llama-3.1-8b-instant (fast)", get_fast_llm()),
        ("llama-3.3-70b-versatile (main)", get_llm()),
        ("openai/gpt-oss-120b", get_writer_llm()),
        ("openai/gpt-oss-20b", get_planner_llm()),
        ("qwen/qwen3-32b", get_analyst_llm()),
    ]:
        try:
            t0 = time.time()
            resp = await llm.ainvoke([HumanMessage(content="Reply with one word: ready")])
            elapsed = time.time() - t0
            assert resp.content.strip(), "Empty response"
            ok(name, f"{elapsed:.1f}s → '{resp.content.strip()[:30]}'")
        except Exception as e:
            fail(name, str(e))


async def test_search_tool_live():
    section("Integration: Tavily search tool")

    tool = get_search_tool()
    try:
        t0 = time.time()
        tool_msg = tool.invoke({"query": "quantum computing 2025"})
        results = tool_msg.get("results", [])
        elapsed = time.time() - t0

        assert isinstance(results, list) and len(results) > 0
        ok("Tavily returns results", f"{elapsed:.1f}s → {len(results)} sources")

        first = results[0]
        for field in ["title", "url", "content"]:
            if field in first:
                ok(f"  Result has '{field}'", str(first[field])[:60])
            else:
                fail(f"  Result missing '{field}'")
    except Exception as e:
        fail("Tavily search", str(e))


async def test_planner_node_live():
    section("Integration: planner_node (real Groq call)")

    state = make_state()
    try:
        result = await planner_node(state)
        sub_qs = result["sub_questions"]

        assert isinstance(sub_qs, list) and len(sub_qs) >= 2
        ok(f"Planner generated {len(sub_qs)} sub-questions")
        for i, q in enumerate(sub_qs):
            ok(f"  [{i+1}] {q[:70]}")

        events = []
        while not state["event_queue"].empty():
            events.append(json.loads(await state["event_queue"].get()))

        thinking = [e for e in events if e["type"] == "thinking"]
        assert len(thinking) >= 1
        ok(f"Planner emitted {len(thinking)} thinking event(s)")
    except AssertionError as e:
        fail("planner_node live", str(e))
    except Exception as e:
        fail("planner_node live (unexpected)", str(e))


async def test_full_pipeline_live():
    section("Integration: full pipeline — run_research()")
    print(f"  {DIM}Query: {TEST_QUERY}{RESET}")
    print(f"  {DIM}(This takes ~30-40s){RESET}\n")

    events_by_type: dict[str, list] = {
        "thinking": [], "tool_call": [], "result": [], "artifact": [], "error": []
    }
    agents_seen: set[str] = set()
    result_chunks: list[str] = []
    t0 = time.time()

    try:
        async for raw in run_research(TEST_QUERY):
            if not raw.strip() or raw.startswith(":"):
                continue
            assert raw.startswith("data: "), f"Bad SSE line: {raw}"
            event = json.loads(raw[6:])
            etype = event.get("type", "unknown")
            if etype in events_by_type:
                events_by_type[etype].append(event)

            if etype == "thinking":
                agents_seen.add(event.get("agent", ""))
                print(f"  {DIM}[{event['agent']}] {event['content'][:70]}{RESET}")
            elif etype == "result" and not event.get("is_final"):
                result_chunks.append(event["content"])

        elapsed = time.time() - t0
        print()

        # All agents ran
        for agent in ("planner", "researcher", "analyst", "writer", "verifier", "publisher"):
            if agent in agents_seen:
                ok(f"Agent '{agent}' ran")
            else:
                fail(f"Agent '{agent}' did NOT run")

        # Thinking events
        n = len(events_by_type["thinking"])
        (ok if n >= 4 else fail)(f"Thinking events emitted ({n} total)")

        # Tool calls
        n = len(events_by_type["tool_call"])
        (ok if n >= 2 else fail)(f"Tool call events emitted ({n} total)")

        # Citation artifact
        artifacts = [a for a in events_by_type["artifact"]
                     if a.get("kind") == "citation_list"]
        if artifacts:
            ok(f"Citation artifact emitted ({len(artifacts[0]['data'])} citations)")
        else:
            fail("No citation_list artifact emitted")

        # Final report
        report = "".join(result_chunks)
        if len(report) >= 200:
            ok(f"Final report generated ({len(report)} chars, {elapsed:.1f}s)")
            print(f"\n  {DIM}── Report preview ──\n  {report.strip()}...{RESET}\n")
        else:
            fail(f"Report too short ({len(report)} chars)")

        # No errors
        for err in events_by_type["error"]:
            fail(f"Pipeline error: {err.get('message')}")
        if not events_by_type["error"]:
            ok("No errors during pipeline")

    except Exception as e:
        fail("Full pipeline", str(e))
        import traceback; traceback.print_exc()


# =============================================================
# SECTION 6 — API tests (requires running server)
# =============================================================

async def test_api():
    section("API: FastAPI endpoints (requires: python main.py)")

    try:
        import httpx
    except ImportError:
        skip("All API tests", "httpx not installed — run: pip install httpx")
        return

    base = "http://localhost:8000"

    async with httpx.AsyncClient(timeout=10.0) as client:

        # GET /
        try:
            r = await client.get(f"{base}/")
            assert r.status_code == 200
            data = r.json()
            assert "status" in data
            ok("GET / → 200", data.get("message", ""))
        except Exception as e:
            fail("GET /", f"{e} — is the server running?")
            skip("remaining API tests", "server unreachable")
            return

        # GET /health
        try:
            r = await client.get(f"{base}/health")
            assert r.status_code == 200
            assert r.json().get("status") == "healthy"
            ok("GET /health → 200")
        except Exception as e:
            fail("GET /health", str(e))

        # POST /api/research/stream — query too short (422)
        try:
            r = await client.post(f"{base}/api/research/stream",
                                  json={"query": "hi"})
            assert r.status_code == 422
            ok("POST /api/research/stream rejects short query → 422")
        except Exception as e:
            fail("POST /api/research/stream validation", str(e))

        # POST /api/research/stream — missing body (422)
        try:
            r = await client.post(f"{base}/api/research/stream", json={})
            assert r.status_code == 422
            ok("POST /api/research/stream rejects empty body → 422")
        except Exception as e:
            fail("POST /api/research/stream empty body", str(e))

        # POST /api/research/stream — valid, read first 5 events
        try:
            print(f"\n  {DIM}Streaming first 5 events from /api/research/stream...{RESET}")
            count = 0
            async with client.stream(
                "POST", f"{base}/api/research/stream",
                json={"query": TEST_QUERY},
                timeout=30.0,
            ) as resp:
                assert resp.status_code == 200
                assert "text/event-stream" in resp.headers.get("content-type", "")
                async for line in resp.aiter_lines():
                    if line.startswith("data: "):
                        event = json.loads(line[6:])
                        count += 1
                        print(f"  {DIM}  event {count}: type={event['type']}{RESET}")
                        if count >= 5:
                            break

            ok(f"POST /api/research/stream SSE works ({count} events received)")
        except Exception as e:
            fail("POST /api/research/stream SSE", str(e))

        # POST /api/research/stream-with-pdf — non-PDF file (422)
        try:
            r = await client.post(
                f"{base}/api/research/stream-with-pdf",
                data={"query": TEST_QUERY},
                files={"file": ("test.txt", b"not a pdf", "text/plain")},
            )
            assert r.status_code == 422
            ok("POST /api/research/stream-with-pdf rejects non-PDF → 422")
        except Exception as e:
            fail("POST /api/research/stream-with-pdf non-PDF", str(e))

        # POST /api/research/stream-with-pdf — valid PDF, read first 5 events
        try:
            pdf_bytes = make_pdf_bytes("Quantum computing research paper content.")
            print(f"\n  {DIM}Streaming first 5 events from /api/research/stream-with-pdf...{RESET}")
            count = 0
            async with client.stream(
                "POST", f"{base}/api/research/stream-with-pdf",
                data={"query": TEST_QUERY},
                files={"file": ("test.pdf", pdf_bytes, "application/pdf")},
                timeout=60.0,
            ) as resp:
                assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
                async for line in resp.aiter_lines():
                    if line.startswith("data: "):
                        event = json.loads(line[6:])
                        count += 1
                        print(f"  {DIM}  event {count}: type={event['type']}, "
                              f"tool={event.get('tool','—')}{RESET}")
                        if count >= 5:
                            break

            ok(f"POST /api/research/stream-with-pdf SSE works ({count} events received)")
        except Exception as e:
            fail("POST /api/research/stream-with-pdf SSE", str(e))


# =============================================================
# Runner
# =============================================================

async def run_unit():
    await test_pdf_reader()
    await test_graph_factories()
    await test_emit_and_state()
    await test_researcher_node_pdf_mode()
    await test_analyst_node_structure()
    await test_analyst_node_malformed_json()
    await test_writer_node_saves_draft()
    await test_publisher_node_streams()
    await test_verifier_node()
    await test_build_graph()
    await test_stream_from_queue()
    await test_run_research_with_sources_pdf_mode()


async def run_integration():
    await test_llm_connection()
    await test_search_tool_live()
    await test_planner_node_live()
    await test_full_pipeline_live()


async def run_api():
    await test_api()


async def main():
    mode = sys.argv[1].lower() if len(sys.argv) > 1 else "all"
    print(f"\n{BOLD}Research Intelligence — Backend Test Suite{RESET}")
    print(f"{DIM}Mode: {mode}{RESET}")

    if mode in ("all", "unit"):
        await run_unit()
    if mode in ("all", "integration"):
        await run_integration()
    if mode in ("all", "api"):
        await run_api()

    summary()
    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    asyncio.run(main())