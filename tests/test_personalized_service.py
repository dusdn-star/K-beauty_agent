from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from pathlib import Path

from k_beauty_agent.agent import KBeautyAgent
from k_beauty_agent.database import ProductDatabase
from k_beauty_agent.knowledge_base import find_evidence_for_ingredient
from k_beauty_agent.personalization import build_personalization, merge_profiles, profile_to_dict
from k_beauty_agent.recommender import IngredientHybridRecommender
from k_beauty_agent.serializers import product_to_dict
from k_beauty_agent.storage import SQLiteStore

ROOT = Path(__file__).resolve().parents[1]
PRODUCTS_CSV = ROOT / "data" / "products_verified.csv"
REVIEWS_CSV = ROOT / "data" / "review_summaries.csv"


class PersonalizedServiceUnitTest(unittest.TestCase):
    def test_session_profile_merge_prioritizes_recent_query(self) -> None:
        stored = profile_to_dict(merge_profiles(None, "dry skin hydration cream", []))
        merged = merge_profiles(stored, "지성 피부에 맞는 가벼운 토너", ["dry skin hydration cream"])

        self.assertEqual(merged.skin_type, "oily")
        self.assertIn("hydration", merged.concerns)
        self.assertIn("oil_control", merged.concerns)

    def test_follow_up_preference_keeps_context_and_adds_gentle_signals(self) -> None:
        stored = profile_to_dict(merge_profiles(None, "지성 피부에 맞는 기초 제품을 추천해줘", []))
        merged = merge_profiles(stored, "그럼 더 순하고 저렴한 걸로 바꿔줘", ["지성 피부에 맞는 기초 제품을 추천해줘"])

        self.assertEqual(merged.skin_type, "oily")
        self.assertIn("oil_control", merged.concerns)
        self.assertIn("barrier_support", merged.concerns)
        self.assertIn("gentle_preference", merged.sensitivities)
        self.assertIn("budget_preference", merged.sensitivities)
        self.assertEqual(merged.uncertainty, [])

    def test_follow_up_ingredient_and_price_constraints_are_applied(self) -> None:
        agent = KBeautyAgent.from_csv(PRODUCTS_CSV, REVIEWS_CSV)
        first = agent.recommend("지성 피부에 맞는 기초 제품을 추천해줘", limit=3)
        follow_up = agent.recommend(
            "나이아신아마이드 성분 들어간 20달러 이하 제품으로 바꿔줘",
            limit=5,
            stored_profile=profile_to_dict(first.profile),
            recent_queries=["지성 피부에 맞는 기초 제품을 추천해줘"],
        )

        self.assertEqual(follow_up.profile.max_price_usd, 20.0)
        self.assertIn("niacinamide", follow_up.profile.preferred_ingredients)
        self.assertTrue(follow_up.results)
        for item in follow_up.results:
            self.assertIsNotNone(item.product.price_usd)
            self.assertLessEqual(item.product.price_usd, 20.0)
            ingredients = " ".join(item.product.ingredients).lower()
            self.assertIn("niacinamide", ingredients)

    def test_korean_follow_up_variants_are_understood(self) -> None:
        stored = profile_to_dict(merge_profiles(None, "지성 피부에 맞는 기초 제품을 추천해줘", []))
        phrases = [
            "자극 없는 걸로 바꿔줘",
            "가격 낮은 제품으로 다시 추천해줘",
            "비싸지 않고 순한 제품으로 보여줘",
        ]

        merged = merge_profiles(stored, " ".join(phrases), ["지성 피부에 맞는 기초 제품을 추천해줘"])

        self.assertEqual(merged.skin_type, "oily")
        self.assertIn("gentle_preference", merged.sensitivities)
        self.assertIn("budget_preference", merged.sensitivities)
        self.assertIn("barrier_support", merged.concerns)

    def test_quiz_texture_and_krw_budget_are_understood(self) -> None:
        merged = merge_profiles(None, "지성 피부, 선크림 추천, 주요 고민은 유분, 산뜻 제형 선호, 20000원 이하", [])

        self.assertEqual(merged.skin_type, "oily")
        self.assertIn("sunscreen", merged.desired_categories)
        self.assertIn("oil_control", merged.concerns)
        self.assertEqual(merged.texture_preference, "lightweight")
        self.assertEqual(merged.max_price_krw, 20000)

    def test_krw_budget_filters_against_oliveyoung_snapshot_price(self) -> None:
        agent = KBeautyAgent.from_csv(PRODUCTS_CSV, REVIEWS_CSV)
        recommendation = agent.recommend("지성 피부 선크림 유분 산뜻 20000원 이하", limit=5)

        self.assertTrue(recommendation.results)
        for item in recommendation.results:
            self.assertIsNotNone(item.product.oliveyoung_price_krw)
            self.assertLessEqual(item.product.oliveyoung_price_krw, 20000)

    def test_korean_allergy_blocks_matching_ingredient_from_full_ingredient_list(self) -> None:
        agent = KBeautyAgent.from_csv(PRODUCTS_CSV, REVIEWS_CSV)
        recommendation = agent.recommend("지성 피부 선크림 추천, 히알루론산 알러지라 피하고 싶어", limit=5)

        self.assertIn("hyaluronic acid", recommendation.profile.avoid_ingredients)
        self.assertTrue(recommendation.results)
        for item in recommendation.results:
            ingredients = " ".join(item.product.ingredients).lower()
            self.assertNotIn("hyaluronic", ingredients)
            self.assertNotIn("sodium hyaluronate", ingredients)

    def test_allergy_exclusion_removes_matching_products_without_empty_results(self) -> None:
        agent = KBeautyAgent.from_csv(PRODUCTS_CSV, REVIEWS_CSV)
        recommendation = agent.recommend("지성 피부 선크림 추천, 나이아신아마이드 알러지라 피하고 싶어", limit=5)

        self.assertIn("niacinamide", recommendation.profile.avoid_ingredients)
        self.assertTrue(recommendation.results)
        for item in recommendation.results:
            ingredients = " ".join(item.product.ingredients).lower()
            self.assertNotIn("niacinamide", ingredients)

    def test_product_serializer_exposes_commerce_and_ingredient_modal_fields(self) -> None:
        db = ProductDatabase.from_csv(PRODUCTS_CSV, REVIEWS_CSV)
        product = db.get("beauty-of-joseon-relief-sun-rice-probiotics")
        self.assertIsNotNone(product)

        data = product_to_dict(product)

        self.assertIn("image_url", data)
        self.assertIn("display_name_ko", data)
        self.assertEqual(data["display_name_ko"], "조선미녀 맑은쌀 선크림")
        self.assertEqual(data["image_source_type"], "official")
        self.assertEqual(data["image_confidence"], "verified")
        self.assertIn(data["image_view_type"], {"single_product", "verified_product"})
        self.assertTrue(data["image_verified_source"])
        self.assertIn("oliveyoung_url", data)
        self.assertIn("oliveyoung_price_krw", data)
        self.assertIn("official_url", data)
        self.assertIn("review_summary_en", data)
        self.assertTrue(data["review_summary_en"])
        self.assertIn("ingredient_explanations", data)
        self.assertTrue(data["ingredient_explanations"])

    def test_product_image_metadata_policy(self) -> None:
        db = ProductDatabase.from_csv(PRODUCTS_CSV, REVIEWS_CSV)
        source_types = {product.image_source_type for product in db.products}

        self.assertIn("glowpick", source_types)
        for product in db.products:
            image_url = product.image_url or ""
            self.assertNotIn("placehold.co", image_url)
            self.assertNotIn("product-placeholder", image_url)
            self.assertIn(product.image_source_type, {"official", "hwahae", "glowpick", "retailer", "none"})
            self.assertIn(product.image_view_type, {"single_product", "verified_product", "none"})
            if product.image_source_type in {"official", "hwahae", "glowpick", "retailer"}:
                self.assertTrue(product.image_url, product.id)
                self.assertTrue(product.image_verified_source, product.id)
                self.assertEqual(product.image_confidence, "verified", product.id)
                self.assertIn(product.image_view_type, {"single_product", "verified_product"}, product.id)
            if product.image_source_type == "none":
                self.assertIsNone(product.image_url, product.id)
                self.assertIsNone(product.image_verified_source, product.id)
                self.assertIsNone(product.image_confidence, product.id)
                self.assertEqual(product.image_view_type, "none", product.id)

    def test_verified_product_database_quality_floor(self) -> None:
        db = ProductDatabase.from_csv(PRODUCTS_CSV, REVIEWS_CSV)

        self.assertGreaterEqual(len(db.products), 50)
        for product in db.products:
            self.assertTrue(product.id)
            self.assertTrue(product.name)
            self.assertTrue(product.display_name_ko, product.id)
            self.assertTrue(product.ingredients, product.id)
            self.assertTrue(product.category, product.id)
            self.assertTrue(product.concerns, product.id)
            self.assertTrue(product.source_url, product.id)
            self.assertTrue(product.ingredient_source_url, product.id)
            self.assertTrue(product.verified_at, product.id)
            self.assertTrue(product.review_summary, product.id)
            self.assertTrue(product.review_summary_en, product.id)
            self.assertIn(product.image_source_type, {"official", "hwahae", "glowpick", "retailer", "none"})
            self.assertIn(product.image_view_type, {"single_product", "verified_product", "none"})
            if product.image_source_type in {"official", "hwahae", "glowpick", "retailer"}:
                self.assertTrue(product.image_url, product.id)
                self.assertTrue(product.image_verified_source, product.id)
                self.assertEqual(product.image_confidence, "verified", product.id)
                self.assertIn(product.image_view_type, {"single_product", "verified_product"}, product.id)

    def test_expanded_database_returns_depth_by_core_category(self) -> None:
        db = ProductDatabase.from_csv(PRODUCTS_CSV, REVIEWS_CSV)
        categories = ["sunscreen", "serum", "moisturizer", "cleanser", "toner"]

        for category in categories:
            with self.subTest(category=category):
                products = db.search(categories=[category], limit=10)
                self.assertGreaterEqual(len(products), 5)

    def test_allergy_filters_cover_expanded_ingredient_database(self) -> None:
        agent = KBeautyAgent.from_csv(PRODUCTS_CSV, REVIEWS_CSV)
        cases = [
            ("히알루론산 알러지 수분 선크림 추천", ["hyaluronic", "sodium hyaluronate"]),
            ("나이아신아마이드 알러지 수분 세럼 추천", ["niacinamide"]),
            ("달팽이 알러지 수분 세럼 추천", ["snail"]),
            ("티트리 알러지 수분 클렌저 추천", ["tea tree"]),
        ]

        for query, blocked_terms in cases:
            with self.subTest(query=query):
                recommendation = agent.recommend(query, limit=5)
                self.assertTrue(recommendation.results)
                for item in recommendation.results:
                    ingredients = " ".join(item.product.ingredients).lower()
                    for term in blocked_terms:
                        self.assertNotIn(term, ingredients)

    def test_hwahae_image_metadata_serializes_when_public_fallback_exists(self) -> None:
        product = ProductDatabase.from_csv(PRODUCTS_CSV, REVIEWS_CSV).products[0]
        hwahae_product = product.__class__(
            **{
                **product.__dict__,
                "image_url": "https://www.hwahae.co.kr/product-image/example.jpg",
                "image_verified_source": "https://www.hwahae.co.kr/search?q=example",
                "image_source_type": "hwahae",
                "image_confidence": "verified",
                "image_view_type": "single_product",
            }
        )

        data = product_to_dict(hwahae_product)

        self.assertEqual(data["image_source_type"], "hwahae")
        self.assertEqual(data["image_confidence"], "verified")
        self.assertEqual(data["image_view_type"], "single_product")
        self.assertTrue(data["image_url"])
        self.assertTrue(data["image_verified_source"])

    def test_frontend_does_not_use_placeholder_image_fallbacks(self) -> None:
        app_js = (ROOT / "static" / "app.js").read_text(encoding="utf-8")

        self.assertIn("이미지 없음", (ROOT / "static" / "styles.css").read_text(encoding="utf-8"))
        self.assertNotIn("fallbackImage", app_js)
        self.assertNotIn("product-placeholder.svg", app_js)
        self.assertNotIn("placehold.co", app_js)

    def test_frontend_localization_and_compare_auto_update_hooks(self) -> None:
        app_js = (ROOT / "static" / "app.js").read_text(encoding="utf-8")

        self.assertIn("const valueLabels = {", app_js)
        self.assertIn("ko: {", app_js)
        self.assertIn("en: {", app_js)
        self.assertIn('text("compareStandard")', app_js)
        self.assertIn("function reviewSummary(product, emptyKey)", app_js)
        self.assertIn('if (listType === "compare" || !document.querySelector("#compareTable").classList.contains("hidden")) renderCompareTable();', app_js)
        self.assertIn('const LANGUAGE_STORAGE_KEY = "kBeautyAgentLanguage";', app_js)
        self.assertIn("function readStoredLanguage()", app_js)
        self.assertIn("function storeLanguage(lang)", app_js)
        self.assertIn("window.localStorage?.setItem(LANGUAGE_STORAGE_KEY, lang)", app_js)
        self.assertIn("renderCompareSummary();\n  renderCompareTable();\n  renderCatalogs();", app_js)
        self.assertIn("glowpick: text(\"glowpickImage\")", app_js)
        self.assertIn("retailer: text(\"retailerImage\")", app_js)
        self.assertIn("function displayProductName(product)", app_js)
        self.assertIn("function displayIngredient(ingredient)", app_js)
        self.assertIn("function displayIngredients(ingredients, limit = 8)", app_js)
        self.assertIn("displayProductName(product)", app_js)
        self.assertIn("displayIngredients(product.ingredients, 8)", app_js)
        self.assertIn('oliveyoung: "Olive Young"', app_js)
        self.assertIn('official: "브랜드 공식몰"', app_js)
        self.assertIn("const koreanOfficialMallByBrand = {", app_js)
        self.assertIn('COSRX: "https://www.cosrx.co.kr/"', app_js)
        self.assertIn('Anua: "https://www.anua.kr/"', app_js)
        self.assertIn('"Round Lab": "https://roundlab.co.kr/"', app_js)
        self.assertIn('function linkButton(product, type, labelKey)', app_js)
        self.assertIn('function globalOliveYoungUrl(product)', app_js)
        self.assertIn("https://global.oliveyoung.com/display/search?query=${encodeURIComponent(query)}", app_js)
        self.assertIn('if (type === "oliveyoung")', app_js)
        self.assertIn('if (state.lang === "ko") return product.oliveyoung_url || "#";', app_js)
        self.assertIn('if (type === "official")', app_js)
        self.assertIn("return koreanOfficialMall(product) || officialUrl(product.official_url);", app_js)
        self.assertIn("function koreanOfficialMall(product)", app_js)
        self.assertNotIn('productLink(product, "buy")', app_js)
        self.assertGreaterEqual(app_js.count('linkButton(product, "oliveyoung", "oliveyoung")'), 2)
        self.assertGreaterEqual(app_js.count('linkButton(product, "official", "official")'), 2)

    def test_bare_betaine_does_not_match_salicylate(self) -> None:
        self.assertIsNone(find_evidence_for_ingredient("Betaine"))
        evidence = find_evidence_for_ingredient("Betaine Salicylate")
        self.assertIsNotNone(evidence)
        self.assertEqual(evidence.name, "salicylic acid")

    def test_feedback_updates_conservative_personalization(self) -> None:
        db = ProductDatabase.from_csv(PRODUCTS_CSV, REVIEWS_CSV)
        with tempfile.TemporaryDirectory() as tmp:
            store = SQLiteStore(Path(tmp) / "feedback.sqlite3")
            session_id = "test-session"
            store.ensure_session(session_id)
            store.add_feedback(session_id, "product", "liked", product_id="anua-heartleaf-77-soothing-toner")
            signals = build_personalization(db.products, store.feedback_for_session(session_id))

        self.assertIn("anua-heartleaf-77-soothing-toner", signals["liked_products"])
        self.assertIn("toner", signals["liked_categories"])

    def test_safety_exclusions_override_personalization(self) -> None:
        db = ProductDatabase.from_csv(PRODUCTS_CSV, REVIEWS_CSV)
        profile = merge_profiles(None, "snail allergy sensitive serum hydration", [])
        product = db.get("cosrx-advanced-snail-96-mucin-power-essence")
        self.assertIsNotNone(product)
        scored = IngredientHybridRecommender().score_product(
            product,
            profile,
            personalization={"liked_products": {product.id}},
        )

        self.assertLess(scored.score, 0)
        self.assertLess(scored.score_components["penalties"], -50)

    def test_similar_products_and_score_components(self) -> None:
        agent = KBeautyAgent.from_csv(PRODUCTS_CSV, REVIEWS_CSV)
        recommendation = agent.recommend("sensitive skin hydration serum", limit=2)

        self.assertTrue(recommendation.results)
        first = recommendation.results[0]
        self.assertGreaterEqual(len(first.similar_products), 3)
        self.assertLessEqual(len(first.similar_products), 5)
        self.assertAlmostEqual(first.score, sum(first.score_components.values()), places=5)


class PersonalizedServiceApiTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        os.environ["DATABASE_URL"] = f"sqlite:///{Path(self.tempdir.name) / 'service.sqlite3'}"
        os.environ["ADMIN_TOKEN"] = "test-admin-token"
        os.environ.pop("OPENAI_API_KEY", None)
        import k_beauty_agent.web as web

        self.web = importlib.reload(web)
        from fastapi.testclient import TestClient

        self.client = TestClient(self.web.app)

    def test_session_cookie_created_and_reused(self) -> None:
        first = self.client.get("/api/session")
        self.assertEqual(first.status_code, 200)
        cookie = first.cookies.get(self.web.SESSION_COOKIE)
        self.assertTrue(cookie)

        second = self.client.get("/api/session", cookies={self.web.SESSION_COOKIE: cookie})
        self.assertEqual(second.status_code, 200)
        self.assertEqual(first.json()["session_id_hash"], second.json()["session_id_hash"])

    def test_recommend_followup_feedback_and_openai_fallback(self) -> None:
        response = self.client.post(
            "/api/recommend",
            json={"query": "지성 피부에 맞는 기초 제품을 추천해줘", "limit": 3, "use_openai": True},
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["decision"], "recommend")
        self.assertEqual(data["openai_status"], "fallback")
        self.assertTrue(data["results"])
        self.assertIn("score_components", data["results"][0])

        feedback = self.client.post(
            "/api/feedback",
            json={
                "recommendation_id": data["recommendation_id"],
                "target": "product",
                "product_id": data["results"][0]["product"]["id"],
                "feedback": "liked",
                "reason_tags": ["liked_ingredients"],
            },
        )
        self.assertEqual(feedback.status_code, 200)

        follow_up = self.client.post(
            "/api/follow-up",
            json={"query": "make it gentler and fragrance-free", "limit": 3, "use_openai": False},
        )
        self.assertEqual(follow_up.status_code, 200)
        self.assertIn("oil_control", follow_up.text)

    def test_selection_api_tracks_saved_compare_and_total_cost(self) -> None:
        response = self.client.post(
            "/api/selections",
            json={
                "product_id": "beauty-of-joseon-relief-sun-rice-probiotics",
                "list_type": "saved",
                "selected": True,
            },
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["saved_ids"], ["beauty-of-joseon-relief-sun-rice-probiotics"])
        self.assertEqual(data["total_cost_krw"], 18000)

        compare = self.client.post(
            "/api/selections",
            json={
                "product_id": "axis-y-dark-spot-correcting-glow-serum",
                "list_type": "compare",
                "selected": True,
            },
        )
        self.assertEqual(compare.status_code, 200)
        self.assertEqual(compare.json()["compare_ids"], ["axis-y-dark-spot-correcting-glow-serum"])

        cleared = self.client.post(
            "/api/selections",
            json={
                "product_id": "beauty-of-joseon-relief-sun-rice-probiotics",
                "list_type": "saved",
                "selected": False,
            },
        )
        self.assertEqual(cleared.status_code, 200)
        self.assertEqual(cleared.json()["saved_ids"], [])

    def test_korean_language_response_is_localized(self) -> None:
        response = self.client.post(
            "/api/recommend",
            json={
                "query": "지성 피부에 맞는 기초 제품을 추천해줘",
                "limit": 2,
                "use_openai": False,
                "language": "ko",
            },
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertIn("추천 제품", data["grounded_explanation"])
        self.assertIn("추천 이유", data["grounded_explanation"])
        self.assertIn("display_reasons", data["results"][0])
        self.assertTrue(any("피부" in reason or "성분" in reason for reason in data["results"][0]["display_reasons"]))

    def test_english_language_response_uses_source_terms(self) -> None:
        response = self.client.post(
            "/api/recommend",
            json={
                "query": "oily skin sunscreen for oil control",
                "limit": 2,
                "use_openai": False,
                "language": "en",
            },
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertIn("Recommended options", data["grounded_explanation"])
        self.assertIn("review_summary_en", data["results"][0]["product"])
        self.assertTrue(data["results"][0]["product"]["review_summary_en"])
        self.assertIn("display_reasons", data["results"][0])
        self.assertFalse(any("피부" in reason or "성분" in reason for reason in data["results"][0]["display_reasons"]))

    def test_admin_endpoints_are_protected(self) -> None:
        unauthorized = self.client.get("/api/admin/metrics")
        self.assertEqual(unauthorized.status_code, 401)

        authorized = self.client.get("/api/admin/metrics", headers={"x-admin-token": "test-admin-token"})
        self.assertEqual(authorized.status_code, 200)
        self.assertIn("total_sessions", authorized.json())

    def test_compare_and_routine_pages_are_served(self) -> None:
        compare = self.client.get("/compare")
        routine = self.client.get("/routine")

        self.assertEqual(compare.status_code, 200)
        self.assertEqual(routine.status_code, 200)
        self.assertIn("제품 비교", compare.text)
        self.assertIn("개인 루틴", routine.text)

    def test_cleanup_endpoint(self) -> None:
        response = self.client.post("/api/admin/cleanup", headers={"x-admin-token": "test-admin-token"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("deleted", response.json())


if __name__ == "__main__":
    unittest.main()
