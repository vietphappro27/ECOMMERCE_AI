import hashlib
import re
from typing import Any

import faiss
import httpx
import numpy as np

from ..config import settings
from ..schemas import ProductCandidate


class RAGService:
    def __init__(self) -> None:
        self.dim = settings.rag_embed_dim
        self.index = faiss.IndexFlatIP(self.dim)
        self.product_ids: list[int] = []
        self.product_names: list[str] = []
        self.product_texts: list[str] = []
        self.product_categories: list[str] = []
        self.product_prices: list[float] = []
        self.product_stocks: list[int] = []
        self.product_images: list[str] = []
        self._index_fingerprint: str = ""

    def _tokenize(self, text: str) -> list[str]:
        cleaned = re.sub(r"[^\w\s]", " ", str(text or "").lower(), flags=re.UNICODE)
        tokens = [tok for tok in cleaned.split() if tok]
        return tokens

    def _normalize_text(self, text: str) -> str:
        return " ".join(self._tokenize(text))

    def _name_match_score(self, query: str, name: str) -> float:
        query_norm = self._normalize_text(query)
        name_norm = self._normalize_text(name)
        if not query_norm or not name_norm:
            return 0.0

        if name_norm in query_norm:
            return 1.0

        name_tokens = [tok for tok in name_norm.split() if len(tok) > 2]
        if not name_tokens:
            return 0.0

        hits = sum(1 for tok in name_tokens if tok in query_norm)
        return hits / max(1, len(name_tokens))

    def _embed_text(self, text: str) -> np.ndarray:
        tokens = self._tokenize(text)
        vec = np.zeros(self.dim, dtype=np.float32)
        if not tokens:
            return vec

        for token in tokens:
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            idx = int.from_bytes(digest[:4], byteorder="little", signed=False) % self.dim
            weight = 1.0 + (len(token) / 10.0)
            vec[idx] += weight

        norm = np.linalg.norm(vec)
        return vec if norm == 0 else vec / norm

    def _extract_query_budget(self, query: str) -> float | None:
        q = str(query or "").lower()
        million_match = re.search(r"(\d+(?:[\.,]\d+)?)\s*(trieu|triệu|m|cu|củ)", q)
        if million_match:
            num = float(million_match.group(1).replace(",", "."))
            return num * 1_000_000.0

        raw_match = re.search(r"(\d{2,})", q)
        if raw_match:
            try:
                return float(raw_match.group(1))
            except Exception:
                return None
        return None

    def _is_under_budget_query(self, query: str) -> bool:
        q = str(query or "").lower()
        return any(
            tok in q
            for tok in [
                "duoi",
                "dưới",
                "under",
                "<",
                "<=",
                "khong qua",
                "không quá",
                "toi da",
                "tối đa",
                "max",
            ]
        )

    def _is_above_budget_query(self, query: str) -> bool:
        q = str(query or "").lower()
        return any(
            tok in q
            for tok in [
                "tren",
                "trên",
                "over",
                ">",
                "lon hon",
                "lớn hơn",
                "cao hon",
                "cao hơn",
            ]
        )

    def _is_at_least_budget_query(self, query: str) -> bool:
        q = str(query or "").lower()
        return any(
            tok in q
            for tok in [
                ">=",
                "it nhat",
                "ít nhất",
                "min",
            ]
        )

    def _is_product_info_query(self, query: str) -> bool:
        q = str(query or "").lower()
        return any(
            tok in q
            for tok in [
                "thong tin",
                "thông tin",
                "chi tiet",
                "chi tiết",
                "cau hinh",
                "cấu hình",
                "review",
                "gia",
                "giá",
                "bao nhieu",
                "bao nhiêu",
                "price",
                "cost",
                "how much",
            ]
        )

    def _is_greeting_query(self, query: str) -> bool:
        q = str(query or "").strip().lower()
        if not q:
            return True

        greeting_phrases = {
            "hello",
            "hi",
            "hey",
            "alo",
            "xin chao",
            "xin chào",
            "chao",
            "chào",
            "good morning",
            "good afternoon",
            "good evening",
        }
        if q in greeting_phrases:
            return True

        tokens = self._tokenize(q)
        if len(tokens) <= 3 and any(tok in greeting_phrases for tok in tokens):
            return True
        return False

    def _extract_query_category_hint(self, query: str) -> str | None:
        q = str(query or "").lower()
        if any(tok in q for tok in ["laptop", "notebook", "gaming"]):
            return "laptop"
        if any(tok in q for tok in ["mobile", "phone", "điện thoại", "dien thoai", "smartphone", "iphone"]):
            return "mobile"
        if any(tok in q for tok in ["book", "sach", "sách", "truyen", "truyện", "tieu thuyet", "tiểu thuyết"]):
            return "book"
        if any(tok in q for tok in ["quần áo", "quan ao", "thời trang", "thoi trang", "fashion", "áo", "ao", "thun"]):
            return "quan ao"
        return None

    async def load_products(self, limit: int = 300) -> list[ProductCandidate]:
        url = f"{settings.product_service_url}/products/?limit={limit}"
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url)
                response.raise_for_status()
                payload = response.json()
        except Exception:
            # Must rely on product-service as the single source of truth.
            return []

        items = payload.get("data") if isinstance(payload, dict) else []
        if not isinstance(items, list):
            items = []

        out: list[ProductCandidate] = []
        for item in items:
            if not isinstance(item, dict) or item.get("id") is None:
                continue

            try:
                product_id = int(item.get("id"))
                price = float(item.get("price") or 0.0)
                stock = int(item.get("stock") or 0)
            except Exception:
                continue

            details = item.get("product_details") if isinstance(item.get("product_details"), dict) else {}
            details_text = " ".join(str(v) for v in details.values() if v not in (None, ""))

            out.append(
                ProductCandidate(
                    id=product_id,
                    name=str(item.get("name") or ""),
                    category_name=str(item.get("category_name") or ""),
                    price=price,
                    stock=stock,
                    image=str(item.get("image") or ""),
                    details_text=details_text,
                )
            )

        return out

    def build_faiss_index(self, products: list[ProductCandidate]) -> int:
        self.index = faiss.IndexFlatIP(self.dim)
        self.product_ids = []
        self.product_names = []
        self.product_texts = []
        self.product_categories = []
        self.product_prices = []
        self.product_stocks = []
        self.product_images = []

        vectors = []
        for product in products:
            text = f"{product.name} {product.category_name} {product.details_text}"
            vectors.append(self._embed_text(text))
            self.product_ids.append(int(product.id))
            self.product_names.append(product.name)
            self.product_texts.append(text)
            self.product_categories.append(str(product.category_name or "").lower())
            self.product_prices.append(float(product.price or 0.0))
            self.product_stocks.append(int(product.stock or 0))
            self.product_images.append(str(product.image or ""))

        if vectors:
            self.index.add(np.stack(vectors).astype(np.float32))
        self._index_fingerprint = self._compute_fingerprint(products)
        return len(vectors)

    def _compute_fingerprint(self, products: list[ProductCandidate]) -> str:
        parts: list[str] = []
        for product in sorted(products, key=lambda x: int(x.id)):
            parts.append(
                f"{int(product.id)}|{str(product.name)}|{str(product.category_name)}|{float(product.price or 0.0)}|{int(product.stock or 0)}|{str(product.image or '')}"
            )
        joined = "\n".join(parts)
        return hashlib.sha256(joined.encode("utf-8")).hexdigest()

    def ensure_index(self, products: list[ProductCandidate], force: bool = False) -> int:
        if force:
            return self.build_faiss_index(products)

        fingerprint = self._compute_fingerprint(products)
        if self.index.ntotal == 0 or fingerprint != self._index_fingerprint:
            return self.build_faiss_index(products)
        return self.index.ntotal

    def retrieve(self, query: str, top_k: int = 5) -> list[dict[str, Any]]:
        if self.index.ntotal == 0:
            return []

        if self._is_greeting_query(query):
            return []

        is_product_info_query = self._is_product_info_query(query)
        if is_product_info_query:
            matches = []
            for idx, name in enumerate(self.product_names):
                score = self._name_match_score(query, name)
                if score <= 0:
                    continue
                matches.append((score, idx))

            if matches:
                matches.sort(key=lambda x: x[0], reverse=True)
                out = []
                for score, idx in matches[: max(1, top_k)]:
                    out.append(
                        {
                            "product_id": self.product_ids[idx],
                            "name": self.product_names[idx],
                            "text": self.product_texts[idx],
                            "category_name": self.product_categories[idx],
                            "price": self.product_prices[idx],
                            "stock": self.product_stocks[idx],
                            "image": self.product_images[idx] if idx < len(self.product_images) else "",
                            "score": float(score) + 2.0,
                        }
                    )
                return out

        q = self._embed_text(query).reshape(1, -1)
        query_lower = str(query or "").lower()
        budget = self._extract_query_budget(query)
        category_hint = self._extract_query_category_hint(query)
        is_under_budget_query = self._is_under_budget_query(query)
        is_above_budget_query = self._is_above_budget_query(query)
        is_at_least_budget_query = self._is_at_least_budget_query(query)
        query_tokens = set(self._tokenize(query))

        should_expand_candidates = bool(category_hint) or bool(budget and (is_under_budget_query or is_above_budget_query or is_at_least_budget_query)) or is_product_info_query
        search_pairs: list[tuple[float, int]] = []

        if should_expand_candidates:
            for idx in range(len(self.product_ids)):
                search_pairs.append((0.0, idx))
        else:
            # Retrieve a wider candidate set first, then apply heuristics.
            search_k = max(10, top_k * 4)
            search_k = min(search_k, max(1, self.index.ntotal))
            scores, idxs = self.index.search(q, search_k)
            search_pairs.extend((float(score), int(idx)) for score, idx in zip(scores[0], idxs[0]))

        out = []
        for score, idx in search_pairs:
            if idx < 0 or idx >= len(self.product_ids):
                continue

            cat = self.product_categories[idx] if idx < len(self.product_categories) else ""
            price = self.product_prices[idx] if idx < len(self.product_prices) else 0.0
            stock = self.product_stocks[idx] if idx < len(self.product_stocks) else 0
            image = self.product_images[idx] if idx < len(self.product_images) else ""
            text = self.product_texts[idx]
            name = self.product_names[idx]
            name_lower = str(name or "").lower()

            lexical_bonus = 0.0
            if query_tokens:
                text_tokens = set(self._tokenize(text))
                overlap = len(query_tokens.intersection(text_tokens))
                lexical_bonus += overlap * 0.05

            if name_lower and name_lower in query_lower:
                lexical_bonus += 1.2
            elif query_tokens and name_lower:
                name_tokens = set(self._tokenize(name_lower))
                if name_tokens:
                    name_overlap = len(query_tokens.intersection(name_tokens)) / max(1, len(name_tokens))
                    lexical_bonus += name_overlap * 0.5

            if is_product_info_query and name_lower and name_lower in query_lower:
                lexical_bonus += 1.0

            if category_hint:
                if category_hint in cat or category_hint in text.lower():
                    lexical_bonus += 0.6
                else:
                    lexical_bonus -= 0.3

            if budget and price > 0:
                if is_under_budget_query:
                    if price <= budget:
                        lexical_bonus += 0.35
                        # Prefer items close to the max budget (typically better value in same budget).
                        budget_distance = abs(price - budget) / max(budget, 1.0)
                        lexical_bonus += max(0.0, 1.0 - min(1.0, budget_distance)) * 0.2
                    else:
                        lexical_bonus -= 0.7
                elif is_above_budget_query or is_at_least_budget_query:
                    budget_passed = price > budget if is_above_budget_query and not is_at_least_budget_query else price >= budget
                    if budget_passed:
                        lexical_bonus += 0.35
                        budget_distance = abs(price - budget) / max(budget, 1.0)
                        lexical_bonus += max(0.0, 1.0 - min(1.0, budget_distance)) * 0.25
                    else:
                        lexical_bonus -= 0.7

            out.append(
                {
                    "product_id": self.product_ids[idx],
                    "name": name,
                    "text": text,
                    "category_name": cat,
                    "price": price,
                    "stock": stock,
                    "image": image,
                    "score": float(score) + lexical_bonus,
                }
            )

        # Enforce query intent first: filter by category and budget when explicitly mentioned.
        filtered = out
        if category_hint:
            by_cat = [
                item
                for item in filtered
                if category_hint in str(item.get("category_name") or "")
                or category_hint in str(item.get("text") or "").lower()
            ]
            if by_cat:
                filtered = by_cat

        if budget and is_under_budget_query:
            by_budget = [
                item for item in filtered if float(item.get("price") or 0.0) > 0 and float(item.get("price") or 0.0) <= float(budget)
            ]
            filtered = by_budget

        if budget and (is_above_budget_query or is_at_least_budget_query):
            by_budget = [
                item
                for item in filtered
                if float(item.get("price") or 0.0) > 0
                and (
                    float(item.get("price") or 0.0) > float(budget)
                    if is_above_budget_query and not is_at_least_budget_query
                    else float(item.get("price") or 0.0) >= float(budget)
                )
            ]
            filtered = by_budget

        if budget and is_under_budget_query:
            filtered.sort(
                key=lambda x: (float(x.get("price") or 0.0), float(x.get("score") or 0.0)),
                reverse=True,
            )
        elif budget and (is_above_budget_query or is_at_least_budget_query):
            filtered.sort(key=lambda x: (abs(float(x.get("price") or 0.0) - float(budget)), -float(x.get("score") or 0.0)))
        else:
            filtered.sort(key=lambda x: float(x.get("score") or 0.0), reverse=True)

        if is_product_info_query and filtered:
            exact_name_hits = [
                item for item in filtered if str(item.get("name") or "").strip().lower() in query_lower
            ]
            filtered = exact_name_hits or filtered

        dedup = []
        seen = set()
        for item in filtered:
            pid = int(item.get("product_id") or 0)
            normalized_key = (
                str(item.get("name") or "").strip().lower(),
                str(item.get("category_name") or "").strip().lower(),
            )
            if pid <= 0 or normalized_key in seen:
                continue
            seen.add(normalized_key)
            dedup.append(item)
            if len(dedup) >= max(1, top_k):
                break

        if is_product_info_query and dedup:
            return dedup[:1]

        return dedup

    async def generate_answer(self, query: str, retrieved: list[dict[str, Any]]) -> str:
        if self._is_greeting_query(query):
            if retrieved:
                categories = []
                seen = set()
                for item in retrieved:
                    cat = str(item.get("category_name") or "").strip()
                    if not cat:
                        continue
                    key = cat.lower()
                    if key in seen:
                        continue
                    seen.add(key)
                    categories.append(cat)
                    if len(categories) >= 3:
                        break
                if categories:
                    cat_text = ", ".join(categories)
                    return f"Xin chào! Hiện tại tôi có các sản phẩm ở danh mục: {cat_text}. Bạn quan tâm sản phẩm nào?"
            return "Xin chào! Tôi là Nova Assistant. Bạn cần tư vấn mua sản phẩm nào không? Tôi có thể giúp bạn tìm theo loại, giá tiền hoặc đặc tính sản phẩm."

        if not retrieved:
            return "Mình chưa tìm thấy sản phẩm phù hợp với yêu cầu của bạn. Bạn có thể mô tả rõ hơn hoặc thử tìm kiếm với từ khóa khác nhé!"

        if self._is_product_info_query(query):
            product = retrieved[0]
            name = str(product.get("name") or "Sản phẩm")
            price = float(product.get("price") or 0.0)
            category = str(product.get("category_name") or "chưa xác định")
            stock = int(product.get("stock") or 0)
            stock_status = "Còn hàng" if stock > 0 else "Hết hàng"
            return (
                f"Thông tin sản phẩm {name}:\n"
                f"- Danh mục: {category}\n"
                f"- Giá: {price:,.0f} VND\n"
                f"- Tình trạng: {stock_status} ({stock} cái)\n"
                "Bạn muốn biết thêm chi tiết hoặc xem sản phẩm tương tự không?"
            )

        # Build detailed product context
        context_lines = []
        for r in retrieved[:6]:
            name = str(r.get("name") or "")
            price = float(r.get("price") or 0.0)
            category = str(r.get("category_name") or "")
            if name:
                context_lines.append(f"- {name} ({category}): {price:,.0f} VND")

        # Check if user is asking about budget
        budget = self._extract_query_budget(query)
        budget_context = ""
        if budget:
            if self._is_under_budget_query(query):
                budget_context = f"(dưới {budget:,.0f} VND)"
            elif self._is_above_budget_query(query) or self._is_at_least_budget_query(query):
                budget_context = f"(từ {budget:,.0f} VND trở lên)"

        category_hint = self._extract_query_category_hint(query)
        category_context = f"({category_hint})" if category_hint else ""

        # Build an improved prompt
        prompt = (
            "Bạn là trợ lý mua sắm thân thiện và chuyên nghiệp của cửa hàng Nova.\n"
            "Hãy trả lời ngắn gọn, tự nhiên, có dấu tiếng Việt, phù hợp với nhu cầu người dùng.\n"
            f"\nCâu hỏi: {query}\n"
            f"Yêu cầu tìm: {category_context} {budget_context}\n"
            "\nSản phẩm gợi ý:\n"
            + "\n".join(context_lines)
            + "\n\nHướng dẫn:\n"
            + "1. Gợi ý 2-3 sản phẩm phù hợp nhất, kèm lý do ngắn gọn tại sao phù hợp.\n"
            + "2. Nếu có nhiều lựa chọn, hãy so sánh giá hoặc chất lượng.\n"
            + "3. Nếu người dùng hỏi về sẵn có, hãy cho biết tình trạng hàng.\n"
            + "4. Lời mời bạn đặt hàng hoặc hỏi thêm chi tiết nếu cần.\n"
            + "5. Không nhắc đến hệ thống kỹ thuật nội bộ.\n"
            + "Trả lời:"
        )

        if settings.ollama_base_url:
            try:
                payload = {"model": settings.ollama_model, "prompt": prompt, "stream": False, "temperature": 0.6}
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.post(f"{settings.ollama_base_url}/api/generate", json=payload)
                    response.raise_for_status()
                    body = response.json()
                text = str(body.get("response") or "").strip()
                if text:
                    return text
            except Exception:
                pass

        # Fallback response when LLM is not available
        unique_names: list[str] = []
        seen_names = set()
        for item in retrieved:
            name = str(item.get("name") or "").strip()
            if not name:
                continue
            lowered = name.lower()
            if lowered in seen_names:
                continue
            seen_names.add(lowered)
            unique_names.append(name)
            if len(unique_names) >= 3:
                break

        if unique_names:
            return f"Bạn có thể tham khảo các sản phẩm sau:\n{', '.join(unique_names)}. Nếu muốn, tôi có thể gợi ý theo ngân sách hoặc danh mục cụ thể hơn."
        return "Mình chưa tìm thấy sản phẩm phù hợp. Bạn có thể thử lại với từ khóa khác không?"
