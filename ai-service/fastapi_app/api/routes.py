from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import desc

from ..background_tasks import (
    trigger_immediate_update,
    configure_update_mode,
    get_update_config,
)
from ..container import container
from ..database import BehaviorORM, db_manager
from ..schemas import (
    BehaviorIn,
    BehaviorOut,
    ChatbotRequest,
    ChatbotResponse,
    LSTMTrainRequest,
)

router = APIRouter()


def _normalize_action(action: str) -> str:
    act = str(action or "").strip().lower()
    if act in {"view", "click", "add_to_cart", "buy", "rating", "search"}:
        return act
    raise HTTPException(status_code=400, detail="action phải là: view, click, add_to_cart, buy, rating hoặc search")


def _load_behaviors_for_user(user_id: int, limit: int = 500) -> list[BehaviorORM]:
    db = db_manager.get_session()
    try:
        rows = (
            db.query(BehaviorORM)
            .filter(BehaviorORM.user_id == user_id)
            .order_by(desc(BehaviorORM.timestamp))
            .limit(max(1, limit))
            .all()[::-1]
        )
        return rows
    finally:
        db.close()


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/behaviors", response_model=BehaviorOut)
async def create_behavior(payload: BehaviorIn) -> BehaviorOut:
    from ..background_tasks import get_update_config
    
    db = db_manager.get_session()
    try:
        action = _normalize_action(payload.action)
        timestamp = payload.timestamp or datetime.now(timezone.utc)

        item = BehaviorORM(
            user_id=int(payload.user_id),
            product_id=int(payload.product_id),
            action=action,
            timestamp=timestamp,
        )
        db.add(item)
        db.flush()

        graph_result = container.graph.sync_behaviors([item])
        if container.graph.driver and graph_result.get("edges", 0) <= 0:
            raise HTTPException(status_code=503, detail="Không thể ghi hành vi vào Neo4j.")

        db.commit()
        db.refresh(item)

        # Check if immediate model update is needed
        config = get_update_config()
        if config.get("mode") == "immediate":
            trigger_immediate_update(1)

        return BehaviorOut(
            id=item.id,
            user_id=item.user_id,
            product_id=item.product_id,
            action=item.action,
            timestamp=item.timestamp,
        )
    except HTTPException:
        db.rollback()
        raise
    except Exception as ex:
        db.rollback()
        raise HTTPException(status_code=503, detail=f"Không thể lưu hành vi: {str(ex)}")
    finally:
        db.close()


@router.get("/behaviors")
async def list_behaviors(user_id: int | None = None, limit: int = Query(default=200, ge=1, le=5000)) -> dict[str, Any]:
    db = db_manager.get_session()
    try:
        query = db.query(BehaviorORM)
        if user_id is not None:
            query = query.filter(BehaviorORM.user_id == int(user_id))

        rows = query.order_by(desc(BehaviorORM.timestamp)).limit(limit).all()
        data = [
            {
                "id": item.id,
                "user_id": item.user_id,
                "product_id": item.product_id,
                "action": item.action,
                "timestamp": item.timestamp.isoformat(),
            }
            for item in rows
        ]
        return {"count": len(data), "data": data}
    finally:
        db.close()


@router.post("/lstm/train")
async def train_lstm(payload: LSTMTrainRequest) -> dict[str, Any]:
    db = db_manager.get_session()
    try:
        behaviors = db.query(BehaviorORM).order_by(BehaviorORM.user_id, BehaviorORM.timestamp).all()
        return container.lstm.train_from_behaviors(
            behaviors=behaviors,
            epochs=max(1, int(payload.epochs)),
            sequence_length=max(2, int(payload.sequence_length)),
            models=payload.models,
            metric_k=max(1, int(payload.metric_k)),
            save_best=bool(payload.save_best),
        )
    finally:
        db.close()


@router.post("/kg/rebuild")
async def rebuild_knowledge_graph() -> dict[str, Any]:
    db = db_manager.get_session()
    try:
        behaviors = db.query(BehaviorORM).order_by(BehaviorORM.timestamp).all()
        sync_result = container.graph.sync_behaviors(behaviors)
        similar_edges = container.graph.rebuild_similar_edges(behaviors)
        return {
            "message": "Đã rebuild Knowledge Graph thành công.",
            "rows": len(behaviors),
            "graph_sync": sync_result,
            "similar_edges": similar_edges,
        }
    finally:
        db.close()


@router.post("/rag/reindex")
async def rebuild_rag_index(limit: int = 400) -> dict[str, Any]:
    products = await container.rag.load_products(limit=limit)
    count = container.rag.build_faiss_index(products)
    return {"indexed_products": count, "message": "Đã cập nhật FAISS index."}


@router.post("/model/update/immediate")
async def trigger_immediate_model_update() -> dict[str, Any]:
    """Trigger immediate model retraining if threshold is met (immediate mode only)."""
    result = trigger_immediate_update(0)
    return {
        "action": "trigger_immediate_update",
        **result,
    }


@router.post("/model/update/configure")
async def configure_model_updates(
    mode: str = "on-demand",
    batch_interval_hours: int = 6,
    behavior_threshold: int = 10,
) -> dict[str, Any]:
    """
    Configure automatic model update settings.
    
    Args:
        mode: "immediate" (retrain when N behaviors accumulated),
              "batch" (scheduled retraining),
              "on-demand" (manual trigger only)
        batch_interval_hours: Hours between batch retraining (batch mode only)
        behavior_threshold: Behaviors accumulated before retraining (immediate mode only)
    """
    if mode not in ["immediate", "batch", "on-demand"]:
        raise HTTPException(status_code=400, detail="Invalid mode. Use: immediate, batch, or on-demand")
    
    result = configure_update_mode(mode, batch_interval_hours, behavior_threshold)
    return {
        "configured": True,
        **result,
    }


@router.get("/model/update/status")
async def get_model_update_status() -> dict[str, Any]:
    """Get current model update configuration and status."""
    return get_update_config()


@router.get("/recommend", response_model=list[int])
async def recommend(user_id: int, limit: int = 10) -> list[int]:
    behaviors = _load_behaviors_for_user(user_id=user_id, limit=1000)
    products = await container.rag.load_products(limit=400)
    container.rag.ensure_index(products)

    candidate_ids = [item.id for item in products]
    if not candidate_ids:
        return []

    lstm_scores = container.lstm.predict_scores(behaviors, candidate_ids)
    graph_scores = container.graph.recommend_scores(user_id=user_id, candidate_ids=candidate_ids, limit=300)
    rag_scores = {x["product_id"]: x["score"] for x in container.rag.retrieve("", top_k=min(20, len(candidate_ids)))}

    blended = container.hybrid.blend_scores(candidate_ids, lstm_scores, graph_scores, rag_scores)
    top = blended[: max(1, min(limit, 50))]
    return [int(item["product_id"]) for item in top]


@router.get("/recommend/details")
async def recommend_details(user_id: int, query: str = "", limit: int = 10) -> dict[str, Any]:
    behaviors = _load_behaviors_for_user(user_id=user_id, limit=1000)
    products = await container.rag.load_products(limit=400)
    container.rag.ensure_index(products)

    candidate_ids = [item.id for item in products]
    lstm_scores = container.lstm.predict_scores(behaviors, candidate_ids)
    graph_scores = container.graph.recommend_scores(user_id=user_id, candidate_ids=candidate_ids, limit=300)

    rag_hits = container.rag.retrieve(query, top_k=min(50, len(candidate_ids))) if query else []
    rag_scores = {int(hit["product_id"]): float(hit["score"]) for hit in rag_hits}

    blended = container.hybrid.blend_scores(candidate_ids, lstm_scores, graph_scores, rag_scores)
    ranked = blended[: max(1, min(limit, 50))]

    product_map = {item.id: item for item in products}
    data = []
    for item in ranked:
        pid = int(item["product_id"])
        product = product_map.get(pid)
        data.append(
            {
                "id": pid,
                "name": product.name if product else "",
                "category_name": product.category_name if product else "",
                "price": product.price if product else 0.0,
                "stock": product.stock if product else 0,
                "image": product.image if product else "",
                "score": item["score"],
                "components": item["components"],
            }
        )

    return {
        "user_id": user_id,
        "count": len(data),
        "data": data,
        "meta": {
            "pipeline": ["lstm_tensorflow", "knowledge_graph", "rag"],
            "weights": {
                "w1": container.hybrid.w1,
                "w2": container.hybrid.w2,
                "w3": container.hybrid.w3,
            },
            "lstm_last_trained": container.lstm.last_trained_at.isoformat() if container.lstm.last_trained_at else None,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        },
    }


@router.post("/chatbot", response_model=ChatbotResponse)
async def chatbot(payload: ChatbotRequest) -> ChatbotResponse:
    user_id = int(payload.user_id or 0)
    top_k = max(1, min(int(payload.top_k or 5), 10))
    query = str(payload.query or "").strip()
    is_greeting = container.rag._is_greeting_query(query)

    products = await container.rag.load_products(limit=400)
    container.rag.ensure_index(products)
    candidate_ids = [int(item.id) for item in products]
    product_map = {int(item.id): item for item in products}

    if is_greeting:
        answer = await container.rag.generate_answer(query, [])
        return ChatbotResponse(
            answer=answer,
            recommended_products=[],
            context={
                "query": query,
                "user_id": payload.user_id,
                "top_k": top_k,
                "rag_hits": 0,
                "strict_intent": False,
                "is_greeting": True,
                "pipeline": ["greeting"],
            },
        )

    # Extract query constraints
    category_hint = container.rag._extract_query_category_hint(query)
    budget = container.rag._extract_query_budget(query)
    is_under_budget = container.rag._is_under_budget_query(query)
    is_above_budget = container.rag._is_above_budget_query(query)
    is_at_least_budget = container.rag._is_at_least_budget_query(query)
    is_product_info = container.rag._is_product_info_query(query)

    rag_hits = container.rag.retrieve(query, top_k=min(max(20, top_k * 6), 100))
    rag_scores = {int(item["product_id"]): float(item.get("score") or 0.0) for item in rag_hits}
    rag_categories = {int(item["product_id"]): str(item.get("category_name") or "").lower() for item in rag_hits}
    rag_prices = {int(item["product_id"]): float(item.get("price") or 0.0) for item in rag_hits}

    has_strict_intent = any([category_hint, budget, is_product_info])

    if is_product_info and rag_hits:
        recommended = [int(rag_hits[0]["product_id"])]
        answer_context = [rag_hits[0]]
        answer = await container.rag.generate_answer(query, answer_context)
        return ChatbotResponse(
            answer=answer,
            recommended_products=recommended,
            context={
                "query": query,
                "user_id": payload.user_id,
                "top_k": 1,
                "rag_hits": len(rag_hits),
                "strict_intent": True,
                "is_greeting": False,
                "pipeline": ["product_info", "rag_retrieve"],
            },
        )

    recommended = []
    if user_id > 0 and candidate_ids:
        behaviors = _load_behaviors_for_user(user_id=user_id, limit=1000)
        lstm_scores = container.lstm.predict_scores(behaviors, candidate_ids)
        graph_scores = container.graph.recommend_scores(user_id=user_id, candidate_ids=candidate_ids, limit=300)

        fused = container.hybrid.blend_scores(
            candidate_ids=candidate_ids,
            lstm_scores=lstm_scores,
            graph_scores=graph_scores,
            rag_scores=rag_scores,
            strict_intent=has_strict_intent,
        )

        fused_ids = [int(item["product_id"]) for item in fused]

        # Apply category filtering if specified
        if category_hint:
            filtered_by_cat = []
            for pid in fused_ids:
                product = product_map.get(pid)
                if product and (
                    category_hint in str(product.category_name or "").lower()
                    or category_hint in str(product.name or "").lower()
                ):
                    filtered_by_cat.append(pid)

            if filtered_by_cat:
                fused_ids = filtered_by_cat
            # If strict category filter yields nothing, relax it slightly

        # Apply budget filtering if specified
        if budget and is_under_budget:
            filtered_by_budget = [pid for pid in fused_ids if rag_prices.get(pid, 0.0) <= budget]
            if filtered_by_budget:
                fused_ids = filtered_by_budget

        elif budget and (is_above_budget or is_at_least_budget):
            is_strict_above = is_above_budget and not is_at_least_budget
            filtered_by_budget = [
                pid
                for pid in fused_ids
                if (rag_prices.get(pid, 0.0) > budget if is_strict_above else rag_prices.get(pid, 0.0) >= budget)
            ]
            if filtered_by_budget:
                fused_ids = filtered_by_budget

        # If after filtering we have nothing, add RAG-filtered results
        if not fused_ids and rag_hits:
            fused_ids = [int(item["product_id"]) for item in rag_hits]

        recommended = fused_ids[:top_k]

    if not recommended and rag_hits:
        recommended = [int(item["product_id"]) for item in rag_hits[:top_k]]

    if not recommended and products:
        fallback = sorted(
            products,
            key=lambda item: (int(item.stock or 0), -float(item.price or 0.0)),
            reverse=True,
        )
        recommended = [int(item.id) for item in fallback[:top_k]]

    answer_context = []
    for pid in recommended:
        product = product_map.get(int(pid))
        if product is None:
            continue
        answer_context.append(
            {
                "product_id": int(product.id),
                "name": str(product.name or ""),
                "price": float(product.price or 0.0),
                "category_name": str(product.category_name or ""),
                "stock": int(product.stock or 0),
                "image": str(product.image or ""),
            }
        )

    answer = await container.rag.generate_answer(query, answer_context)

    return ChatbotResponse(
        answer=answer,
        recommended_products=recommended,
        context={
            "query": query,
            "user_id": payload.user_id,
            "top_k": top_k,
            "rag_hits": len(rag_hits),
            "strict_intent": has_strict_intent,
            "is_greeting": is_greeting,
            "pipeline": ["retrieve_rag", "score_lstm", "score_graph", "hybrid_fusion", "generate_answer"],
        },
    )


@router.get("/ai/recommendations/{customer_id}/")
async def recommend_compat(customer_id: int, limit: int = 10) -> dict[str, Any]:
    details = await recommend_details(user_id=customer_id, limit=limit)
    return {
        "customer_id": customer_id,
        "count": details.get("count", 0),
        "data": details.get("data", []),
        "meta": details.get("meta", {}),
    }


@router.post("/ai/chat/")
async def chat_compat(payload: dict[str, Any]) -> dict[str, Any]:
    question = str(payload.get("question") or "").strip()
    if not question:
        raise HTTPException(status_code=400, detail="question là bắt buộc")

    top_k = max(1, min(int(payload.get("top_k") or 5), 10))
    customer_id = payload.get("customer_id")

    result = await chatbot(
        ChatbotRequest(
            query=question,
            user_id=customer_id,
            top_k=top_k,
        )
    )

    products = await container.rag.load_products(limit=500)
    product_map = {int(item.id): item for item in products}
    sources: list[dict[str, Any]] = []
    seen_source_keys: set[tuple[str, str]] = set()
    for pid in result.recommended_products[:top_k]:
        product = product_map.get(int(pid))
        if product is None:
            key = ("product", f"product #{int(pid)}")
            if key in seen_source_keys:
                continue
            seen_source_keys.add(key)
            sources.append({"item_id": int(pid), "item_type": "product", "name": f"Product #{int(pid)}"})
            continue

        normalized_type = str(product.category_name or "product").lower()
        normalized_name = str(product.name or "").strip().lower()
        key = (normalized_type, normalized_name)
        if key in seen_source_keys:
            continue
        seen_source_keys.add(key)

        sources.append(
            {
                "item_id": int(product.id),
                "item_type": normalized_type,
                "name": product.name,
                "price": float(product.price or 0.0),
                "stock": int(product.stock or 0),
                "image": str(product.image or ""),
            }
        )

    return {
        "message": "Đã tạo phản hồi chatbot thành công.",
        "model": "hybrid-lstm-tensorflow-graph-rag",
        "answer": result.answer,
        "sources": sources,
        "context_count": len(sources),
    }
