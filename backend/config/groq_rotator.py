"""
Groq API Key Rotator
====================
Wraps multiple Groq API keys and rotates automatically when a
rate-limit (HTTP 429 / 'rate_limit_exceeded') is encountered.

Usage:
    from backend.config.groq_rotator import GroqRotatingClient
    client = GroqRotatingClient(api_keys=["key1", "key2"])
    response = client.chat_completion(model=..., messages=...)

The rotator cycles through keys round-robin. On a 429 it immediately
tries the next key instead of waiting, maximising throughput across
accounts.
"""
from __future__ import annotations

import logging
import itertools
import threading
from typing import List, Any

from openai import OpenAI, RateLimitError

logger = logging.getLogger(__name__)


class GroqRotatingClient:
    """
    Drop-in replacement for the GroqAdapter that rotates API keys
    on rate-limit errors (HTTP 429).

    Thread-safe: key rotation uses a lock so parallel threads don't
    simultaneously advance the iterator.
    """

    GROQ_BASE_URL = "https://api.groq.com/openai/v1"

    def __init__(self, api_keys: List[str]):
        if not api_keys:
            raise ValueError("At least one Groq API key is required")

        # Deduplicate while preserving order
        seen = set()
        unique_keys = [k for k in api_keys if k and not (k in seen or seen.add(k))]  # type: ignore[func-returns-value]

        self._keys = unique_keys
        self._clients = [
            OpenAI(base_url=self.GROQ_BASE_URL, api_key=key)
            for key in unique_keys
        ]
        self._cycle = itertools.cycle(range(len(self._clients)))
        self._current_idx = next(self._cycle)
        self._lock = threading.Lock()

        logger.info(f"[GroqRotator] Initialised with {len(self._clients)} API key(s)")

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _current_client(self) -> OpenAI:
        return self._clients[self._current_idx]

    def _rotate(self) -> OpenAI:
        """Advance to the next key and return the new client."""
        with self._lock:
            self._current_idx = next(self._cycle)
            key_hint = self._keys[self._current_idx][-6:]  # last 6 chars
            logger.warning(
                f"[GroqRotator] Rotated to key #{self._current_idx} "
                f"(…{key_hint})"
            )
        return self._clients[self._current_idx]

    # ── Public interface (matches GroqAdapter / OpenAI-compatible) ─────────────

    def chat_completion(self, model: str, messages: list, **kwargs) -> Any:
        """
        Call chat.completions.create, rotating to the next key on 429.
        Tries every key once before giving up.
        """
        attempts = len(self._clients)
        last_exc: Exception | None = None

        for attempt in range(attempts):
            client = self._current_client() if attempt == 0 else self._rotate()
            try:
                return client.chat.completions.create(
                    model=model,
                    messages=messages,
                    **kwargs,
                )
            except RateLimitError as exc:
                last_exc = exc
                logger.warning(
                    f"[GroqRotator] 429 rate-limit on key #{self._current_idx} "
                    f"(attempt {attempt + 1}/{attempts}): {exc!s:.120}"
                )
                # Rotate and retry immediately
            except Exception as exc:
                # Non-rate-limit errors bubble up immediately
                raise

        # All keys exhausted
        raise last_exc or RuntimeError("All Groq API keys are rate-limited")
