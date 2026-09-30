"""
services/mongo_service.py

MongoDB Atlas persistence layer for AI Coding Assistant.
Provides cached client lifecycle management, connection diagnostics,
and idempotent index initialization for users, coding_history, and activity_logs collections.
"""
from __future__ import annotations

from typing import Any, Optional, Tuple

from config.settings import settings
from utils.logger import get_logger

logger = get_logger(__name__)


class DatabaseUnavailableError(Exception):
    """Raised when an operation is attempted while MongoDB is unreachable."""
    pass


class MongoService:
    """
    Singleton service managing MongoDB Atlas connection and collection access.
    Caches the client instance to avoid recreating connections on every Streamlit rerun.
    """

    _instance: Optional[MongoService] = None
    _client: Optional[Any] = None
    _indexes_created: bool = False

    def __new__(cls) -> MongoService:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        # Avoid re-running __init__ if already initialized
        if hasattr(self, "_initialized") and self._initialized:
            return
        self._initialized = True
        self._uri = settings.mongodb_uri
        self._db_name = settings.mongodb_database

    def get_client(self) -> Optional[Any]:
        """
        Get or initialize the cached MongoClient instance.
        Returns None if MONGODB_URI is not set or pymongo is missing.
        """
        if not settings.mongodb_uri:
            return None

        if self._client is not None:
            return self._client

        try:
            from pymongo import MongoClient
            from pymongo.server_api import ServerApi

            self._client = MongoClient(
                settings.mongodb_uri,
                server_api=ServerApi("1"),
                serverSelectionTimeoutMS=5000,
                connectTimeoutMS=5000,
                socketTimeoutMS=5000,
                appname="ai_coding_assistant",
            )
            self._ensure_indexes()
            logger.info("MongoDB client initialized for database: %s", settings.mongodb_database)
            return self._client
        except Exception as exc:
            logger.error("Failed to initialize MongoDB client: %s", exc)
            self._client = None
            return None

    def get_database(self) -> Any:
        """
        Return the configured database handle.
        Raises DatabaseUnavailableError if connection cannot be established.
        """
        client = self.get_client()
        if client is None:
            raise DatabaseUnavailableError(
                "MongoDB is not configured or unavailable. Please check MONGODB_URI in your .env file."
            )
        return client[settings.mongodb_database]

    def get_users_collection(self) -> Any:
        """Return the 'users' collection."""
        return self.get_database()[settings.mongodb_users_collection]

    def get_history_collection(self) -> Any:
        """Return the 'coding_history' collection."""
        return self.get_database()[settings.mongodb_history_collection]

    def get_activity_collection(self) -> Any:
        """Return the 'activity_logs' collection."""
        return self.get_database()[settings.mongodb_activity_collection]

    def is_available(self) -> bool:
        """Fast check to determine if MongoDB is configured and reachable."""
        if not settings.mongodb_uri:
            return False
        try:
            client = self.get_client()
            if client is None:
                return False
            # Ping database with short timeout
            client.admin.command("ping")
            return True
        except Exception as exc:
            logger.debug("MongoDB is_available check failed: %s", exc)
            return False

    @staticmethod
    def _sanitize_connection_error(exc: Exception) -> str:
        """Extract a safe, human-readable reason without exposing passwords or URIs."""
        err_msg = str(exc).lower()
        if "tlsv1 alert internal error" in err_msg or "ssl handshake failed" in err_msg:
            return "IP address not allowed in Atlas Network Access or SSL handshake rejected"
        if "authentication failed" in err_msg or "bad auth" in err_msg or "auth failed" in err_msg:
            return "Authentication failed (invalid database username or password)"
        if "timed out" in err_msg or "serverselectiontimeouterror" in err_msg or "timeout" in err_msg:
            return "Connection timeout (cluster unreachable or network blocked)"
        if "configurationerror" in err_msg:
            return "Invalid connection string configuration"
        return "Unable to establish connection to database"

    def test_connection(self) -> Tuple[bool, str]:
        """
        Diagnostic connection test safe for user display.
        Verifies: MongoDB client → database → users collection
        Never reveals connection URI, password, or cluster internals.

        Returns only:
            (True, "Connected successfully")
            or
            (False, "Connection failed: <sanitized reason>")
        """
        if not settings.mongodb_uri or not settings.mongodb_uri.strip():
            return False, "Connection failed: MongoDB URI is not configured in .env"

        try:
            from pymongo import MongoClient

            test_client = MongoClient(
                settings.mongodb_uri,
                serverSelectionTimeoutMS=4000,
                connectTimeoutMS=4000,
                socketTimeoutMS=4000,
            )
            # 1. Verify client can ping admin
            test_client.admin.command("ping")

            # 2. Verify database handle
            db = test_client[settings.mongodb_database]

            # 3. Verify users collection access
            users_col = db[settings.mongodb_users_collection]
            users_col.estimated_document_count()

            # 4. Ensure required unique indexes
            self._ensure_indexes(test_client)

            return True, "Connected successfully"
        except Exception as exc:
            logger.warning("MongoDB diagnostic test failed: %s", exc)
            sanitized = self._sanitize_connection_error(exc)
            return False, f"Connection failed: {sanitized}"

    def _ensure_indexes(self, client: Optional[Any] = None) -> None:
        """
        Create required unique and query indexes idempotently.
        """
        if self._indexes_created:
            return

        target_client = client or self._client or self.get_client()
        if target_client is None:
            return

        try:
            from pymongo import ASCENDING, DESCENDING

            db = target_client[settings.mongodb_database]

            # 1. Users collection: unique email, unique username, and reset token hash lookup
            users_col = db[settings.mongodb_users_collection]
            users_col.create_index([("email", ASCENDING)], unique=True, name="uniq_user_email")
            users_col.create_index([("username", ASCENDING)], unique=True, name="uniq_user_username")
            users_col.create_index([("password_reset_token_hash", ASCENDING)], sparse=True, name="idx_reset_token_hash")


            # 2. Coding History collection: user_id + created_at
            history_col = db[settings.mongodb_history_collection]
            history_col.create_index([("user_id", ASCENDING), ("created_at", DESCENDING)], name="idx_user_history")
            history_col.create_index([("created_at", DESCENDING)], name="idx_history_date")

            # 3. Activity Logs collection: user_id + timestamp
            activity_col = db[settings.mongodb_activity_collection]
            activity_col.create_index([("user_id", ASCENDING), ("timestamp", DESCENDING)], name="idx_user_activity")

            self._indexes_created = True
            logger.info("MongoDB indexes verified successfully.")
        except Exception as exc:
            logger.warning("Failed to create/verify MongoDB indexes: %s", exc)


# Singleton instance
mongo_service = MongoService()
