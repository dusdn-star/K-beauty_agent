from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from .models import Recommendation


class LLMClient(Protocol):
    def complete(self, system: str, user: str) -> str:
        ...


@dataclass
class HybridExplainer:
    """Optional LLM explainer that must stay inside rule-generated evidence."""

    client: LLMClient | None = None

    def explain(self, recommendation: Recommendation, language: str = "en") -> str:
        if self.client is None:
            return recommendation.to_text()

        grounded_context = recommendation.to_text()
        output_language = "Korean" if language.lower().startswith("ko") else "English"
        system = (
            "You are a neutral K-beauty shopping assistant for foreign consumers. "
            "Use only the provided recommendation context. Do not invent products, "
            "reviews, ingredient benefits, rankings, awards, clinical claims, or brand claims. "
            "If evidence is insufficient, say so and ask a follow-up question. "
            "Keep the explanation non-promotional and disclose cautions. "
            f"Write the final answer in {output_language}."
        )
        user = (
            "Rewrite the following grounded recommendation in a clear, concise, explainable way. "
            "Preserve cautions and missing-data notes.\n\n"
            f"{grounded_context}"
        )
        return self.client.complete(system=system, user=user)
