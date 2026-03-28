from agents.helper import get_llm, emit
from agents.helper import ResearchState
from langchain_core.messages import HumanMessage

# ── Node 4: Writer ────────────────────────────────────────────

async def writer_node(state: ResearchState) -> ResearchState:
    queue = state["event_queue"]

    await emit(queue, {
        "type": "thinking",
        "agent": "writer",
        "content": "Synthesizing final report from all collected data..."
    })

    llm = get_llm(temperature=0.4, model="llama-3.3-70b-versatile")

    findings = "\n".join([f"- {f}" for f in state["analysis"].get("key_findings", [])])
    contradictions = state["analysis"].get("contradictions", [])
    sources_text = "\n\n".join([
        f"[{c['id']}] {c['title']}\n{c['snippet']}"
        for c in state["citations"]
    ])
    contradiction_section = (
        "\nContradictions found:\n" + "\n".join(f"- {c}" for c in contradictions)
        if contradictions else ""
    )

    prompt = f"""You are a professional research writer. Write a comprehensive research report in English.

Original question: {state['query']}

Key findings:
{findings}
{contradiction_section}

Verified sources:
{sources_text}

Requirements:
- Markdown formatting with clear headings (##, ###)
- Cite sources using [1], [2], ... notation inline
- Structure: ## Executive Summary → ## Detailed Analysis → ## Contradictions (if any) → ## Conclusion
- Length: 500-700 words
- Tone: objective, analytical, academic
- Do NOT fabricate any facts not present in the sources above"""

    full_report = ""
    async for chunk in llm.astream([HumanMessage(content=prompt)]):
        text = chunk.content
        if text:
            full_report += text
            await emit(queue, {
                "agent": "writer",
                "type": "result",
                "content": text,
                "is_final": False
            })

    await emit(queue, {
        "agent": "writer",
        "type": "result",
        "content": "",
        "is_final": True
    })

    return {**state, "final_report": full_report}