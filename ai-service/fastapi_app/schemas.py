from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class BehaviorIn(BaseModel):
    user_id: int
    product_id: int
    action: str = Field(..., description="view | click | add_to_cart | buy | rating | search")
    timestamp: datetime | None = None


class BehaviorOut(BaseModel):
    id: int
    user_id: int
    product_id: int
    action: str
    timestamp: datetime


class LSTMTrainRequest(BaseModel):
    epochs: int = 25
    sequence_length: int = 4
    models: list[str] | None = None
    metric_k: int = 5
    save_best: bool = True


class ChatbotRequest(BaseModel):
    query: str = Field(..., min_length=1)
    user_id: int | None = None
    top_k: int = 5


class ChatbotResponse(BaseModel):
    answer: str
    recommended_products: list[int]
    context: dict[str, Any]


class ProductCandidate(BaseModel):
    id: int
    name: str = ""
    category_name: str = ""
    price: float = 0.0
    stock: int = 0
    image: str = ""
    details_text: str = ""
