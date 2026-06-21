"""
Prometheus-style metrics tracking for SIA-RAG system.
Maintains counters and gauges for API latency, LLM checks, and cache hits.

Note: In a true production environment, we'd use prometheus_client and
expose a /metrics endpoint, but for this demo/research framework we
can maintain a simple singleton to track and log key metrics.
"""
import time
import logging
from collections import defaultdict
from typing import Dict, Any

logger = logging.getLogger(__name__)

class MetricsTracker:
    def __init__(self):
        self.counters: Dict[str, int] = defaultdict(int)
        self.gauges: Dict[str, float] = defaultdict(float)
        self.histograms: Dict[str, list] = defaultdict(list)
    
    def inc(self, metric: str, value: int = 1):
        """Increment a counter."""
        self.counters[metric] += value
    
    def set_gauge(self, metric: str, value: float):
        """Set a point-in-time value."""
        self.gauges[metric] = value
        
    def observe(self, metric: str, value: float):
        """Add to a histogram/distribution."""
        self.histograms[metric].append(value)
        # Prevent unbounded growth in memory
        if len(self.histograms[metric]) > 1000:
            self.histograms[metric] = self.histograms[metric][-1000:]
            
    def get_summary(self) -> Dict[str, Any]:
        """Return a snapshot of current metrics."""
        summary = {
            "counters": dict(self.counters),
            "gauges": dict(self.gauges),
            "averages": {}
        }
        for metric, values in self.histograms.items():
            if values:
                summary["averages"][f"{metric}_avg"] = sum(values) / len(values)
        return summary
        
    def log_snapshot(self):
        """Log the current state of metrics to the standard logger."""
        summary = self.get_summary()
        logger.info(f"[METRICS] Counters: {summary['counters']}")
        logger.info(f"[METRICS] Gauges: {summary['gauges']}")
        logger.info(f"[METRICS] Averages: {summary['averages']}")

# Global singleton
metrics = MetricsTracker()

# ── FastAPI Middleware for tracking request latency ────────────────────────────
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi import Request

class MetricsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        
        # Track active requests
        metrics.inc("active_requests", 1)
        metrics.set_gauge("current_active_requests", metrics.counters["active_requests"])
        
        try:
            response = await call_next(request)
            
            # Record latency
            process_time = time.time() - start_time
            metrics.observe("request_duration_seconds", process_time)
            
            # Track HTTP status counts
            metrics.inc(f"http_status_{response.status_code}")
            
            # Specifically track gap analysis requests
            if request.url.path.startswith("/gap-analysis"):
                metrics.inc("gap_analysis_requests")
                metrics.observe("gap_analysis_duration_seconds", process_time)
                
            return response
            
        except Exception as e:
            # Track errors
            metrics.inc("http_500_errors")
            raise e
        finally:
            metrics.inc("active_requests", -1)
            metrics.set_gauge("current_active_requests", metrics.counters["active_requests"])
