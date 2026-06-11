import math
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

from ..database import BehaviorORM


def _get_tf():
    try:
        import tensorflow as tf  # type: ignore
        return tf
    except Exception:  # pragma: no cover
        return None


class LSTMTrainerTF:
    ACTION_WEIGHT = {
        "view": 0.35,
        "click": 0.65,
        "add_to_cart": 1.0,
        "buy": 1.2,
        "rating": 0.9,
        "search": 0.2,
    }

    def __init__(self) -> None:
        self.model = None
        self.model_name: str | None = None
        self.model_metrics: dict[str, float] = {}
        self.product_to_idx: dict[int, int] = {}
        self.idx_to_product: dict[int, int] = {}
        self.sequence_length = 4
        self.input_dim = 10
        self.last_trained_at: datetime | None = None
        self.artifacts_dir = Path(__file__).resolve().parent.parent / "artifacts"

    def _event_vector(self, product_id: int, action: str, ts: datetime) -> list[float]:
        weight = self.ACTION_WEIGHT.get(action, 0.1)
        vals = [((product_id * (i + 5)) % 97) / 96.0 for i in range(self.input_dim)]
        vals[0] = min(1.0, vals[0] * weight)

        now = datetime.now(timezone.utc)
        days_ago = max((now - ts).total_seconds() / 86400.0, 0.0)
        vals[1] = math.exp(-days_ago / 14.0)
        return vals

    def _build_model(self, tf: Any, model_type: str, output_dim: int, metric_k: int) -> Any:
        if model_type == "rnn":
            encoder = tf.keras.layers.SimpleRNN(64)
        elif model_type == "bilstm":
            encoder = tf.keras.layers.Bidirectional(tf.keras.layers.LSTM(64))
        else:
            encoder = tf.keras.layers.LSTM(64)

        model = tf.keras.Sequential(
            [
                tf.keras.layers.Input(shape=(self.sequence_length, self.input_dim)),
                encoder,
                tf.keras.layers.Dense(output_dim, activation="softmax"),
            ]
        )
        model.compile(
            optimizer=tf.keras.optimizers.Adam(learning_rate=0.01),
            loss="sparse_categorical_crossentropy",
            metrics=[
                tf.keras.metrics.SparseCategoricalAccuracy(name="accuracy"),
                tf.keras.metrics.SparseTopKCategoricalAccuracy(k=metric_k, name=f"top_{metric_k}_accuracy"),
            ],
        )
        return model

    def _split_train_val(self, x: np.ndarray, y: np.ndarray, ratio: float = 0.2) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        rng = np.random.default_rng(42)
        indices = rng.permutation(len(x))
        val_size = max(1, int(len(x) * ratio))
        val_idx = indices[:val_size]
        train_idx = indices[val_size:]
        return x[train_idx], y[train_idx], x[val_idx], y[val_idx]

    def _evaluate_model(self, model: Any, x_val: np.ndarray, y_val: np.ndarray, metric_k: int) -> dict[str, float]:
        if len(x_val) == 0:
            return {}

        eval_metrics = model.evaluate(x_val, y_val, verbose=0, return_dict=True)
        preds = model.predict(x_val, verbose=0)

        top1 = np.argmax(preds, axis=1)
        accuracy = float(np.mean(top1 == y_val))

        topk = np.argsort(preds, axis=1)[:, -metric_k:]
        hits = np.any(topk == y_val[:, None], axis=1)
        hit_rate = float(np.mean(hits))
        precision_at_k = hit_rate / float(metric_k)
        recall_at_k = hit_rate

        ndcg_scores = []
        for row, target in zip(topk, y_val, strict=False):
            if target in row:
                rank = list(reversed(row)).index(int(target)) + 1
                ndcg_scores.append(1.0 / math.log2(rank + 1))
            else:
                ndcg_scores.append(0.0)

        return {
            "val_loss": float(eval_metrics.get("loss", 0.0)),
            "val_accuracy": float(eval_metrics.get("accuracy", accuracy)),
            f"val_top_{metric_k}_accuracy": float(eval_metrics.get(f"top_{metric_k}_accuracy", hit_rate)),
            f"precision_at_{metric_k}": precision_at_k,
            f"recall_at_{metric_k}": recall_at_k,
            f"ndcg_at_{metric_k}": float(np.mean(ndcg_scores)),
        }

    def _plot_history(self, history: Any, model_type: str) -> str | None:
        try:
            import matplotlib.pyplot as plt
        except Exception:
            return None

        self.artifacts_dir.mkdir(parents=True, exist_ok=True)
        fig, ax = plt.subplots(1, 2, figsize=(10, 4))

        ax[0].plot(history.history.get("loss", []), label="train")
        ax[0].plot(history.history.get("val_loss", []), label="val")
        ax[0].set_title(f"{model_type.upper()} Loss")
        ax[0].set_xlabel("epoch")
        ax[0].set_ylabel("loss")
        ax[0].legend()

        ax[1].plot(history.history.get("accuracy", []), label="train")
        ax[1].plot(history.history.get("val_accuracy", []), label="val")
        ax[1].set_title(f"{model_type.upper()} Accuracy")
        ax[1].set_xlabel("epoch")
        ax[1].set_ylabel("accuracy")
        ax[1].legend()

        output_path = self.artifacts_dir / f"history_{model_type}.png"
        fig.tight_layout()
        fig.savefig(output_path, dpi=160)
        plt.close(fig)
        return str(output_path)

    def _plot_metric_comparison(self, results: dict[str, dict[str, float]], metric_key: str) -> str | None:
        try:
            import matplotlib.pyplot as plt
        except Exception:
            return None

        self.artifacts_dir.mkdir(parents=True, exist_ok=True)
        labels = list(results.keys())
        values = [float(results[name].get(metric_key, 0.0)) for name in labels]

        fig, ax = plt.subplots(figsize=(6, 4))
        ax.bar(labels, values, color=["#4C78A8", "#F58518", "#54A24B"][: len(labels)])
        ax.set_title(f"Model Comparison: {metric_key}")
        ax.set_xlabel("model")
        ax.set_ylabel(metric_key)
        fig.tight_layout()

        output_path = self.artifacts_dir / f"compare_{metric_key}.png"
        fig.savefig(output_path, dpi=160)
        plt.close(fig)
        return str(output_path)

    def train_from_behaviors(
        self,
        behaviors: list[BehaviorORM],
        epochs: int = 25,
        sequence_length: int = 4,
        models: list[str] | None = None,
        metric_k: int = 5,
        save_best: bool = True,
    ) -> dict[str, Any]:
        tf = _get_tf()
        if tf is None:
            return {
                "trained": False,
                "message": "TensorFlow chưa sẵn sàng trong môi trường hiện tại.",
            }

        self.sequence_length = max(2, sequence_length)
        by_user: dict[int, list[BehaviorORM]] = defaultdict(list)
        for behavior in sorted(behaviors, key=lambda x: (x.user_id, x.timestamp)):
            by_user[behavior.user_id].append(behavior)

        product_ids = sorted({int(item.product_id) for item in behaviors})
        if len(product_ids) < 2:
            return {"trained": False, "message": "Không đủ sản phẩm khác nhau để huấn luyện."}

        self.product_to_idx = {pid: idx for idx, pid in enumerate(product_ids)}
        self.idx_to_product = {idx: pid for pid, idx in self.product_to_idx.items()}

        train_x: list[list[list[float]]] = []
        train_y: list[int] = []

        for user_events in by_user.values():
            if len(user_events) <= self.sequence_length:
                continue

            for i in range(len(user_events) - self.sequence_length):
                window = user_events[i : i + self.sequence_length]
                target = user_events[i + self.sequence_length]
                if target.product_id not in self.product_to_idx:
                    continue

                train_x.append(
                    [
                        self._event_vector(int(event.product_id), str(event.action).lower(), event.timestamp)
                        for event in window
                    ]
                )
                train_y.append(self.product_to_idx[int(target.product_id)])

        if not train_x:
            return {"trained": False, "message": "Không đủ chuỗi hành vi để huấn luyện LSTM."}

        x_train = np.array(train_x, dtype=np.float32)
        y_train = np.array(train_y, dtype=np.int32)

        x_train, y_train, x_val, y_val = self._split_train_val(x_train, y_train, ratio=0.2)
        if len(x_val) == 0 or len(x_train) == 0:
            return {"trained": False, "message": "Không đủ dữ liệu để tách tập validation."}

        models_to_train = [m.strip().lower() for m in (models or ["rnn", "lstm", "bilstm"]) if m.strip()]
        results: dict[str, dict[str, float]] = {}
        histories: dict[str, Any] = {}
        best_model = None
        best_name = None
        best_score = -1.0
        best_tie = -1.0

        for model_type in models_to_train:
            model = self._build_model(tf, model_type, len(self.product_to_idx), metric_k)
            history = model.fit(
                x_train,
                y_train,
                validation_data=(x_val, y_val),
                epochs=max(1, epochs),
                verbose=0,
            )
            metrics = self._evaluate_model(model, x_val, y_val, metric_k)
            results[model_type] = metrics
            histories[model_type] = history

            score = float(metrics.get(f"ndcg_at_{metric_k}", 0.0))
            tie_breaker = float(metrics.get(f"val_top_{metric_k}_accuracy", 0.0))
            if score > best_score or (score == best_score and tie_breaker > best_tie):
                best_score = score
                best_tie = tie_breaker
                best_model = model
                best_name = model_type

        if best_model is None or best_name is None:
            return {"trained": False, "message": "Huấn luyện thất bại do không có mô hình hợp lệ."}

        plot_paths: dict[str, str] = {}
        for model_type, history in histories.items():
            plot_path = self._plot_history(history, model_type)
            if plot_path:
                plot_paths[model_type] = plot_path

        compare_plot = self._plot_metric_comparison(results, f"ndcg_at_{metric_k}")
        if compare_plot:
            plot_paths["comparison"] = compare_plot

        self.model = best_model
        self.model_name = best_name
        self.model_metrics = results.get(best_name, {})

        if save_best:
            self.artifacts_dir.mkdir(parents=True, exist_ok=True)
            model_path = self.artifacts_dir / "best_recommender.keras"
            best_model.save(model_path)

        self.last_trained_at = datetime.now(timezone.utc)
        return {
            "trained": True,
            "message": "Đã huấn luyện nhiều mô hình và chọn mô hình tốt nhất.",
            "samples": len(train_x) + len(x_val),
            "products": len(self.product_to_idx),
            "best_model": best_name,
            "metrics": results,
            "plots": plot_paths,
            "last_trained_at": self.last_trained_at.isoformat(),
        }

    def predict_scores(self, user_behaviors: list[BehaviorORM], candidate_ids: list[int]) -> dict[int, float]:
        tf = _get_tf()
        if not candidate_ids:
            return {}

        if tf is None or self.model is None or not user_behaviors:
            return self._fallback_scores(user_behaviors, candidate_ids)

        ordered = sorted(user_behaviors, key=lambda x: x.timestamp)
        recent = ordered[-self.sequence_length :]
        if len(recent) < self.sequence_length:
            return self._fallback_scores(user_behaviors, candidate_ids)

        window = np.array(
            [[self._event_vector(int(event.product_id), str(event.action).lower(), event.timestamp) for event in recent]],
            dtype=np.float32,
        )
        probs = self.model.predict(window, verbose=0)[0].tolist()

        out: dict[int, float] = {}
        for pid in candidate_ids:
            idx = self.product_to_idx.get(int(pid))
            out[int(pid)] = float(probs[idx]) if idx is not None else 0.0
        return out

    def _fallback_scores(self, user_behaviors: list[BehaviorORM], candidate_ids: list[int]) -> dict[int, float]:
        if not user_behaviors:
            return {int(pid): 0.0 for pid in candidate_ids}

        now = datetime.now(timezone.utc)
        agg: dict[int, float] = defaultdict(float)
        for behavior in user_behaviors:
            weight = self.ACTION_WEIGHT.get(str(behavior.action).lower(), 0.1)
            days_ago = max((now - behavior.timestamp).total_seconds() / 86400.0, 0.0)
            recency = math.exp(-days_ago / 14.0)
            agg[int(behavior.product_id)] += weight * recency

        max_score = max(agg.values(), default=1.0) or 1.0
        return {int(pid): float(agg.get(int(pid), 0.0)) / max_score for pid in candidate_ids}
