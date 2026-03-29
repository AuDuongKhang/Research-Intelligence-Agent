import asyncio
from agents.helper import emit, ResearchState

async def publisher_node(state: ResearchState) -> ResearchState:
    """Final node that simulates publishing the report."""
    queue = state["event_queue"]
    report = state["final_report"]
    
    await emit(queue, {"type": "thinking", "agent": "publisher", "content": "Finalizing and publishing report..."})

    words = report.split(' ')
    for i in range(0, len(words), 5):
        chunk = " ".join(words[i:i+5]) + " "
        await emit(queue, {
            "type": "result",
            "content": chunk,
            "is_final": False
        })
        await asyncio.sleep(0.02)

    await emit(queue, {"type": "result", "content": "", "is_final": True})
    return state