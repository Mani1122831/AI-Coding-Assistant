"""
services/activity_service.py

Lightweight audit and activity logging service for AI Coding Assistant.
Logs non-sensitive user events (registration, login, logout, tool usage)
persisted in MongoDB Atlas.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from models.schemas import ActivityLog
from services.mongo_service import DatabaseUnavailableError, MongoService, mongo_service
from utils.logger import get_logger

logger = get_logger(__name__)


class ActivityService:
    """
    Service for logging and retrieving lightweight user activity events.
    """

    def __init__(self, db_service: Optional[MongoService] = None) -> None:
        self._db_service = db_service or mongo_service

    def log_activity(
        self,
        user_id: str,
        action: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Record a user activity event.
        Guarantees no sensitive data (passwords, tokens, keys) is logged.
        """
        if not user_id or not action:
            return

        now_iso = datetime.now(timezone.utc).isoformat()
        doc = {
            "user_id": user_id,
            "action": action,
            "timestamp": now_iso,
            "details": details or {},
        }

        try:
            activity_col = self._db_service.get_activity_collection()
            activity_col.insert_one(doc)
            logger.debug("Logged activity '%s' for user %s", action, user_id)
        except DatabaseUnavailableError:
            logger.debug("MongoDB unavailable — activity '%s' skipped", action)
        except Exception as exc:
            logger.debug("Non-fatal error writing activity log: %s", exc)

    def get_recent_activities(
        self, user_id: str, limit: int = 10
    ) -> List[ActivityLog]:
        """
        Retrieve recent activity events for a specific user.
        """
        if not user_id:
            return []

        try:
            activity_col = self._db_service.get_activity_collection()
            cursor = (
                activity_col.find({"user_id": user_id})
                .sort("timestamp", -1)
                .limit(limit)
            )

            activities: List[ActivityLog] = []
            for doc in cursor:
                activities.append(
                    ActivityLog(
                        id=str(doc["_id"]),
                        user_id=doc.get("user_id", user_id),
                        action=doc.get("action", "unknown"),
                        timestamp=str(doc.get("timestamp", "")),
                        details=doc.get("details"),
                    )
                )
            return activities
        except Exception as exc:
            logger.debug("Error fetching recent activities for user %s: %s", user_id, exc)
            return []


# Singleton instance
activity_service = ActivityService()
