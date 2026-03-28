import asyncio
from agents.helper import emit
from agents.helper import ResearchState
from tools.tavily_tool import get_search_tool

# ── Web search for each sub-question ─────────────────────
async def web_search(question, queue, search_tool):
    await emit(queue, {"type": "thinking", "agent": "researcher", "content": f"Searching: '{question}'"})
    await emit(queue, {"type": "tool_call", "agent": "researcher", "tool": "tavily_search", "params": {"query": question}, "status": "running"})
        
    try:
        tool_msg = await search_tool.ainvoke({"query": question})
        results = tool_msg.get("results", [])
        await emit(queue, {"type": "tool_call", "agent": "researcher", "tool": "tavily_search", "params": {"query": question}, "status": "done", "result_preview": f"Found {len(results)} sources"})
        return [{
            "question": question,
            "title": r.get("title", "Untitled"),
            "url": r.get("url", ""),
            "content": r.get("content", "")[:2000],
            "score": r.get("score", 0),
        } for r in results]
    except Exception as e:
        await emit(queue, {"type": "tool_call", "agent": "researcher", "tool": "tavily_search", "params": {"query": question}, "status": "error", "result_preview": str(e)})
        return []


# ── Node 2: Researcher ────────────────────────────────────────

async def researcher_node(state: ResearchState) -> ResearchState:
    queue = state["event_queue"]
    
    # ── PDF mode: sources already preloaded, skip web search ──
    if state.get("raw_sources"):
        await emit(queue, {
            "type":    "thinking",
            "agent":   "researcher",
            "content": f"Using {len(state['raw_sources'])} pre-loaded PDF "
                       f"chunk(s). Skipping web search."
        })
        return state
    
    search_tool = get_search_tool()
    all_sources: list[dict] = []
    
    tasks = [web_search(q, queue, search_tool) for q in state["sub_questions"]]
    search_results = await asyncio.gather(*tasks)
    
    new_sources = [item for sublist in search_results for item in sublist]
    all_sources = state.get("raw_sources", []) + new_sources
    
    await emit(queue, {
        "type": "thinking",
        "agent": "researcher",
        "content": f"Research complete. Collected {len(all_sources)} sources "
                   f"across {len(state['sub_questions'])} queries."
    })
 
    return {**state, "raw_sources": all_sources}