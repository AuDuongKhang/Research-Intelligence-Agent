import json
from langchain_core.messages import HumanMessage
from agents.helper import get_fast_llm, emit
from agents.helper import ResearchState

# ── Node 1: Planner ───────────────────────────────────────────

async def planner_node(state: ResearchState) -> ResearchState:
    queue = state["event_queue"]

    await emit(queue, {
        "type": "thinking",
        "agent": "planner",
        "content": f"Analyzing research request: '{state['query']}'..."
    })

    llm = get_fast_llm()

    prompt = f"""You are a research planner. Break the following question into 3-5 specific sub-questions to research.
Respond ONLY with a valid JSON array of strings. No explanation, no markdown, no extra text.

Question: {state['query']}

Example output: ["Sub-question 1", "Sub-question 2", "Sub-question 3"]"""

    response = await llm.ainvoke([HumanMessage(content=prompt)])

    try:
        raw = response.content.strip().removeprefix("```json").removesuffix("```").strip()
        sub_questions = json.loads(raw)
        if not isinstance(sub_questions, list):
            raise ValueError("Not a list")
    except (json.JSONDecodeError, ValueError):
        sub_questions = [state["query"]]

    await emit(queue, {
        "type": "thinking",
        "agent": "planner",
        "content": f"Research plan ready — {len(sub_questions)} sub-questions: "
                   + " | ".join(sub_questions)
    })

    return {**state, "sub_questions": sub_questions}