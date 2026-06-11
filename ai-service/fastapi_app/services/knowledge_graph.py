from collections import defaultdict

try:
    from neo4j import GraphDatabase
except Exception:  # pragma: no cover
    GraphDatabase = None

from ..config import settings
from ..database import BehaviorORM


class KnowledgeGraphService:
    def __init__(self) -> None:
        self.enabled = settings.neo4j_enabled and GraphDatabase is not None
        self.driver = None

        if self.enabled:
            try:
                self.driver = GraphDatabase.driver(
                    settings.neo4j_uri,
                    auth=(settings.neo4j_username, settings.neo4j_password),
                )
            except Exception:
                self.driver = None

    def close(self) -> None:
        if self.driver:
            self.driver.close()

    @staticmethod
    def _to_edge(action: str) -> str:
        act = str(action).lower()
        if act in {"buy", "add_to_cart", "rating"}:
            return "BUY"
        return "VIEW"

    def sync_behaviors(self, behaviors: list[BehaviorORM]) -> dict[str, int]:
        if not self.driver:
            return {"nodes": 0, "edges": 0}

        rows = [
            {
                "user_id": int(item.user_id),
                "product_id": int(item.product_id),
                "edge": self._to_edge(item.action),
                "action": str(item.action),
                "event_time": item.timestamp.isoformat(),
            }
            for item in behaviors
        ]
        if not rows:
            return {"nodes": 0, "edges": 0}

        query = """
        UNWIND $rows AS row
        MERGE (u:User {id: row.user_id})
        SET u.updated_at = datetime(),
            u.last_behavior_at = datetime(row.event_time)
        MERGE (p:Product {id: row.product_id})
        SET p.updated_at = datetime(),
            p.last_behavior_at = datetime(row.event_time)
        FOREACH(_ IN CASE WHEN row.edge = 'BUY' THEN [1] ELSE [] END |
            MERGE (u)-[b:BUY]->(p)
            SET b.event_count = coalesce(b.event_count, 0) + 1,
                b.last_action = row.action,
                b.last_event_at = datetime(row.event_time),
                b.updated_at = datetime()
        )
        FOREACH(_ IN CASE WHEN row.edge = 'VIEW' THEN [1] ELSE [] END |
            MERGE (u)-[v:VIEW]->(p)
            SET v.event_count = coalesce(v.event_count, 0) + 1,
                v.last_action = row.action,
                v.last_event_at = datetime(row.event_time),
                v.updated_at = datetime()
        )
        """
        with self.driver.session() as session:
            session.run(query, rows=rows)

        return {
            "nodes": len({r["user_id"] for r in rows}) + len({r["product_id"] for r in rows}),
            "edges": len(rows),
        }

    def rebuild_similar_edges(self, behaviors: list[BehaviorORM], max_pairs: int = 4000) -> int:
        if not self.driver:
            return 0

        by_user: dict[int, set[int]] = defaultdict(set)
        for item in behaviors:
            by_user[int(item.user_id)].add(int(item.product_id))

        pair_weight: dict[tuple[int, int], int] = defaultdict(int)
        for products in by_user.values():
            product_list = sorted(products)
            for i in range(len(product_list)):
                for j in range(i + 1, len(product_list)):
                    pair_weight[(product_list[i], product_list[j])] += 1

        rows = [
            {"a": a, "b": b, "score": int(score)}
            for (a, b), score in sorted(pair_weight.items(), key=lambda x: x[1], reverse=True)[:max_pairs]
        ]

        with self.driver.session() as session:
            session.run("MATCH ()-[r:SIMILAR]->() DELETE r")
            if rows:
                session.run(
                    """
                    UNWIND $rows AS row
                    MERGE (p1:Product {id: row.a})
                    MERGE (p2:Product {id: row.b})
                    MERGE (p1)-[s:SIMILAR]->(p2)
                    SET s.score = row.score
                    MERGE (p2)-[s2:SIMILAR]->(p1)
                    SET s2.score = row.score
                    """,
                    rows=rows,
                )

        return len(rows)

    def recommend_scores(self, user_id: int, candidate_ids: list[int], limit: int = 100) -> dict[int, float]:
        if not self.driver or not candidate_ids:
            return {int(pid): 0.0 for pid in candidate_ids}

        query = """
        MATCH (u:User {id: $user_id})-[:BUY|VIEW]->(seen:Product)
        WITH u, collect(seen) AS seen_products
        UNWIND seen_products AS s
        OPTIONAL MATCH (s)-[sim:SIMILAR]->(cand:Product)
        WHERE cand.id IN $candidate_ids AND NOT cand IN seen_products
        WITH u, cand, sum(coalesce(sim.score, 0)) AS similar_score
        OPTIONAL MATCH (u)-[:BUY|VIEW]->(:Product)<-[:BUY|VIEW]-(peer:User)-[:BUY]->(cand)
        WITH cand, similar_score, count(DISTINCT peer) AS peer_score
        RETURN cand.id AS product_id,
               (0.7 * similar_score + 1.8 * peer_score) AS final_score
        ORDER BY final_score DESC
        LIMIT $limit
        """

        out = {int(pid): 0.0 for pid in candidate_ids}
        with self.driver.session() as session:
            rows = session.run(
                query,
                user_id=int(user_id),
                candidate_ids=[int(x) for x in candidate_ids],
                limit=max(1, int(limit)),
            )
            for row in rows:
                product_id = row.get("product_id")
                if product_id is not None:
                    out[int(product_id)] = float(row.get("final_score") or 0.0)

        max_score = max(out.values(), default=1.0) or 1.0
        return {pid: val / max_score for pid, val in out.items()}
