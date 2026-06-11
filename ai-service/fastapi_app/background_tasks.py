"""
Background tasks for automatic model updates and scheduled retraining.
"""

from datetime import datetime, timezone, timedelta
import logging
from typing import Any
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from .database import BehaviorORM, db_manager
from .container import container

logger = logging.getLogger(__name__)
scheduler = BackgroundScheduler()
_last_behavior_count = 0
_update_config = {
    "mode": "on-demand",  # "immediate", "batch", "on-demand"
    "batch_interval_hours": 6,
    "behavior_threshold": 10,  # Train if N new behaviors added
    "enabled": True,
}


def _get_behavior_count() -> int:
    """Get total number of behaviors in database."""
    db = db_manager.get_session()
    try:
        count = db.query(BehaviorORM).count()
        return count
    finally:
        db.close()


def _retrain_models() -> dict[str, Any]:
    """Retrain models with latest behavior data."""
    try:
        db = db_manager.get_session()
        behaviors = db.query(BehaviorORM).order_by(BehaviorORM.user_id, BehaviorORM.timestamp).all()
        db.close()

        if len(behaviors) < 10:
            logger.info("Not enough behavior data for retraining.")
            return {"trained": False, "message": "Insufficient data"}

        result = container.lstm.train_from_behaviors(
            behaviors=behaviors,
            epochs=20,
            sequence_length=4,
            models=["rnn", "lstm", "bilstm"],
            metric_k=5,
            save_best=True,
        )
        logger.info(f"Model retraining completed: {result.get('best_model', 'unknown')}")
        return result
    except Exception as e:
        logger.error(f"Error during model retraining: {str(e)}")
        return {"trained": False, "error": str(e)}


def trigger_immediate_update(new_behaviors_count: int) -> dict[str, Any]:
    """
    For 'immediate' mode: retrain if threshold behaviors accumulated.
    """
    global _last_behavior_count
    current_count = _get_behavior_count()
    behaviors_since_training = current_count - _last_behavior_count

    if behaviors_since_training >= _update_config.get("behavior_threshold", 10):
        _last_behavior_count = current_count
        result = _retrain_models()
        return {
            "triggered": True,
            "reason": f"Accumulated {behaviors_since_training} new behaviors",
            **result,
        }
    return {
        "triggered": False,
        "behaviors_accumulated": behaviors_since_training,
        "threshold": _update_config.get("behavior_threshold", 10),
    }


def schedule_batch_retraining():
    """
    For 'batch' mode: scheduled retraining at regular intervals.
    """
    result = _retrain_models()
    return {
        "scheduled_retrain": True,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        **result,
    }


def initialize_scheduler() -> None:
    """Initialize background scheduler with configured update mode."""
    mode = _update_config.get("mode", "on-demand")
    interval_hours = _update_config.get("batch_interval_hours", 6)

    if not _update_config.get("enabled", True):
        logger.info("Background tasks are disabled.")
        return

    global _last_behavior_count
    _last_behavior_count = _get_behavior_count()

    try:
        if mode == "batch":
            # Schedule periodic retraining
            trigger = IntervalTrigger(hours=interval_hours)
            scheduler.add_job(
                schedule_batch_retraining,
                trigger,
                id="batch_retrain",
                name="Batch Model Retraining",
                replace_existing=True,
                max_instances=1,
            )
            logger.info(f"Batch retraining scheduled every {interval_hours} hours")

        scheduler.start()
        logger.info(f"Background scheduler started in '{mode}' mode")
    except Exception as e:
        logger.error(f"Failed to initialize scheduler: {str(e)}")


def shutdown_scheduler() -> None:
    """Shutdown background scheduler gracefully."""
    try:
        if scheduler.running:
            scheduler.shutdown(wait=True)
            logger.info("Background scheduler shut down.")
    except Exception as e:
        logger.error(f"Error shutting down scheduler: {str(e)}")


def configure_update_mode(
    mode: str = "on-demand",
    batch_interval_hours: int = 6,
    behavior_threshold: int = 10,
) -> dict[str, Any]:
    """
    Configure model update mode.

    Args:
        mode: "immediate", "batch", or "on-demand"
        batch_interval_hours: Hours between scheduled retraining
        behavior_threshold: New behaviors required to trigger immediate update
    """
    global _update_config
    _update_config["mode"] = mode
    _update_config["batch_interval_hours"] = batch_interval_hours
    _update_config["behavior_threshold"] = behavior_threshold

    # Restart scheduler if it's running
    if scheduler.running:
        shutdown_scheduler()
        initialize_scheduler()

    return {
        "configured": True,
        "mode": mode,
        "batch_interval_hours": batch_interval_hours,
        "behavior_threshold": behavior_threshold,
    }


def get_update_config() -> dict[str, Any]:
    """Get current update configuration."""
    behavior_count = _get_behavior_count()
    return {
        **_update_config,
        "total_behaviors": behavior_count,
        "last_trained_at": container.lstm.last_trained_at.isoformat()
        if container.lstm.last_trained_at
        else None,
        "scheduler_running": scheduler.running,
    }
