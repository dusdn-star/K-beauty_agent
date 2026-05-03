from __future__ import annotations

import os
import time

from .config import openai_model
from .storage import SQLiteStore


class OpenAIResponsesClient:
    def __init__(self, store: SQLiteStore | None = None, session_id: str | None = None, model: str | None = None):
        self.store = store
        self.session_id = session_id
        self.model = model or openai_model()

    def complete(self, system: str, user: str) -> str:
        if not os.getenv("OPENAI_API_KEY"):
            self._record("skipped", 0, "OPENAI_API_KEY is not configured")
            raise RuntimeError("OPENAI_API_KEY is not configured")
        started = time.perf_counter()
        try:
            from openai import OpenAI

            client = OpenAI(timeout=12.0)
            response = client.responses.create(
                model=self.model,
                instructions=system,
                input=user,
                store=False,
                max_output_tokens=700,
            )
            latency_ms = int((time.perf_counter() - started) * 1000)
            self._record("ok", latency_ms)
            return response.output_text
        except Exception as exc:  # pragma: no cover - depends on external service
            latency_ms = int((time.perf_counter() - started) * 1000)
            self._record("error", latency_ms, str(exc)[:500])
            raise

    def _record(self, status: str, latency_ms: int, error: str | None = None) -> None:
        if self.store:
            self.store.record_openai_call(self.session_id, self.model, status, latency_ms, error)
