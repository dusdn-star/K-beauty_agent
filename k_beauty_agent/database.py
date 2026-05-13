from __future__ import annotations

import csv
import json
from pathlib import Path

from .knowledge_base import find_evidence_for_ingredient, normalize_token
from .models import Product


class ProductDatabase:
    def __init__(self, products: list[Product]):
        self.products = products

    @classmethod
    def from_json(cls, path: str | Path) -> "ProductDatabase":
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(data, list):
            raise ValueError("Product DB must be a JSON array.")
        return cls([Product.from_mapping(item) for item in data])

    @classmethod
    def from_csv(cls, products_path: str | Path, reviews_path: str | Path | None = None) -> "ProductDatabase":
        reviews = _load_review_summaries(reviews_path) if reviews_path else {}
        products: list[Product] = []
        with Path(products_path).open("r", encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                product_id = row.get("id", "")
                review_data = reviews.get(product_id, {})
                merged = {**row, **review_data}
                products.append(Product.from_mapping(_coerce_row(merged)))
        return cls(products)

    def search(
        self,
        query: str = "",
        *,
        categories: list[str] | None = None,
        concerns: list[str] | None = None,
        ingredients: list[str] | None = None,
        limit: int = 20,
    ) -> list[Product]:
        query_tokens = set(normalize_token(query).split())
        category_set = {normalize_token(item) for item in categories or []}
        concern_set = {normalize_token(item) for item in concerns or []}
        ingredient_set = {normalize_token(item) for item in ingredients or []}

        scored: list[tuple[float, Product]] = []
        for product in self.products:
            score = 0.0
            haystack = self._product_text(product)
            product_category = normalize_token(product.category)
            if category_set and "basic" not in category_set and product_category not in category_set:
                continue
            if query_tokens:
                score += sum(1.0 for token in query_tokens if token in haystack)
            if category_set:
                score += 4.0 if product_category in category_set else 0.0
            if concern_set:
                product_concerns = {normalize_token(item) for item in product.concerns}
                score += 2.0 * len(product_concerns & concern_set)
            if ingredient_set:
                product_ingredients = {normalize_token(item) for item in product.ingredients}
                score += 3.0 * sum(
                    1 for ingredient in ingredient_set if _ingredient_in_product(ingredient, product_ingredients)
                )

            if not any((query_tokens, category_set, concern_set, ingredient_set)):
                score = 1.0

            if score > 0:
                scored.append((score, product))

        scored.sort(key=lambda item: (-item[0], item[1].brand.lower(), item[1].name.lower()))
        return [product for _, product in scored[:limit]]

    def get(self, product_id: str) -> Product | None:
        for product in self.products:
            if product.id == product_id:
                return product
        return None

    @staticmethod
    def _product_text(product: Product) -> str:
        values = [
            product.name,
            product.brand,
            product.category,
            *product.ingredients,
            *product.claims,
            *product.suited_skin_types,
            *product.concerns,
        ]
        return normalize_token(" ".join(values))


def _coerce_row(row: dict[str, str]) -> dict[str, object]:
    list_fields = {
        "ingredients",
        "claims",
        "suited_skin_types",
        "concerns",
        "avoid_for",
        "reviews",
        "evidence_notes",
        "texture_tags",
    }
    numeric_fields = {"price_usd", "rating", "review_count", "oliveyoung_price_krw"}
    coerced: dict[str, object] = {}
    for key, value in row.items():
        if value is None:
            continue
        if isinstance(value, tuple):
            coerced[key] = value
            continue
        stripped = value.strip()
        if not stripped:
            continue
        if key in list_fields:
            coerced[key] = tuple(item.strip() for item in stripped.replace(";", "|").split("|") if item.strip())
        elif key in numeric_fields:
            coerced[key] = float(stripped) if key != "review_count" else int(float(stripped))
        else:
            coerced[key] = stripped
    return coerced


def _load_review_summaries(path: str | Path | None) -> dict[str, dict[str, object]]:
    if not path or not Path(path).exists():
        return {}
    summaries: dict[str, dict[str, object]] = {}
    with Path(path).open("r", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            product_id = (row.get("product_id") or "").strip()
            if not product_id:
                continue
            reviews = [
                row.get("summary", ""),
                f"Common positives: {row.get('common_positives', '')}",
                f"Common cautions: {row.get('common_cautions', '')}",
            ]
            summaries[product_id] = {
                "review_summary": row.get("summary", "").strip(),
                "review_summary_en": row.get("summary_en", "").strip(),
                "reviews": tuple(item.strip() for item in reviews if item.strip()),
            }
    return summaries


def _ingredient_in_product(ingredient: str, product_ingredients: set[str]) -> bool:
    wanted_evidence = find_evidence_for_ingredient(ingredient)
    for product_ingredient in product_ingredients:
        product_evidence = find_evidence_for_ingredient(product_ingredient)
        if wanted_evidence and product_evidence and wanted_evidence.name == product_evidence.name:
            return True
        if ingredient in product_ingredient or product_ingredient in ingredient:
            return True
    return False
