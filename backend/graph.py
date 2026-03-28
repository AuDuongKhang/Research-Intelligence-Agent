"""
graph.py — LangGraph Research Workflow
=======================================
Stack: Groq (Llama 3.3 70B) + Tavily Search
Pipeline: Planner → Researcher → Analyst → Writer

Each node emits SSE events into an asyncio.Queue.
main.py reads that queue and streams events to the client.
"""

import asyncio
import json

from typing import AsyncGenerator
from langgraph.graph import StateGraph, END
from agents.helper import ResearchState, _stream_from_queue
from agents.planner_agent import planner_node
from agents.researcher_agent import researcher_node
from agents.analyst_agent import analyst_node
from agents.writer_agent import writer_node

def should_continue(state: ResearchState):
    analysis = state.get("analysis", {})
    loop_step = state.get("loop_step", 0)
    
    if analysis.get("overall_confidence", 1.0) < 0.6 and loop_step < 2:
        return "researcher"
    return "writer"


# ── Build Graph ───────────────────────────────────────────────

def build_graph():
    graph = StateGraph(ResearchState)

    graph.add_node("planner",    planner_node)
    graph.add_node("researcher", researcher_node)
    graph.add_node("analyst",    analyst_node)
    graph.add_node("writer",     writer_node)

    graph.set_entry_point("planner")
    graph.add_edge("planner",    "researcher")
    graph.add_edge("researcher", "analyst")
    graph.add_conditional_edges(
        "analyst",
        should_continue,
        {
            "researcher": "researcher",
            "writer": "writer"
        }
    )
    graph.add_edge("writer",     END)

    return graph.compile()


research_graph = build_graph()


# ── Public API ────────────────────────────────────────────────

async def run_research(query: str) -> AsyncGenerator[str, None]:
    """
    Run the full research pipeline and yield SSE-formatted strings.
    Called by main.py's StreamingResponse.
    """
    queue: asyncio.Queue = asyncio.Queue()
 
    async def _run():
        try:
            await research_graph.ainvoke({
                "query": query,
                "sub_questions": [],
                "raw_sources": [],
                "analysis": {},
                "final_report": "",
                "citations": [],
                "event_queue": queue,
            })
        except Exception as e:
            await queue.put(json.dumps({
                "type": "error",
                "message": f"Pipeline error: {str(e)}"
            }))
        finally:
            await queue.put(None)
 
    asyncio.create_task(_run())
    
    yield f": {' ' * 2048}\n\n"
    
    async for event in _stream_from_queue(queue):
        yield event
 
 
async def run_research_with_sources(
    query: str,
    preloaded_sources: list[dict],
) -> AsyncGenerator[str, None]:
    """
    PDF mode — pre-extracted PDF chunks are injected as raw_sources.
    researcher_node detects non-empty raw_sources and skips web search.
    Pipeline still runs full Planner → Researcher → Analyst → Writer.
    """
    queue: asyncio.Queue = asyncio.Queue()
 
    async def _run():
        try:
            # Emit a tool_call event so the UI shows the PDF was loaded
            await queue.put(json.dumps({
                "type":           "tool_call",
                "tool":           "pdf_reader",
                "params":         {"filename": preloaded_sources[0].get("title", "upload.pdf")},
                "status":         "done",
                "result_preview": f"Extracted {len(preloaded_sources)} chunk(s) from PDF"
            }))
 
            await research_graph.ainvoke({
                "query":         query,
                "sub_questions": [],
                "raw_sources":   preloaded_sources,  # non-empty → researcher skips web search
                "analysis":      {},
                "final_report":  "",
                "citations":     [],
                "event_queue":   queue,
            })
        except Exception as e:
            await queue.put(json.dumps({
                "type":    "error",
                "message": f"Pipeline error: {str(e)}"
            }))
        finally:
            await queue.put(None)
 
    asyncio.create_task(_run())
    
    yield f": {' ' * 2048}\n\n"
    
    async for event in _stream_from_queue(queue):
        yield event