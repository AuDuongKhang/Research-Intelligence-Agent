from agents.helper import get_writer_llm, get_llm, emit
from agents.helper import ResearchState
from langchain_core.messages import HumanMessage

# ── Node 4: Writer ────────────────────────────────────────────

async def writer_node(state: ResearchState) -> ResearchState:
    queue = state["event_queue"]
    
    # First check if we're here for a revision based on Verifier feedback or the initial writing step
    verification = state.get("analysis", {}).get("verification", {})
    is_revision = verification.get("is_accurate") == False
    
    status_msg = "Revising report based on verification feedback..." if is_revision else "Synthesizing final report from all collected data..."
    await emit(queue, {
        "type": "thinking",
        "agent": "writer",
        "content": status_msg
    })

    llm = get_writer_llm()
    #llm = get_llm()
    
    findings = "\n".join([f"- {f}" for f in state["analysis"].get("key_findings", [])])
    sources_text = "\n\n".join([f"[{c['id']}] {c['title']}\n{c['snippet']}" for c in state["citations"]])
    
    # Add detailed revision instructions if this is a rewrite based on verification feedback
    revision_instructions = ""
    if is_revision:
        errors = "\n".join([f"- {e}" for e in verification.get("errors", [])])
        cit_errors = "\n".join([f"- {e}" for e in verification.get("citation_errors", [])])
        revision_instructions = f"""
        ### REVISION REQUIRED
        The previous draft had the following issues:
        Factual Errors:
        {errors}
        Citation Issues:
        {cit_errors}
        
        Please correct these specific issues while maintaining the overall structure.
        """

    prompt = f"""You are a professional research writer. Write a comprehensive research report in English.
    
    Original question: {state['query']}
    {revision_instructions}
    
    Key findings:
    {findings}
    
    Verified sources:
    {sources_text}

    Requirements:
    - Markdown formatting with clear headings (##)
    - Cite sources using [1], [2], ... notation inline
    - Structure: ## Executive Summary → ## Detailed Analysis → ## Contradictions (if any) → ## Conclusion
    - Length: 500-700 words
    - Tone: objective, analytical, academic
    - Do NOT fabricate any facts not present in the sources above."""

    full_report = ""
    async for chunk in llm.astream([HumanMessage(content=prompt)]):
        text = chunk.content
        if text:
            full_report += text

    return {**state, "final_report": full_report}