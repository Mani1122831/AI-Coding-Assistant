"""
tests/test_history_activity.py
Unit tests for coding history, secret redaction, and activity logging.
Tests run in isolation using mocked database services.
"""
import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock
from bson import ObjectId

from models.schemas import ActivityLog, HistoryRecord
from services.history_service import HistoryService
from services.activity_service import ActivityService


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def mock_db_service():
    mock = MagicMock()
    mock.is_connected = True
    return mock


@pytest.fixture
def history_service(mock_db_service):
    return HistoryService(db_service=mock_db_service)


@pytest.fixture
def activity_service(mock_db_service):
    return ActivityService(db_service=mock_db_service)


# ── Secret Redaction Tests ───────────────────────────────────────────────────

class TestSecretRedaction:
    def test_redact_gemini_api_key(self):
        text = "GEMINI_API_KEY = 'AIzaSyA1234567890abcdefghijklmnopqrst'"
        sanitized, detected = HistoryService.sanitize_text(text)
        assert detected is True
        assert "AIzaSy" not in sanitized
        assert "[REDACTED_SECRET]" in sanitized

    def test_redact_openai_api_key(self):
        text = "client = OpenAI(api_key='sk-1234567890abcdefghijklmnopqrstuvwxyz1234567890')"
        sanitized, detected = HistoryService.sanitize_text(text)
        assert detected is True
        assert "sk-" not in sanitized
        assert "[REDACTED_SECRET]" in sanitized

    def test_redact_github_token(self):
        text = "GITHUB_TOKEN = 'ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890'"
        sanitized, detected = HistoryService.sanitize_text(text)
        assert detected is True
        assert "ghp_" not in sanitized
        assert "[REDACTED_SECRET]" in sanitized

    def test_redact_aws_access_key(self):
        text = "AWS_ACCESS_KEY_ID = 'AKIAIOSFODNN7EXAMPLE'"
        sanitized, detected = HistoryService.sanitize_text(text)
        assert detected is True
        assert "AKIAIOSFODNN7EXAMPLE" not in sanitized
        assert "[REDACTED_SECRET]" in sanitized

    def test_redact_mongodb_uri_credentials(self):
        text = "mongodb+srv://admin_user:SuperSecretPassword123@cluster0.abc.mongodb.net/dev_db"
        sanitized, detected = HistoryService.sanitize_text(text)
        assert detected is True
        assert "admin_user" not in sanitized
        assert "SuperSecretPassword123" not in sanitized
        assert "[REDACTED_SECRET]" in sanitized

    def test_redact_postgres_uri_credentials(self):
        text = "DATABASE_URL = 'postgres://dbuser:mypassword99@localhost:5432/mydb'"
        sanitized, detected = HistoryService.sanitize_text(text)
        assert detected is True
        assert "mypassword99" not in sanitized
        assert "[REDACTED_SECRET]" in sanitized

    def test_normal_code_not_mangled(self):
        code = "def calculate_sum(a, b):\n    return a + b\n\nresult = calculate_sum(10, 20)\nprint(result)"
        sanitized, detected = HistoryService.sanitize_text(code)
        assert detected is False
        assert sanitized == code


# ── HistoryService Tests ──────────────────────────────────────────────────────

class TestHistoryService:
    def test_save_history_sanitizes_and_persists(self, history_service, mock_db_service):
        mock_col = MagicMock()
        fake_id = ObjectId()
        mock_col.insert_one.return_value = MagicMock(inserted_id=fake_id)
        mock_db_service.get_history_collection.return_value = mock_col

        raw_input = "Analyze this key: AIzaSyA1234567890abcdefghijklmnopqrst"
        raw_output = "Found secret: AIzaSyA1234567890abcdefghijklmnopqrst"

        rec_id, secret_detected = history_service.save_history(
            user_id="user_123",
            operation="Security Analysis",
            language="Python",
            input_summary="Code scan",
            input_code=raw_input,
            generated_code=raw_output,
            explanation="Scanned code for secrets",
            metadata={"risk": "HIGH"},
        )

        assert rec_id == str(fake_id)
        assert secret_detected is True
        mock_col.insert_one.assert_called_once()
        saved_doc = mock_col.insert_one.call_args[0][0]

        assert saved_doc["user_id"] == "user_123"
        assert saved_doc["operation"] == "security analysis"
        assert "AIzaSy" not in saved_doc["input_code"]
        assert "AIzaSy" not in saved_doc["generated_code"]
        assert "[REDACTED_SECRET]" in saved_doc["input_code"]
        assert "[REDACTED_SECRET]" in saved_doc["generated_code"]

    def test_get_user_history_filters_by_user_id(self, history_service, mock_db_service):
        fake_id = ObjectId()
        mock_doc = {
            "_id": fake_id,
            "user_id": "user_123",
            "operation": "generate code",
            "language": "Python",
            "input_summary": "Write a binary search",
            "input_code": "def binary_search()...",
            "generated_code": "def binary_search()...",
            "explanation": "Binary search implementation",
            "metadata": {},
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        mock_col = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.sort.return_value = mock_cursor
        mock_cursor.limit.return_value = [mock_doc]
        mock_col.find.return_value = mock_cursor
        mock_db_service.get_history_collection.return_value = mock_col

        records = history_service.get_user_history(user_id="user_123", operation="Generate Code")

        assert len(records) == 1
        assert records[0].id == str(fake_id)
        assert records[0].user_id == "user_123"
        assert records[0].operation == "generate code"

        query = mock_col.find.call_args[0][0]
        assert query["user_id"] == "user_123"
        assert query["operation"] == "generate code"

    def test_delete_history_item_enforces_user_isolation(self, history_service, mock_db_service):
        item_id = str(ObjectId())
        mock_col = MagicMock()
        mock_col.delete_one.return_value = MagicMock(deleted_count=1)
        mock_db_service.get_history_collection.return_value = mock_col

        deleted = history_service.delete_history_item("user_123", item_id)
        assert deleted is True

        delete_query = mock_col.delete_one.call_args[0][0]
        assert delete_query["_id"] == ObjectId(item_id)
        assert delete_query["user_id"] == "user_123"

    def test_clear_user_history_scoped_to_user(self, history_service, mock_db_service):
        mock_col = MagicMock()
        mock_col.delete_many.return_value = MagicMock(deleted_count=5)
        mock_db_service.get_history_collection.return_value = mock_col

        count = history_service.clear_user_history("user_123")
        assert count == 5
        delete_query = mock_col.delete_many.call_args[0][0]
        assert delete_query == {"user_id": "user_123"}


# ── ActivityService Tests ─────────────────────────────────────────────────────

class TestActivityService:
    def test_log_activity_records_event(self, activity_service, mock_db_service):
        mock_col = MagicMock()
        mock_db_service.get_activity_collection.return_value = mock_col

        activity_service.log_activity(
            user_id="user_123",
            action="Generate Code",
            details={"description": "Generated Python code for binary search"},
        )

        mock_col.insert_one.assert_called_once()
        doc = mock_col.insert_one.call_args[0][0]
        assert doc["user_id"] == "user_123"
        assert doc["action"] == "Generate Code"
        assert doc["details"]["description"] == "Generated Python code for binary search"
        assert isinstance(doc["timestamp"], str)

    def test_get_recent_activities_returns_records(self, activity_service, mock_db_service):
        fake_id = ObjectId()
        mock_doc = {
            "_id": fake_id,
            "user_id": "user_123",
            "action": "User Login",
            "details": {"method": "web"},
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        mock_col = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.sort.return_value = mock_cursor
        mock_cursor.limit.return_value = [mock_doc]
        mock_col.find.return_value = mock_cursor
        mock_db_service.get_activity_collection.return_value = mock_col

        activities = activity_service.get_recent_activities("user_123", limit=10)
        assert len(activities) == 1
        assert activities[0].id == str(fake_id)
        assert activities[0].action == "User Login"
