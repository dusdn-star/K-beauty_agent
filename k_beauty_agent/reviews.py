from __future__ import annotations

from collections import Counter
import re

from .knowledge_base import normalize_token
from .models import Product

POSITIVE_TERMS = {
    "hydrating",
    "gentle",
    "soothing",
    "lightweight",
    "non-greasy",
    "matte",
    "calming",
    "absorbs",
    "보습",
    "산뜻",
    "진정",
    "순함",
}

NEGATIVE_TERMS = {
    "sticky",
    "irritating",
    "stinging",
    "drying",
    "greasy",
    "fragrance",
    "breakout",
    "따가",
    "건조",
    "끈적",
    "향",
    "트러블",
}


def summarize_reviews(products: list[Product]) -> str:
    snippets = [(product, review) for product in products for review in product.reviews]
    if not snippets:
        return "No review snippets are available in the product DB."

    positive = Counter()
    negative = Counter()
    mentioned_products: Counter[str] = Counter()

    for product, review in snippets:
        normalized = normalize_token(review)
        for term in POSITIVE_TERMS:
            if normalize_token(term) in normalized:
                positive[term] += 1
                mentioned_products[product.name] += 1
        for term in NEGATIVE_TERMS:
            normalized_term = normalize_token(term)
            if normalized_term in normalized and not _is_negated(normalized, normalized_term):
                negative[term] += 1
                mentioned_products[product.name] += 1

    lines = [f"Analyzed {len(snippets)} DB review snippets across {len(products)} product(s)."]
    if positive:
        lines.append("Common positives: " + ", ".join(term for term, _ in positive.most_common(4)) + ".")
    if negative:
        lines.append("Common cautions: " + ", ".join(term for term, _ in negative.most_common(4)) + ".")
    if not positive and not negative:
        lines.append("Reviews did not contain enough known sentiment signals for a reliable summary.")
    return " ".join(lines)


def _is_negated(text: str, term: str) -> bool:
    if re.search(rf"\b(no|not|without|non)\s+(a\s+|an\s+|the\s+)?(too\s+|very\s+)?{re.escape(term)}\b", text):
        return True
    return re.search(rf"\b{re.escape(term)}\s+free\b", text) is not None
