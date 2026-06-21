# backend/web/client.py
import requests
from typing import List, Dict
from backend.config.settings import settings


def web_search(query: str, k: int = None) -> List[Dict]:
    """
    Fetch raw web search results constraint.
    Tries Tavily first, then generic search endpoint.
    Returns raw JSON-like dicts, or empty list if unconfigured.
    """
    k = k or settings.web_search_max_results

    # 1. Try Tavily
    if settings.tavily_api_key:
        try:
            response = requests.post(
                "https://api.tavily.com/search",
                json={
                    "api_key": settings.tavily_api_key,
                    "query": query,
                    "search_depth": "basic",
                    "max_results": k,
                },
                timeout=15,
            )
            response.raise_for_status()
            results = response.json().get("results", [])
            # Map Tavily result format to generic format expected by parser
            return [{"title": r.get("title", ""), "link": r.get("url", ""), "snippet": r.get("content", "")} for r in results]
        except Exception as e:
            print(f"[web_client] Tavily search failed: {e}")
            return []

    # 2. Try Generic Endpoint
    if settings.search_api_key and settings.search_endpoint:
        try:
            response = requests.get(
                settings.search_endpoint,
                params={
                    "q": query,
                    "num": k,
                    "api_key": settings.search_api_key,
                },
                timeout=10,
            )
            response.raise_for_status()
            return response.json().get("results", [])
        except Exception as e:
            print(f"[web_client] Generic search failed: {e}")
            return []

    # 3. Handle unconfigured state gracefully
    print("[WARNING] No web search API configured (TAVILY_API_KEY or SEARCH_API_KEY). Skipping web search.")
    return []
