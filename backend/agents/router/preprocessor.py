"""
Query Preprocessor for Router Enhancement

Detects query patterns and provides hints to improve router classification.
"""

import re
from typing import Dict, Optional
from dataclasses import dataclass


@dataclass
class QueryHints:
    """Hints derived from query preprocessing."""
    is_definitional: bool = False
    is_technical_detail: bool = False
    is_comparison: bool = False
    suggested_intent: Optional[str] = None
    suggested_granularity: Optional[str] = None
    suggested_retrieval: Optional[str] = None
    confidence: float = 0.0
    reasoning: str = ""


class QueryPreprocessor:
    """Analyzes queries and provides classification hints."""
    
    # Definitional query patterns
    DEFINITIONAL_STARTERS = [
        r"^what\s+is\s+",
        r"^what\s+are\s+",
        r"^define\s+",
        r"^explain\s+",
        r"^describe\s+",
        r"^overview\s+of\s+",
        r"^introduction\s+to\s+",
        r"^give\s+me\s+(an?\s+)?(intro|overview|definition)",
    ]
    
    # Technical detail patterns
    TECHNICAL_DETAIL_PATTERNS = [
        r"how\s+is\s+\w+\s+calculated",
        r"what\s+is\s+the\s+(formula|equation|calculation)",
        r"how\s+to\s+compute",
        r"step-by-step",
        r"algorithm for",
        r"implementation of",
        r"code for",
    ]
    
    # Comparison patterns
    COMPARISON_PATTERNS = [
        r"compare\s+",
        r"difference\s+between",
        r"versus",
        r"\s+vs\s+",
        r"similarities\s+(and\s+)?differences",
        r"better\s+than",
        r"advantage\s+of",
    ]
    
    # Summary indicators
    SUMMARY_INDICATORS = [
        r"summarize",
        r"summary\s+of",
        r"main\s+points",
        r"key\s+concepts",
        r"overall",
        r"in\s+general",
    ]
    
    # Specific fact patterns
    FACT_PATTERNS = [
        r"how\s+many",
        r"how\s+much",
        r"when\s+(did|was|were)",
        r"who\s+(is|was|were)",
        r"where\s+(is|was|were)",
        r"which\s+\w+\s+(has|have|had)",
        r"what\s+(year|date|time|number|value|percentage)",
    ]
    
    def __init__(self):
        """Initialize preprocessor with compiled regex patterns."""
        self.definitional_patterns = [
            re.compile(pattern, re.IGNORECASE) 
            for pattern in self.DEFINITIONAL_STARTERS
        ]
        self.technical_patterns = [
            re.compile(pattern, re.IGNORECASE) 
            for pattern in self.TECHNICAL_DETAIL_PATTERNS
        ]
        self.comparison_patterns = [
            re.compile(pattern, re.IGNORECASE) 
            for pattern in self.COMPARISON_PATTERNS
        ]
        self.summary_patterns = [
            re.compile(pattern, re.IGNORECASE) 
            for pattern in self.SUMMARY_INDICATORS
        ]
        self.fact_patterns = [
            re.compile(pattern, re.IGNORECASE) 
            for pattern in self.FACT_PATTERNS
        ]
    
    def analyze(self, query: str) -> QueryHints:
        """
        Analyze query and return classification hints.
        
        Args:
            query: User query string
            
        Returns:
            QueryHints with suggested classifications
        """
        query = query.strip()
        hints = QueryHints()
        
        # Check for definitional queries
        if self._is_definitional(query):
            hints.is_definitional = True
            hints.suggested_intent = "summary"
            hints.suggested_granularity = "section"
            hints.suggested_retrieval = "hybrid"
            hints.confidence = 0.9
            hints.reasoning = "Query asks for definition/explanation (e.g., 'what is', 'define', 'explain')"
            return hints
        
        # Check for comparisons
        if self._is_comparison(query):
            hints.is_comparison = True
            hints.suggested_intent = "comparison"
            hints.suggested_granularity = "section"
            hints.suggested_retrieval = "hybrid"
            hints.confidence = 0.85
            hints.reasoning = "Query asks to compare multiple items"
            return hints
        
        # Check for technical details
        if self._is_technical_detail(query):
            hints.is_technical_detail = True
            hints.suggested_intent = "fact"
            hints.suggested_granularity = "sentence"
            hints.suggested_retrieval = "sparse"
            hints.confidence = 0.8
            hints.reasoning = "Query asks for specific technical detail or formula"
            return hints
        
        # Check for summary requests
        if self._is_summary_request(query):
            hints.suggested_intent = "summary"
            hints.suggested_granularity = "section"
            hints.suggested_retrieval = "dense"
            hints.confidence = 0.75
            hints.reasoning = "Query asks for summary or overview"
            return hints
        
        # Check for specific facts
        if self._is_fact_query(query):
            hints.suggested_intent = "fact"
            hints.suggested_granularity = "sentence"
            hints.suggested_retrieval = "hybrid"
            hints.confidence = 0.7
            hints.reasoning = "Query asks for specific factual information"
            return hints
        
        # Default: low confidence, let LLM decide
        hints.confidence = 0.0
        hints.reasoning = "No strong pattern match, defer to LLM classification"
        return hints
    
    def _is_definitional(self, query: str) -> bool:
        """Check if query is asking for a definition."""
        return any(pattern.search(query) for pattern in self.definitional_patterns)
    
    def _is_technical_detail(self, query: str) -> bool:
        """Check if query is asking for technical details."""
        return any(pattern.search(query) for pattern in self.technical_patterns)
    
    def _is_comparison(self, query: str) -> bool:
        """Check if query is asking for comparison."""
        return any(pattern.search(query) for pattern in self.comparison_patterns)
    
    def _is_summary_request(self, query: str) -> bool:
        """Check if query is asking for summary."""
        return any(pattern.search(query) for pattern in self.summary_patterns)
    
    def _is_fact_query(self, query: str) -> bool:
        """Check if query is asking for specific fact."""
        return any(pattern.search(query) for pattern in self.fact_patterns)
    
    def get_override_decision(self, query: str) -> Optional[Dict[str, str]]:
        """
        Get a high-confidence override decision if applicable.
        
        Returns None if confidence < 0.85, otherwise returns a decision dict.
        """
        hints = self.analyze(query)
        
        if hints.confidence >= 0.85:
            decision = {}
            if hints.suggested_intent:
                decision["intent"] = hints.suggested_intent
            if hints.suggested_granularity:
                decision["granularity"] = hints.suggested_granularity
            if hints.suggested_retrieval:
                decision["retrieval"] = hints.suggested_retrieval
            
            return decision if decision else None
        
        return None


# Global instance for reuse
preprocessor = QueryPreprocessor()


def preprocess_query(query: str) -> QueryHints:
    """
    Convenience function to analyze a query.
    
    Args:
        query: User query string
        
    Returns:
        QueryHints with classification suggestions
    """
    return preprocessor.analyze(query)
