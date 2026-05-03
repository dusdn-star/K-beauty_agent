from __future__ import annotations

from dataclasses import asdict
from typing import Any

from .knowledge_base import normalize_token
from .models import Product, SkinProfile
from .skin import analyze_skin_query


PROFILE_LIST_FIELDS = (
    "concerns",
    "desired_categories",
    "sensitivities",
    "allergies",
    "avoid_ingredients",
)


def profile_to_dict(profile: SkinProfile) -> dict[str, Any]:
    data = asdict(profile)
    data.pop("uncertainty", None)
    data.pop("follow_up_questions", None)
    return data


def profile_from_dict(data: dict[str, Any] | None) -> SkinProfile:
    if not data:
        return SkinProfile()
    return SkinProfile(
        skin_type=data.get("skin_type"),
        concerns=list(data.get("concerns") or []),
        desired_categories=list(data.get("desired_categories") or []),
        sensitivities=list(data.get("sensitivities") or []),
        allergies=list(data.get("allergies") or []),
        avoid_ingredients=list(data.get("avoid_ingredients") or []),
        location_or_climate=data.get("location_or_climate"),
        pregnant_or_nursing=data.get("pregnant_or_nursing"),
    )


def merge_profiles(stored: dict[str, Any] | None, query: str, recent_queries: list[str] | None = None) -> SkinProfile:
    merged = profile_from_dict(stored)
    recent_text = " ".join((recent_queries or [])[-5:])
    recent_profile = analyze_skin_query(recent_text) if recent_text else SkinProfile()
    query_profile = analyze_skin_query(query)

    for profile in (recent_profile, query_profile):
        if profile.skin_type:
            merged.skin_type = profile.skin_type
        if profile.pregnant_or_nursing is not None:
            merged.pregnant_or_nursing = profile.pregnant_or_nursing
        for field in PROFILE_LIST_FIELDS:
            _extend_unique(getattr(merged, field), getattr(profile, field))

    if query_profile.location_or_climate:
        merged.location_or_climate = query_profile.location_or_climate
    merged.uncertainty = query_profile.uncertainty
    merged.follow_up_questions = query_profile.follow_up_questions
    return merged


def build_personalization(products: list[Product], feedback_rows: list[dict[str, Any]]) -> dict[str, set[str]]:
    by_id = {product.id: product for product in products}
    signals: dict[str, set[str]] = {
        "liked_products": set(),
        "disliked_products": set(),
        "liked_brands": set(),
        "disliked_brands": set(),
        "liked_ingredients": set(),
        "disliked_ingredients": set(),
        "liked_concerns": set(),
        "disliked_concerns": set(),
        "liked_categories": set(),
        "disliked_categories": set(),
    }
    for row in feedback_rows:
        product_id = row.get("product_id")
        product = by_id.get(product_id or "")
        if not product:
            continue
        prefix = "liked" if row.get("feedback") == "liked" else "disliked"
        signals[f"{prefix}_products"].add(product.id)
        signals[f"{prefix}_brands"].add(normalize_token(product.brand))
        signals[f"{prefix}_categories"].add(normalize_token(product.category))
        signals[f"{prefix}_ingredients"].update(normalize_token(item) for item in product.ingredients)
        signals[f"{prefix}_concerns"].update(normalize_token(item) for item in product.concerns)
    return signals


def _extend_unique(target: list[str], values: list[str]) -> None:
    seen = set(target)
    for value in values:
        if value not in seen:
            target.append(value)
            seen.add(value)
