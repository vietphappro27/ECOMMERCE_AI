import unittest

from fastapi_app.schemas import ProductCandidate
from fastapi_app.services.rag import RAGService


class RAGQualityExamplesTest(unittest.TestCase):
    def setUp(self) -> None:
        self.rag = RAGService()
        self.products = [
            ProductCandidate(
                id=1,
                name="Laptop Gaming A",
                category_name="laptop",
                price=19900000,
                stock=10,
                details_text="RTX 4050 RAM 16GB SSD 512GB",
            ),
            ProductCandidate(
                id=2,
                name="Laptop Văn phòng B",
                category_name="laptop",
                price=14900000,
                stock=12,
                details_text="RAM 16GB SSD 512GB màn hình 15 inch",
            ),
            ProductCandidate(
                id=3,
                name="Điện thoại C",
                category_name="mobile",
                price=10900000,
                stock=20,
                details_text="camera 108MP pin 5000mAh",
            ),
        ]
        self.rag.build_faiss_index(self.products)

    def test_greeting_query_returns_no_retrieval(self) -> None:
        hits = self.rag.retrieve("xin chào", top_k=5)
        self.assertEqual(hits, [])

    def test_under_budget_query_filters_results(self) -> None:
        hits = self.rag.retrieve("tư vấn laptop dưới 20 triệu", top_k=5)
        self.assertGreaterEqual(len(hits), 1)
        self.assertTrue(all(float(item.get("price") or 0.0) <= 20_000_000 for item in hits))
        self.assertIn("laptop", str(hits[0].get("category_name") or ""))

    def test_product_info_query_prefers_exact_product(self) -> None:
        hits = self.rag.retrieve("Cho mình thông tin Laptop Gaming A", top_k=5)
        self.assertEqual(len(hits), 1)
        self.assertEqual(int(hits[0]["product_id"]), 1)


if __name__ == "__main__":
    unittest.main()
