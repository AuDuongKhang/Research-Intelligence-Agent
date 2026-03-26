"""
test_research.py — Backend Test Suite
======================================
Tests the research pipeline at three levels:
  1. Unit  — individual nodes (planner, researcher, analyst, writer)
  2. Integration — full graph run end-to-end
  3. API   — FastAPI SSE endpoint via HTTP

Usage:
  # Run all tests
  python test_backend.py

  # Run only one level
  python test_backend.py unit
  python test_backend.py integration
  python test_backend.py api
"""

import asyncio
import json
import os
import sys
import time
from dotenv import load_dotenv
from graph import run_research
from agents.helper import *
from agents.planner_agent import planner_node
from tools.tavily_tool import get_search_tool
from langchain_core.messages import HumanMessage

# ── Dependency check ─────────────────────────────────────────
# Give a clear error if .env is missing before anything else fails

if not os.path.exists(".env"):
    print("ERROR: .env file not found.")
    sys.exit(1)

load_dotenv()

MISSING_KEYS = []
if not os.getenv("GROQ_API_KEY"):
    MISSING_KEYS.append("GROQ_API_KEY")
if not os.getenv("TAVILY_API_KEY"):
    MISSING_KEYS.append("TAVILY_API_KEY")

if MISSING_KEYS:
    print(f"ERROR: Missing keys in .env: {', '.join(MISSING_KEYS)}")
    sys.exit(1)


# ── Helpers ───────────────────────────────────────────────────

BOLD  = "\033[1m"
GREEN = "\033[92m"
RED   = "\033[91m"
CYAN  = "\033[96m"
DIM   = "\033[2m"
RESET = "\033[0m"

TEST_QUERY = "What are the latest breakthroughs in quantum computing in 2025?"

passed = 0
failed = 0


def section(title: str):
    print(f"\n{BOLD}{CYAN}{'─'*50}{RESET}")
    print(f"{BOLD}{CYAN}  {title}{RESET}")
    print(f"{BOLD}{CYAN}{'─'*50}{RESET}")


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


def summary():
    total = passed + failed
    color = GREEN if failed == 0 else RED
    print(f"\n{BOLD}{color}{'─'*50}")
    print(f"  Results: {passed}/{total} passed", end="")
    if failed:
        print(f"  ({failed} failed)", end="")
    print(f"{RESET}\n")


# ═════════════════════════════════════════════════════════════
# LEVEL 1 — Unit Tests
# ═════════════════════════════════════════════════════════════

async def test_llm_connection():
    """Verify Groq API key works and model responds."""
    section("Unit: LLM Connection (Groq)")

    for name, llm in [("llama-3.1-8b-instant (fast)", get_fast_llm()),
                       ("llama-3.3-70b-versatile (main)", get_llm())]:
        try:
            t0 = time.time()
            response = await llm.ainvoke([HumanMessage(content="Reply with one word: ready")])
            elapsed = time.time() - t0
            assert response.content.strip(), "Empty response"
            ok(name, f"{elapsed:.1f}s → '{response.content.strip()[:40]}'")
        except Exception as e:
            fail(name, str(e))


async def test_search_tool():
    """Verify Tavily API key works and returns results."""
    section("Unit: Search Tool (Tavily)")

    tool = get_search_tool()
    try:
        t0 = time.time()
        tool_msg = tool.invoke({"query": "quantum computing 2025"})
        results = tool_msg.get("results", [])
        elapsed = time.time() - t0

        assert isinstance(results, list), "Results not a list"
        assert len(results) > 0, "No results returned"

        ok("Tavily returned results", f"{elapsed:.1f}s → {len(results)} sources")

        # Check result structure
        first = results[0]
        for field in ["title", "url", "content"]:
            if field in first:
                ok(f"  Result has '{field}'", str(first[field])[:60])
            else:
                fail(f"  Result missing '{field}'")

    except Exception as e:
        fail("Tavily search", str(e))


async def test_planner_node():
    """Verify planner produces valid sub-questions."""
    section("Unit: Planner Node")

    queue: asyncio.Queue = asyncio.Queue()
    state: ResearchState = {
        "query": TEST_QUERY,
        "sub_questions": [],
        "raw_sources": [],
        "analysis": {},
        "final_report": "",
        "citations": [],
        "event_queue": queue,
    }

    try:
        result = await planner_node(state)
        sub_qs = result["sub_questions"]

        assert isinstance(sub_qs, list), "sub_questions not a list"
        assert len(sub_qs) >= 2, f"Expected ≥2 sub-questions, got {len(sub_qs)}"
        ok(f"Generated {len(sub_qs)} sub-questions")

        for i, q in enumerate(sub_qs):
            ok(f"  [{i+1}] {q[:70]}")

        # Check emitted events
        events = []
        while not queue.empty():
            events.append(json.loads(await queue.get()))

        thinking_events = [e for e in events if e.get("type") == "thinking"]
        assert len(thinking_events) >= 1, "No thinking events emitted"
        ok(f"Emitted {len(thinking_events)} thinking event(s)")

    except AssertionError as e:
        fail("Planner node", str(e))
    except Exception as e:
        fail("Planner node (unexpected error)", str(e))


async def test_event_emission():
    """Verify all required SSE event types can be constructed."""
    section("Unit: SSE Event Types")

    required_event_types = [
        {"type": "thinking",  "agent": "planner",    "content": "test"},
        {"type": "tool_call", "tool": "tavily_search","params": {}, "status": "running"},
        {"type": "tool_call", "tool": "tavily_search","params": {}, "status": "done", "result_preview": "3 sources"},
        {"type": "result",    "content": "chunk",    "is_final": False},
        {"type": "result",    "content": "",          "is_final": True},
        {"type": "artifact",  "kind": "citation_list","title": "Sources", "data": []},
        {"type": "error",     "message": "test error"},
    ]

    for event in required_event_types:
        try:
            serialized = json.dumps(event)
            parsed = json.loads(serialized)
            assert parsed["type"] == event["type"]
            ok(f"type='{event['type']}'", f"agent/tool={event.get('agent', event.get('tool', '—'))}")
        except Exception as e:
            fail(f"type='{event['type']}'", str(e))


# ═════════════════════════════════════════════════════════════
# LEVEL 2 — Integration Test (full graph)
# ═════════════════════════════════════════════════════════════

async def test_full_pipeline():
    """Run the complete 4-node graph and validate all SSE events."""
    section("Integration: Full Research Pipeline")
    print(f"  {DIM}Query: {TEST_QUERY}{RESET}")
    print(f"  {DIM}(This will take ~20-40s — Groq is fast but search takes time){RESET}\n")


    events_by_type: dict[str, list] = {
        "thinking": [], "tool_call": [], "result": [], "artifact": [], "error": []
    }
    agents_seen: set[str] = set()
    tools_seen: set[str] = set()
    result_chunks = []
    t0 = time.time()

    try:
        async for raw in run_research(TEST_QUERY):
            # Strip SSE prefix "data: " and parse
            line = raw.strip()
            if not line.startswith("data: "):
                continue
            event = json.loads(line[6:])
            event_type = event.get("type", "unknown")

            if event_type in events_by_type:
                events_by_type[event_type].append(event)

            # Live progress indicator
            if event_type == "thinking":
                agent = event.get("agent", "?")
                agents_seen.add(agent)
                print(f"  {DIM}[{agent}] {event.get('content', '')[:70]}{RESET}")

            elif event_type == "tool_call":
                tool = event.get("tool", "?")
                status = event.get("status", "?")
                tools_seen.add(tool)
                if status == "running":
                    q = event.get("params", {}).get("query", "")[:50]
                    print(f"  {DIM}[tool] {tool}: '{q}'{RESET}")

            elif event_type == "result" and not event.get("is_final"):
                result_chunks.append(event.get("content", ""))

        elapsed = time.time() - t0

        # ── Assertions ────────────────────────────────────────
        print()

        # All 4 agents ran
        expected_agents = {"planner", "researcher", "analyst", "writer"}
        for agent in expected_agents:
            if agent in agents_seen:
                ok(f"Agent '{agent}' executed")
            else:
                fail(f"Agent '{agent}' did NOT execute")

        # Thinking events emitted
        n_thinking = len(events_by_type["thinking"])
        if n_thinking >= 4:
            ok(f"Thinking events emitted ({n_thinking} total)")
        else:
            fail(f"Too few thinking events (got {n_thinking}, expected ≥4)")

        # Tool calls emitted
        n_tools = len(events_by_type["tool_call"])
        if n_tools >= 2:
            ok(f"Tool call events emitted ({n_tools} total)", f"tools: {', '.join(tools_seen)}")
        else:
            fail(f"Too few tool call events (got {n_tools})")

        # Artifact (citation list) emitted
        artifacts = events_by_type["artifact"]
        citation_artifacts = [a for a in artifacts if a.get("kind") == "citation_list"]
        if citation_artifacts:
            n_cits = len(citation_artifacts[0].get("data", []))
            ok(f"Citation artifact emitted ({n_cits} citations)")
        else:
            fail("No citation_list artifact emitted")

        # Final report generated
        full_report = "".join(result_chunks)
        if len(full_report) >= 200:
            ok(f"Final report generated ({len(full_report)} chars, {elapsed:.1f}s total)")
            print(f"\n  {DIM}── Report preview (first 300 chars) ──{RESET}")
            print(f"  {DIM}{full_report[:300].strip()}...{RESET}\n")
        else:
            fail(f"Report too short ({len(full_report)} chars)")

        # No errors
        if events_by_type["error"]:
            for err in events_by_type["error"]:
                fail(f"Pipeline error: {err.get('message', '?')}")
        else:
            ok("No errors during pipeline")

    except Exception as e:
        fail("Full pipeline", str(e))
        import traceback; traceback.print_exc()


# ═════════════════════════════════════════════════════════════
# LEVEL 3 — API Tests (requires running server)
# ═════════════════════════════════════════════════════════════

async def test_api_endpoints():
    """Test FastAPI endpoints via HTTP. Requires `python main.py` running."""
    section("API: FastAPI Endpoint Tests")

    try:
        import httpx
    except ImportError:
        print(f"  {DIM}Skipping API tests — install httpx: pip install httpx{RESET}")
        return

    base = "http://localhost:8000"

    async with httpx.AsyncClient(timeout=10.0) as client:

        # GET /health
        try:
            r = await client.get(f"{base}/health")
            assert r.status_code == 200
            ok("GET /health → 200")
        except Exception as e:
            fail("GET /health", f"{e} — is the server running? (python main.py)")
            print(f"  {DIM}Skipping remaining API tests.{RESET}")
            return

        # GET /
        try:
            r = await client.get(f"{base}/")
            assert r.status_code == 200
            ok("GET / → 200")
        except Exception as e:
            fail("GET /", str(e))

        # POST /api/research/stream — validation: too short query
        try:
            r = await client.post(
                f"{base}/api/research/stream",
                json={"query": "hi"},   # min_length=10 in Pydantic model
            )
            assert r.status_code == 422, f"Expected 422, got {r.status_code}"
            ok("POST /stream rejects short query → 422")
        except Exception as e:
            fail("POST /stream validation", str(e))

        # POST /api/research/stream — valid request, read first few events only
        try:
            print(f"\n  {DIM}Streaming first 5 events from /api/research/stream...{RESET}")
            events_received = 0

            async with client.stream(
                "POST",
                f"{base}/api/research/stream",
                json={"query": TEST_QUERY},
                timeout=30.0,
            ) as response:
                assert response.status_code == 200, f"Expected 200, got {response.status_code}"
                assert "text/event-stream" in response.headers.get("content-type", "")

                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        event = json.loads(line[6:])
                        events_received += 1
                        print(f"  {DIM}  event {events_received}: type={event['type']}{RESET}")
                        if events_received >= 5:
                            break  # Don't wait for full run

            ok(f"SSE stream started, received {events_received} events")

        except Exception as e:
            fail("POST /stream SSE", str(e))


# ═════════════════════════════════════════════════════════════
# Runner
# ═════════════════════════════════════════════════════════════

async def run_unit():
    await test_llm_connection()
    await test_search_tool()
    await test_planner_node()
    await test_event_emission()

async def run_integration():
    await test_full_pipeline()

async def run_api():
    await test_api_endpoints()

async def main():
    mode = sys.argv[1].lower() if len(sys.argv) > 1 else "all"

    print(f"\n{BOLD}Research Intelligence — Backend Tests{RESET}")
    print(f"{DIM}Mode: {mode}  |  Query: \"{TEST_QUERY[:50]}...\"{RESET}")

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