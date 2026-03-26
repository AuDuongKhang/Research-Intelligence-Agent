import os
from langchain_tavily import TavilySearch 

# ── Search Tool ───────────────────────────────────────────────

def get_search_tool():
    return TavilySearch(
        max_results=int(os.getenv("TAVILY_MAX_RESULTS", "5")),
        include_raw_content=True,
        include_images=False,
        tavily_api_key=os.getenv("TAVILY_API_KEY"),
    )