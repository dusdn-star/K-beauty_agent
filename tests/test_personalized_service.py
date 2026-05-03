from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from pathlib import Path

from k_beauty_agent.agent import KBeautyAgent
from k_beauty_agent.database import ProductDatabase
from k_beauty_agent.personalization import build_personalization, merge_profiles, profile_to_dict
from k_beauty_agent.recommender import IngredientHybridRecommender
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

    def test_admin_endpoints_are_protected(self) -> None:
        unauthorized = self.client.get("/api/admin/metrics")
        self.assertEqual(unauthorized.status_code, 401)

        authorized = self.client.get("/api/admin/metrics", headers={"x-admin-token": "test-admin-token"})
        self.assertEqual(authorized.status_code, 200)
        self.assertIn("total_sessions", authorized.json())

    def test_cleanup_endpoint(self) -> None:
        response = self.client.post("/api/admin/cleanup", headers={"x-admin-token": "test-admin-token"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("deleted", response.json())


if __name__ == "__main__":
    unittest.main()
