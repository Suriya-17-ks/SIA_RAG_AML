# backend/web/parser.py
from typing import List, Dict
from backend.web.schemas import WebChunk
# Removed bs4 import as we aren't using it yet for simple snippet parsing
# from bs4 import BeautifulSoup 


# Trusted domains get higher reliability scores
TRUSTED_DOMAINS = {
    "wikipedia.org": 0.9,
    "ieee.org": 0.95,
    "arxiv.org": 0.9,
    "sciencedirect.com": 0.85,
    "springer.com": 0.85,
    "nature.com": 0.9,
    ".gov": 0.95,
    ".edu": 0.85,
}


def calculate_reliability(url: str, title: str = "") -> float:
    """Calculate trust score based on domain and source type."""
    url_lower = url.lower()
    
    # Check against trusted domains
    for domain, score in TRUSTED_DOMAINS.items():
        if domain in url_lower:
            return score
    
    # Default scores for other domains
    if any(ext in url_lower for ext in ['.gov', '.edu']):
        return 0.85
    elif 'wiki' in url_lower:
        return 0.8
    else:
        return 0.6  # Generic web source


def parse_web_results(raw_results: List[Dict]) -> List[WebChunk]:
    """
    Parse raw web search results into WebChunk objects with reliability scoring.
    
    Args:
        raw_results: List of dicts from web search API
    
    Returns:
        List of WebChunk objects
    """
    chunks = []
    
    for result in raw_results:
        url = result.get('url', result.get('link', ''))
        title = result.get('title', '')
        snippet = result.get('snippet', result.get('description', ''))
        content = result.get('content', snippet)
        
        # Calculate reliability score
        reliability = calculate_reliability(url, title)
        
        # Determine source type
        source_type = "web"
        if "wikipedia" in url.lower():
            source_type = "wikipedia"
        elif any(ext in url.lower() for ext in ['.gov', '.edu']):
            source_type = "official"
        elif any(domain in url.lower() for domain in ["ieee", "arxiv", "springer", "nature"]):
            source_type = "academic"
        
        chunk = WebChunk(
            content=content,
            url=url,
            title=title,
            reliability=reliability,
            snippet=snippet,
            source_type=source_type
        )
        
        chunks.append(chunk)
    
    return chunks
