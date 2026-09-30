"""
services/history_service.py

Coding history persistence service for AI Coding Assistant.
Provides secret detection & redaction before storage, user-scoped querying,
search/filtering, and record lifecycle management backed by MongoDB Atlas.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from bson import ObjectId

from models.schemas import HistoryRecord
from services.mongo_service import DatabaseUnavailableError, MongoService, mongo_service
from utils.logger import get_logger

logger = get_logger(__name__)

# Patterns for detecting common API keys, tokens, and credentials
_SECRET_PATTERNS = [
    re.compile(r"AIza[0-9A-Za-z-_]{30,45}"),                      # Google/Gemini API key
    re.compile(r"sk-[a-zA-Z0-9_-]{20,}"),                         # OpenAI API key
    re.compile(r"ghp_[0-9a-zA-Z]{30,}"),                          # GitHub Personal Access Token
    re.compile(r"gho_[0-9a-zA-Z]{30,}"),                          # GitHub OAuth Token
    re.compile(r"AKIA[0-9A-Z]{16}"),                              # AWS Access Key ID
    re.compile(r"mongodb(\+srv)?://[^\s\"']+"),                   # MongoDB connection string
    re.compile(r"postgres(ql)?://[^\s\"']+"),                     # Postgres connection string
    re.compile(r"mysql://[^\s\"']+"),                             # MySQL connection string
    re.compile(r"-----BEGIN (?:RSA )?PRIVATE KEY-----"),          # Private key header
    re.compile(r"(?:api[_-]?key|secret|password|passwd|token)\s*=\s*['\"][^'\"]{6,}['\"]", re.IGNORECASE),
]


class HistoryService:
    """
    Manages coding history records in MongoDB with secret redaction and user-level isolation.
    """

    def __init__(self, db_service: Optional[MongoService] = None) -> None:
        self._db_service = db_service or mongo_service

    @staticmethod
    def sanitize_text(text: Optional[str]) -> Tuple[Optional[str], bool]:
        """
        Scan text for hardcoded API keys, passwords, and tokens.
        Redact any detected secrets with [REDACTED_SECRET].

        Returns:
            Tuple of (sanitized_text, secret_was_detected: bool)
        """
        if not text:
            return text, False

        detected = False
        cleaned = text

        for pattern in _SECRET_PATTERNS:
            if pattern.search(cleaned):
                detected = True
                cleaned = pattern.sub("[REDACTED_SECRET]", cleaned)

        return cleaned, detected

    def save_history(
        self,
        user_id: str,
        operation: str,
        language: str,
        input_summary: str,
        input_code: Optional[str] = None,
        generated_code: Optional[str] = None,
        explanation: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Tuple[Optional[str], bool]:
        """
        Persist a coding interaction to MongoDB after redacting any detected credentials.

        Returns:
            Tuple of (inserted_id: Optional[str], secret_detected: bool)
        """
        if not user_id:
            logger.warning("Cannot save history record without user_id")
            return None, False

        # Redact secrets from all user-generated texts
        clean_summary, det_summary = self.sanitize_text(input_summary)
        clean_input, det_input = self.sanitize_text(input_code)
        clean_generated, det_gen = self.sanitize_text(generated_code)
        clean_expl, det_expl = self.sanitize_text(explanation)

        secret_detected = any([det_summary, det_input, det_gen, det_expl])

        meta = dict(metadata or {})
        if secret_detected:
            meta["secret_redacted"] = True

        now_iso = datetime.now(timezone.utc).isoformat()

        doc: Dict[str, Any] = {
            "user_id": user_id,
            "operation": operation.lower(),
            "language": language or "Unknown",
            "input_summary": clean_summary or "",
            "input_code": clean_input,
            "generated_code": clean_generated,
            "explanation": clean_expl,
            "metadata": meta,
            "created_at": now_iso,
        }

        try:
            history_col = self._db_service.get_history_collection()
            result = history_col.insert_one(doc)
            record_id = str(result.inserted_id)
            logger.debug("Saved history record %s for user %s (operation: %s)", record_id, user_id, operation)
            return record_id, secret_detected
        except DatabaseUnavailableError:
            logger.debug("MongoDB unavailable — history record not persisted")
            return None, secret_detected
        except Exception as exc:
            logger.error("Failed to save history record for user %s: %s", user_id, exc)
            return None, secret_detected

    def get_user_history(
        self,
        user_id: str,
        limit: int = 50,
        operation: Optional[str] = None,
        search_query: Optional[str] = None,
    ) -> List[HistoryRecord]:
        """
        Retrieve history records strictly belonging to the specified user.
        Supports filtering by operation type and text search.
        """
        if not user_id:
            return []

        try:
            history_col = self._db_service.get_history_collection()
        except Exception:
            return []

        query: Dict[str, Any] = {"user_id": user_id}

        if operation and operation.lower() != "all":
            query["operation"] = operation.lower()

        if search_query and search_query.strip():
            regex = re.compile(re.escape(search_query.strip()), re.IGNORECASE)
            query["$or"] = [
                {"input_summary": regex},
                {"input_code": regex},
                {"generated_code": regex},
                {"language": regex},
                {"explanation": regex},
            ]

        try:
            cursor = (
                history_col.find(query)
                .sort("created_at", -1)
                .limit(limit)
            )

            records: List[HistoryRecord] = []
            for doc in cursor:
                records.append(
                    HistoryRecord(
                        id=str(doc["_id"]),
                        user_id=doc.get("user_id", user_id),
                        operation=doc.get("operation", "unknown"),
                        language=doc.get("language", "Unknown"),
                        input_summary=doc.get("input_summary", ""),
                        input_code=doc.get("input_code"),
                        generated_code=doc.get("generated_code"),
                        explanation=doc.get("explanation"),
                        metadata=doc.get("metadata", {}),
                        created_at=str(doc.get("created_at", "")),
                    )
                )
            return records
        except Exception as exc:
            logger.error("Error querying history for user %s: %s", user_id, exc)
            return []

    def get_history_item(self, user_id: str, item_id: str) -> Optional[HistoryRecord]:
        """
        Fetch a specific history record by ID, enforcing user ownership.
        """
        if not user_id or not item_id:
            return None

        try:
            history_col = self._db_service.get_history_collection()
            doc = history_col.find_one({"_id": ObjectId(item_id), "user_id": user_id})
            if not doc:
                return None
            return HistoryRecord(
                id=str(doc["_id"]),
                user_id=doc.get("user_id", user_id),
                operation=doc.get("operation", "unknown"),
                language=doc.get("language", "Unknown"),
                input_summary=doc.get("input_summary", ""),
                input_code=doc.get("input_code"),
                generated_code=doc.get("generated_code"),
                explanation=doc.get("explanation"),
                metadata=doc.get("metadata", {}),
                created_at=str(doc.get("created_at", "")),
            )
        except Exception as exc:
            logger.warning("Error fetching history item %s for user %s: %s", item_id, user_id, exc)
            return None

    def delete_history_item(self, user_id: str, item_id: str) -> bool:
        """
        Delete a single history record belonging to the user.
        """
        if not user_id or not item_id:
            return False

        try:
            history_col = self._db_service.get_history_collection()
            res = history_col.delete_one({"_id": ObjectId(item_id), "user_id": user_id})
            return res.deleted_count > 0
        except Exception as exc:
            logger.error("Error deleting history item %s for user %s: %s", item_id, user_id, exc)
            return False

    def clear_user_history(self, user_id: str) -> int:
        """
        Delete all history records for a given user.
        Returns the number of deleted records.
        """
        if not user_id:
            return 0

        try:
            history_col = self._db_service.get_history_collection()
            res = history_col.delete_many({"user_id": user_id})
            logger.info("Cleared %d history records for user %s", res.deleted_count, user_id)
            return res.deleted_count
        except Exception as exc:
            logger.error("Error clearing history for user %s: %s", user_id, exc)
            return 0


# Singleton instance
history_service = HistoryService()
