from agents.helper import emit
from agents.helper import ResearchState
from tools.tavily_tool import get_search_tool

# ── Node 2: Researcher ────────────────────────────────────────

async def researcher_node(state: ResearchState) -> ResearchState:
    queue = state["event_queue"]
    search_tool = get_search_tool()
    all_sources: list[dict] = []

    for question in state["sub_questions"]:
        await emit(queue, {
            "type": "thinking",
            "agent": "researcher",
            "content": f"Searching: '{question}'"
        })

        await emit(queue, {
            "type": "tool_call",
            "tool": "tavily_search",
            "params": {"query": question},
            "status": "running"
        })

        try:
            tool_msg = search_tool.invoke({"query": question})
            results = tool_msg.get("results", [])

            await emit(queue, {
                "type": "tool_call",
                "tool": "tavily_search",
                "params": {"query": question},
                "status": "done",
                "result_preview": f"Found {len(results)} sources"
            })

            for r in results:
                all_sources.append({
                    "question": question,
                    "title": r.get("title", "Untitled"),
                    "url": r.get("url", ""),
                    "content": r.get("content", "")[:2000],
                    "score": r.get("score", 0),
                })

        except Exception as e:
            await emit(queue, {
                "type": "tool_call",
                "tool": "tavily_search",
                "params": {"query": question},
                "status": "error",
                "result_preview": str(e)
            })

    await emit(queue, {
        "type": "thinking",
        "agent": "researcher",
        "content": f"Research complete. Collected {len(all_sources)} sources "
                   f"across {len(state['sub_questions'])} queries."
    })

    return {**state, "raw_sources": all_sources}