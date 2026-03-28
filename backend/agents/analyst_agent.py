from agents.helper import get_fast_llm, emit, extract_json
from agents.helper import ResearchState
from langchain_core.messages import HumanMessage


# ── Node 3: Analyst ───────────────────────────────────────────

async def analyst_node(state: ResearchState) -> ResearchState:
    queue = state["event_queue"]

    await emit(queue, {
        "type": "thinking",
        "agent": "analyst",
        "content": "Evaluating source credibility and detecting contradictions..."
    })

    llm = get_fast_llm()

    sources_text = "\n\n".join([
        f"[{i}] {s['title']}\nURL: {s['url']}\n{s['content'][:500]}"
        for i, s in enumerate(state["raw_sources"][:8])
    ])

    prompt = f"""Analyze the following sources and return a JSON object with this exact structure:
{{
  "key_findings": ["finding 1", "finding 2", "finding 3"],
  "contradictions": [],
  "credible_source_indices": [0, 1, 2],
  "overall_confidence": 0.85
}}

Sources (0-indexed):
{sources_text}

Return ONLY the JSON object. No markdown, no explanation."""

    response = await llm.ainvoke([HumanMessage(content=prompt)])
    analysis = extract_json(response.content)

    if not analysis:
        analysis = {"overall_confidence": 0, "key_findings": ["Failed to parse analysis"]}

    if analysis.get("contradictions"):
        await emit(queue, {
            "type": "thinking",
            "agent": "analyst",
            "content": f"Warning: detected {len(analysis['contradictions'])} "
                       f"contradiction(s) across sources."
        })

    confidence_pct = int(analysis.get("overall_confidence", 0.7) * 100)
    await emit(queue, {
        "type": "thinking",
        "agent": "analyst",
        "content": f"Analysis complete. Overall source confidence: {confidence_pct}%"
    })

    # Build citation list
    citations: list[dict] = []
    for idx in analysis.get("credible_source_indices", []):
        if idx < len(state["raw_sources"]):
            s = state["raw_sources"][idx]
            citations.append({
                "id": len(citations) + 1,
                "title": s["title"],
                "url": s["url"],
                "snippet": s["content"][:250],
                "credibility_score": analysis.get("overall_confidence", 0.7)
            })

    await emit(queue, {
        "type": "artifact",
        "kind": "citation_list",
        "title": "Verified Sources",
        "data": citations
    })

    return {**state, "analysis": analysis, "citations": citations}
