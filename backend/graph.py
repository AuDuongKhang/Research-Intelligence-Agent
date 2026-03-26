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
from agents.helper import ResearchState
from agents.planner_agent import planner_node
from agents.researcher_agent import researcher_node
from agents.analyst_agent import analyst_node
from agents.writer_agent import writer_node


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
    graph.add_edge("analyst",    "writer")
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

    while True:
        event = await queue.get()
        if event is None:
            break
        yield f"data: {event}\n\n"