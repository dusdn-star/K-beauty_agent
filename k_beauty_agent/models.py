from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

EvidenceLevel = Literal["high", "moderate", "low", "insufficient"]
Decision = Literal["recommend", "fallback", "ask_more", "do_not_recommend"]


@dataclass(frozen=True)
class IngredientEvidence:
    name: str
    aliases: tuple[str, ...]
    supports: tuple[str, ...]
    suitable_for: tuple[str, ...]
    cautions: tuple[str, ...]
    evidence_level: EvidenceLevel
    rationale: str


@dataclass(frozen=True)
class Product:
    id: str
    name: str
    brand: str
    category: str
    country: str
    ingredients: tuple[str, ...]
    claims: tuple[str, ...] = ()
    suited_skin_types: tuple[str, ...] = ()
    concerns: tuple[str, ...] = ()
    avoid_for: tuple[str, ...] = ()
    price_usd: float | None = None
    rating: float | None = None
    review_count: int | None = None
    reviews: tuple[str, ...] = ()
    evidence_notes: tuple[str, ...] = ()
    source_url: str | None = None
    ingredient_source_url: str | None = None
    verified_at: str | None = None
    review_summary: str | None = None

    @classmethod
    def from_mapping(cls, data: dict[str, Any]) -> "Product":
        def tup(key: str) -> tuple[str, ...]:
            value = data.get(key, ())
            if value is None:
                return ()
            if isinstance(value, str):
                return tuple(item.strip() for item in value.replace(";", "|").split("|") if item.strip())
            return tuple(str(item).strip() for item in value if str(item).strip())

        return cls(
            id=str(data["id"]),
            name=str(data["name"]),
            brand=str(data.get("brand", "Unknown")),
            category=str(data.get("category", "unknown")),
            country=str(data.get("country", "Korea")),
            ingredients=tup("ingredients"),
            claims=tup("claims"),
            suited_skin_types=tup("suited_skin_types"),
            concerns=tup("concerns"),
            avoid_for=tup("avoid_for"),
            price_usd=float(data["price_usd"]) if data.get("price_usd") is not None else None,
            rating=float(data["rating"]) if data.get("rating") is not None else None,
            review_count=int(data["review_count"]) if data.get("review_count") is not None else None,
            reviews=tup("reviews"),
            evidence_notes=tup("evidence_notes"),
            source_url=str(data["source_url"]) if data.get("source_url") else None,
            ingredient_source_url=str(data["ingredient_source_url"]) if data.get("ingredient_source_url") else None,
            verified_at=str(data["verified_at"]) if data.get("verified_at") else None,
            review_summary=str(data["review_summary"]) if data.get("review_summary") else None,
        )


@dataclass
class SkinProfile:
    skin_type: str | None = None
    concerns: list[str] = field(default_factory=list)
    desired_categories: list[str] = field(default_factory=list)
    sensitivities: list[str] = field(default_factory=list)
    allergies: list[str] = field(default_factory=list)
    avoid_ingredients: list[str] = field(default_factory=list)
    location_or_climate: str | None = None
    pregnant_or_nursing: bool | None = None
    uncertainty: list[str] = field(default_factory=list)
    follow_up_questions: list[str] = field(default_factory=list)

    @property
    def has_minimum_signal(self) -> bool:
        return bool(self.skin_type or self.concerns or self.desired_categories)


@dataclass
class ProductScore:
    product: Product
    score: float
    score_components: dict[str, float] = field(
        default_factory=lambda: {
            "ingredient_evidence": 0.0,
            "skin_fit": 0.0,
            "category_match": 0.0,
            "review_confidence": 0.0,
            "personalization": 0.0,
            "penalties": 0.0,
        }
    )
    reasons: list[str] = field(default_factory=list)
    cautions: list[str] = field(default_factory=list)
    evidence: list[str] = field(default_factory=list)
    matched_ingredients: list[str] = field(default_factory=list)
    missing_data: list[str] = field(default_factory=list)
    similar_products: list[Product] = field(default_factory=list)


@dataclass
class Recommendation:
    decision: Decision
    query: str
    profile: SkinProfile
    results: list[ProductScore] = field(default_factory=list)
    fallback_message: str | None = None
    review_summary: str | None = None
    guardrails: list[str] = field(default_factory=list)

    def to_text(self) -> str:
        lines: list[str] = []
        if self.decision == "ask_more":
            lines.append("I need a little more information before recommending products.")
            for question in self.profile.follow_up_questions:
                lines.append(f"- {question}")
            return "\n".join(lines)

        if self.fallback_message:
            lines.append(self.fallback_message)

        if self.results:
            lines.append("Recommended options:")
            for index, item in enumerate(self.results, start=1):
                product = item.product
                price = f", ${product.price_usd:.2f}" if product.price_usd is not None else ""
                lines.append(f"{index}. {product.name} by {product.brand} ({product.category}{price})")
                lines.append(f"   Score: {item.score:.1f}")
                lines.append(f"   Why: {'; '.join(item.reasons) or 'No strong reason recorded.'}")
                if item.matched_ingredients:
                    lines.append(f"   Evidence ingredients: {', '.join(item.matched_ingredients)}")
                if item.cautions:
                    lines.append(f"   Cautions: {'; '.join(item.cautions)}")
                if item.missing_data:
                    lines.append(f"   Missing data: {', '.join(item.missing_data)}")

        if self.review_summary:
            lines.append("")
            lines.append("Review summary:")
            lines.append(self.review_summary)

        if self.guardrails:
            lines.append("")
            lines.append("Guardrails:")
            for guardrail in self.guardrails:
                lines.append(f"- {guardrail}")
        return "\n".join(lines)
