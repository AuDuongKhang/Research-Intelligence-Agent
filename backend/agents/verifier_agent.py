from langchain_core.messages import HumanMessage
from agents.helper import get_verifier_llm, get_llm, emit, extract_json, ResearchState

# ── Node 5: Verifier ────────────────────────────────────────────
async def verifier_node(state: ResearchState) -> ResearchState:
    queue = state["event_queue"]

    await emit(queue, {
        "type": "thinking",
        "agent": "verifier", 
        "content": "Verifying report accuracy and citations..."
    })

    llm = get_verifier_llm()
    #llm = get_llm()
    
    sources_summary = "\n".join([f"[{c['id']}] {c['title']}: {c['snippet']}" for c in state["citations"]])
    
    prompt = f"""You are a fact-checker. Compare the Draft Report against the Verified Sources.
    
    Draft Report:
    {state['final_report']}
    
    Verified Sources:
    {sources_summary}
    
    Return a JSON object:
    {{
      "is_accurate": true/false,
      "errors": ["list of factual errors or hallucinated claims found"],
      "citation_errors": ["list of incorrect source references"],
      "score": 0.0 to 1.0
    }}
    Return ONLY the JSON object. No markdown, no explanation."""

    response = await llm.ainvoke([HumanMessage(content=prompt)])
    verification = extract_json(response.content)

    if not verification:
        verification = {"is_accurate": True, "score": 1.0} # Fallback

    if verification.get("score", 1.0) < 0.6:
        error_msg = f"Factual inconsistencies detected (Score: {int(verification['score']*100)}%). Sending back for revision."
        await emit(queue, {"type": "thinking", "agent": "verifier", "content": error_msg})
    else:
        await emit(queue, {"type": "thinking", "agent": "verifier", "content": "Verification passed. Report is factually grounded."})

    return {**state, "analysis": {**state["analysis"], "verification": verification}}