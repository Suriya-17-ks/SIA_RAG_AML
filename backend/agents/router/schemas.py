# backend/agents/router/schemas.py
from typing import List, Optional
from pydantic import BaseModel
from typing_extensions import Literal


class RouterDecision(BaseModel):
    intent: Literal[
        "fact",
        "summary",
        "regulatory_lookup",
        "gap_analysis",
        "cross_jurisdiction",
        "remediation",
    ]
    sources: List[Literal["pdf", "web"]]
    retrieval: Literal["sparse", "dense", "hybrid"]
    granularity: Literal["sentence", "section"]
    aml_regulation_type: Optional[str] = None
    detected_jurisdiction: Optional[Literal["india", "fatf", "eu", "usa", "cross"]] = None
