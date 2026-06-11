import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from fastapi_app.api import routes
from fastapi_app.schemas import ChatbotRequest, ProductCandidate
from fastapi_app.services.hybrid import HybridRecommender


class HybridRecommenderTest(unittest.TestCase):
    def test_blend_scores_normalize_components(self) -> None:
        recommender = HybridRecommender()
        candidate_ids = [1, 2]

        lstm_scores = {1: 0.1, 2: 0.95}
        graph_scores = {1: 0.2, 2: 0.9}
        rag_scores = {1: 100.0, 2: 1.0}

        blended = recommender.blend_scores(
            candidate_ids=candidate_ids,
            lstm_scores=lstm_scores,
            graph_scores=graph_scores,
            rag_scores=rag_scores,
            strict_intent=False,
        )

        self.assertEqual(blended[0]["product_id"], 2)
        self.assertGreater(blended[0]["score"], blended[1]["score"])

    def test_blend_scores_strict_intent_prioritizes_rag(self) -> None:
        recommender = HybridRecommender()
        candidate_ids = [1, 2]

        lstm_scores = {1: 0.1, 2: 0.95}
        graph_scores = {1: 0.2, 2: 0.9}
        rag_scores = {1: 100.0, 2: 1.0}

        blended = recommender.blend_scores(
            candidate_ids=candidate_ids,
            lstm_scores=lstm_scores,
            graph_scores=graph_scores,
            rag_scores=rag_scores,
            strict_intent=True,
        )

        self.assertEqual(blended[0]["product_id"], 1)


class ChatbotFusionTest(unittest.IsolatedAsyncioTestCase):
    async def test_chatbot_uses_hybrid_fusion_for_user(self) -> None:
        products = [
            ProductCandidate(id=1, name="Laptop A", category_name="laptop", price=19000000, stock=10),
            ProductCandidate(id=2, name="Laptop B", category_name="laptop", price=17000000, stock=8),
            ProductCandidate(id=3, name="Laptop C", category_name="laptop", price=22000000, stock=5),
        ]

        with patch.object(routes.container.rag, "load_products", new=AsyncMock(return_value=products)), patch.object(
            routes.container.rag, "ensure_index", return_value=3
        ), patch.object(
            routes.container.rag,
            "retrieve",
            return_value=[
                {"product_id": 1, "name": "Laptop A", "score": 0.95, "price": 19000000},
                {"product_id": 2, "name": "Laptop B", "score": 0.7, "price": 17000000},
            ],
        ), patch.object(
            routes.container.rag,
            "generate_answer",
            new=AsyncMock(return_value="Bạn có thể tham khảo Laptop A và Laptop B."),
        ), patch.object(
            routes, "_load_behaviors_for_user", return_value=[SimpleNamespace(product_id=2, action="buy", timestamp=0)]
        ), patch.object(
            routes.container.lstm,
            "predict_scores",
            return_value={1: 0.2, 2: 0.9, 3: 0.95},
        ), patch.object(
            routes.container.graph,
            "recommend_scores",
            return_value={1: 0.1, 2: 0.85, 3: 0.9},
        ):
            result = await routes.chatbot(
                ChatbotRequest(
                    query="Tư vấn laptop dưới 20 triệu",
                    user_id=99,
                    top_k=2,
                )
            )

        self.assertEqual(result.recommended_products[0], 1)
        self.assertIn("hybrid_fusion", result.context.get("pipeline", []))
        self.assertTrue(result.context.get("strict_intent"))


if __name__ == "__main__":
    unittest.main()
