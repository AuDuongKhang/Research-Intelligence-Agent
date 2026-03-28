import httpx
import asyncio
import json
import time

async def test_stream():
    url = "http://localhost:8000/api/research/stream"
    payload = {"query": "What are the latest breakthroughs in quantum computing 2025?"}
    
    print(f"{'Time (s)':<10} | {'Agent':<12} | {'Event Type':<12} | {'Content Preview'}")
    print("-" * 80)
    
    start_time = time.perf_counter()
    
    async with httpx.AsyncClient(timeout=120.0) as client:
        async with client.stream("POST", url, json=payload) as response:
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    elapsed = time.perf_counter() - start_time
                    event = json.loads(line[6:])
                    
                    agent = event.get("agent", "N/A")
                    etype = event.get("type", "N/A")

                    content = event.get("content", event.get("result_preview", ""))[:50]
                    
                    print(f"{elapsed:<10.2f} | {agent:<12} | {etype:<12} | {content}...")

if __name__ == "__main__":
    asyncio.run(test_stream())