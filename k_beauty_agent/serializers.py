from __future__ import annotations

from dataclasses import asdict
from typing import Any

from .knowledge_base import normalize_token
from .models import Product, ProductScore, Recommendation, SkinProfile


def product_to_dict(product: Product) -> dict[str, Any]:
    return {
        "id": product.id,
        "name": product.name,
        "brand": product.brand,
        "category": product.category,
        "country": product.country,
        "ingredients": list(product.ingredients),
        "claims": list(product.claims),
        "suited_skin_types": list(product.suited_skin_types),
        "concerns": list(product.concerns),
        "avoid_for": list(product.avoid_for),
        "price_usd": product.price_usd,
        "rating": product.rating,
        "review_count": product.review_count,
        "source_url": product.source_url,
        "ingredient_source_url": product.ingredient_source_url,
        "verified_at": product.verified_at,
        "review_summary": product.review_summary,
    }


def score_to_dict(score: ProductScore) -> dict[str, Any]:
    return {
        "product": product_to_dict(score.product),
        "score": round(score.score, 2),
        "score_components": {key: round(value, 2) for key, value in score.score_components.items()},
        "reasons": score.reasons,
        "cautions": score.cautions,
        "evidence": score.evidence,
        "matched_ingredients": score.matched_ingredients,
        "missing_data": score.missing_data,
        "similar_products": [product_to_dict(product) for product in score.similar_products],
    }


def profile_to_public_dict(profile: SkinProfile) -> dict[str, Any]:
    data = asdict(profile)
    return data


def recommendation_to_dict(
    recommendation: Recommendation,
    *,
    recommendation_id: int | None = None,
    grounded_explanation: str | None = None,
    openai_status: str = "not_used",
) -> dict[str, Any]:
    return {
        "recommendation_id": recommendation_id,
        "decision": recommendation.decision,
        "query": recommendation.query,
        "profile": profile_to_public_dict(recommendation.profile),
        "results": [score_to_dict(item) for item in recommendation.results],
        "fallback_message": recommendation.fallback_message,
        "review_summary": recommendation.review_summary,
        "guardrails": recommendation.guardrails,
        "grounded_explanation": grounded_explanation or recommendation.to_text(),
        "openai_status": openai_status,
    }


def similarity_score(base: Product, candidate: Product) -> float:
    if base.id == candidate.id:
        return -1.0
    score = 0.0
    if normalize_token(base.category) == normalize_token(candidate.category):
        score += 3.0
    base_ingredients = {normalize_token(item) for item in base.ingredients}
    candidate_ingredients = {normalize_token(item) for item in candidate.ingredients}
    base_concerns = {normalize_token(item) for item in base.concerns}
    candidate_concerns = {normalize_token(item) for item in candidate.concerns}
    score += 1.5 * len(base_ingredients & candidate_ingredients)
    score += 2.0 * len(base_concerns & candidate_concerns)
    if normalize_token(base.brand) != normalize_token(candidate.brand):
        score += 0.25
    if candidate.rating:
        score += min(0.5, max(0.0, (candidate.rating - 3.5) / 2.0))
    return score
