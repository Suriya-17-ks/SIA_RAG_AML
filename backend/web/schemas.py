from pydantic import BaseModel
from typing import Optional


class WebChunk(BaseModel):
    """Represents a web search result with reliability scoring."""
    content: str
    url: str
    title: Optional[str] = None
    reliability: float = 0.5  # 0.0 to 1.0 trust score
    snippet: Optional[str] = None  # Short preview
    source_type: str = "web"  # Could be "web", "wikipedia", "academic", etc.
    
    def __str__(self):
        return f"[WEB | {self.url} | reliability={self.reliability:.2f}] {self.content}"
