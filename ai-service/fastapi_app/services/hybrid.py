from typing import Any

from ..config import settings


class HybridRecommender:
    def __init__(self) -> None:
        total = settings.weight_lstm + settings.weight_graph + settings.weight_rag
        if total <= 0:
            self.w1, self.w2, self.w3 = 0.45, 0.30, 0.25
        else:
            self.w1 = settings.weight_lstm / total
            self.w2 = settings.weight_graph / total
            self.w3 = settings.weight_rag / total

    @staticmethod
    def _normalize_scores(candidate_ids: list[int], scores: dict[int, float]) -> dict[int, float]:
        values = [float(scores.get(int(pid), 0.0)) for pid in candidate_ids]
        if not values:
            return {}

        low = min(values)
        high = max(values)
        if high <= low:
            if high == 0:
                return {int(pid): 0.0 for pid in candidate_ids}
            return {int(pid): 1.0 for pid in candidate_ids}

        span = high - low
        return {int(pid): (float(scores.get(int(pid), 0.0)) - low) / span for pid in candidate_ids}

    def blend_scores(
        self,
        candidate_ids: list[int],
        lstm_scores: dict[int, float],
        graph_scores: dict[int, float],
        rag_scores: dict[int, float],
        strict_intent: bool = False,
    ) -> list[dict[str, Any]]:
        # Normalize each channel before blending so no source dominates due to scale mismatch.
        n_lstm = self._normalize_scores(candidate_ids, lstm_scores)
        n_graph = self._normalize_scores(candidate_ids, graph_scores)
        n_rag = self._normalize_scores(candidate_ids, rag_scores)

        w1, w2, w3 = self.w1, self.w2, self.w3
        if strict_intent:
            # For explicit query intent (budget/category/spec), favor query relevance from RAG.
            w1 *= 0.5
            w2 *= 0.5
            w3 *= 2.4

        total = w1 + w2 + w3
        if total > 0:
            w1, w2, w3 = w1 / total, w2 / total, w3 / total

        out = []
        for pid in candidate_ids:
            l_score = float(lstm_scores.get(pid, 0.0))
            g_score = float(graph_scores.get(pid, 0.0))
            r_score = float(rag_scores.get(pid, 0.0))

            ln = float(n_lstm.get(pid, 0.0))
            gn = float(n_graph.get(pid, 0.0))
            rn = float(n_rag.get(pid, 0.0))
            final = w1 * ln + w2 * gn + w3 * rn

            out.append(
                {
                    "product_id": int(pid),
                    "score": round(final, 6),
                    "components": {
                        "lstm": round(l_score, 6),
                        "graph": round(g_score, 6),
                        "rag": round(r_score, 6),
                    },
                    "normalized_components": {
                        "lstm": round(ln, 6),
                        "graph": round(gn, 6),
                        "rag": round(rn, 6),
                    },
                }
            )

        out.sort(key=lambda x: x["score"], reverse=True)
        return out
