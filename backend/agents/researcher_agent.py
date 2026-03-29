import asyncio
import json
from agents.helper import emit, extract_json
from agents.helper import get_fast_llm, ResearchState
from tools.tavily_tool import get_search_tool
from langchain_core.messages import HumanMessage

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


async def select_tools_for_questions(questions: list[str], has_pdf: bool) -> list[dict]:
    """Use LLM to assign the best tool for each question."""
    llm = get_fast_llm()
    
    # Only allow PDF selection if the user has uploaded a file
    tools_available = ["web_search", "arxiv_search"]
    if has_pdf: tools_available.append("pdf_reader")
    
    prompt = f"""Assign the best tool for each research question.
    Available Tools: {tools_available}
    
    Questions:
    {json.dumps(questions)}
    
    Return a JSON object with this exact structure: [{{"question": "...", "tool": "..."}}]
    Return ONLY the JSON object. No markdown, no explanation"""

    response = await llm.ainvoke([HumanMessage(content=prompt)])

    return extract_json(response.content) or [{"question": q, "tool": "web_search"} for q in questions]


# ── Node 2: Researcher ────────────────────────────────────────

async def researcher_node(state: ResearchState) -> ResearchState:
    queue = state["event_queue"]
    has_pdf = len(state.get("pdf_sources", [])) > 0
    if has_pdf and not state.get("raw_sources"):
        await emit(queue, {
            "type":    "thinking",
            "agent":   "researcher",
            "content": f"Using {len(state['pdf_sources'])} pre-loaded PDF chunk(s). Skipping web search."
        })
        return {**state, "raw_sources": state["pdf_sources"]}

    await emit(queue, {"type": "thinking", "agent": "researcher", "content": "Orchestrating tools based on query intent..."})
    
    # Select tools for each question (e.g., PDF search vs web search)
    plan = await select_tools_for_questions(state["sub_questions"], has_pdf)
    
    if isinstance(plan, dict):
        plan = [plan]
    elif not plan:
        plan = [{"question": q, "tool": "web_search"} for q in state["sub_questions"]]
        
    search_tool = get_search_tool()
    tasks = []
    
    # Choose search method for each question based on LLM plan
    for item in plan:
        q = item["question"]
        tool = item["tool"]
        
        if has_pdf:
            await emit(queue, {
            "type":    "thinking",
            "agent":   "researcher",
            "content": f"Using {len(state['pdf_sources'])} pre-loaded PDF "
                       f"chunk(s). Skipping web search."
            })
            return state
        elif tool == "arxiv_search":
            tasks.append(web_search(f"site:arxiv.org {q}", queue, search_tool))
        else:
            tasks.append(web_search(q, queue, search_tool))

    search_results = await asyncio.gather(*tasks)
    new_sources = [item for sublist in search_results for item in sublist]
    
    # Update state
    all_sources = state.get("raw_sources", []) + new_sources
    
    await emit(queue, {
        "type": "thinking",
        "agent": "researcher",
        "content": f"Research complete. Collected {len(all_sources)} sources "
                   f"across {len(state['sub_questions'])} queries."
    })
    
    return {**state, "raw_sources": all_sources}