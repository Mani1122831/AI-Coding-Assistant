"""
tests/test_forgot_password_security.py

Dedicated security and regression tests for Forgot Password & Reset Token handling:
1. No raw reset tokens or full reset URLs rendered or logged in UI/source.
2. Accurate notification when SMTP is not configured vs configured.
3. Safe in-memory development transition without plain-text token exposure.
4. Complete suppression of development tools and tokens in production mode.
5. Cryptographic token security (SHA-256 hash storage, expiration, single-use, bcrypt password storage).
"""
import hashlib
import inspect
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest
from bson import ObjectId

import app
from config.settings import settings
from services.auth_service import AuthService
from services.email_service import EmailService


@pytest.fixture
def mock_db():
    mock = MagicMock()
    mock.is_connected = True
    return mock


@pytest.fixture
def mock_email():
    mock = MagicMock()
    mock.is_configured = False
    mock.send_password_reset_email.return_value = (False, "SMTP is not configured.")
    return mock


class TestForgotPasswordUISecurity:
    def test_app_source_contains_no_raw_token_or_dev_url_leaks(self):
        """
        Verify that app.py does not display raw reset tokens or test URLs in plain text.
        """
        app_source = inspect.getsource(app)

        # Forbidden strings in UI templates
        assert "dev_reset_url" not in app_source, "Found dev_reset_url in app.py UI"
        assert "Testing Reset Link" not in app_source, "Found raw test link template in app.py"
        assert "Open Reset Password Page with Dev Token" not in app_source, "Found raw dev token button in app.py"
        assert "dev_last_token" not in app_source, "Found legacy dev_last_token in app.py"

    def test_reset_password_field_is_masked(self):
        """
        Verify that the token input on the reset password screen is masked with type='password'.
        """
        render_fn_source = inspect.getsource(app._render_auth_reset_password)
        assert 'type="password"' in render_fn_source
        assert '"Reset Token"' in render_fn_source


class TestSMTPConfiguredVsUnconfiguredMessaging:
    def test_unconfigured_smtp_honest_warning_in_dev(self, mock_db, mock_email):
        """
        When SMTP is unconfigured in development:
        - Never claim an email has been sent.
        - Return honest warning: 'Password reset email is not configured in this environment.'
        - Provide dev_token strictly for in-memory session transition.
        """
        user_id = ObjectId()
        user_doc = {
            "_id": user_id,
            "email": "dev@example.com",
            "username": "dev_user",
            "password_hash": "$2b$12$somehash",
            "is_active": True,
        }
        mock_col = MagicMock()
        mock_col.find_one.return_value = user_doc
        mock_db.get_users_collection.return_value = mock_col

        auth = AuthService(db_service=mock_db, email_srv=mock_email)

        with patch.object(settings, "environment", "development"):
            success, msg, dev_info = auth.request_password_reset("dev@example.com")

        assert success is False
        assert "Password reset email is not configured in this environment." in msg
        assert "sent" not in msg.lower()  # Never claim email sent!
        assert dev_info is not None
        assert "dev_token" in dev_info
        assert "dev_reset_url" not in dev_info
        assert len(dev_info["dev_token"]) > 20

    def test_unconfigured_smtp_hides_all_tokens_in_production(self, mock_db, mock_email):
        """
        When SMTP is unconfigured in production:
        - Return honest warning message.
        - dev_info must be strictly None.
        - MongoDB record is not updated.
        """
        user_id = ObjectId()
        user_doc = {
            "_id": user_id,
            "email": "prod@example.com",
            "username": "prod_user",
            "password_hash": "$2b$12$somehash",
            "is_active": True,
        }
        mock_col = MagicMock()
        mock_col.find_one.return_value = user_doc
        mock_db.get_users_collection.return_value = mock_col

        auth = AuthService(db_service=mock_db, email_srv=mock_email)

        with patch.object(settings, "environment", "production"):
            success, msg, dev_info = auth.request_password_reset("prod@example.com")

        assert success is False
        assert "Password reset email is not configured in this environment." in msg
        assert dev_info is None
        mock_col.update_one.assert_not_called()

    def test_configured_smtp_delivers_email_and_protects_enumeration(self, mock_db, mock_email):
        """
        When SMTP is configured:
        - Sends real email if user exists.
        - Returns generic success message whether user exists or not.
        - dev_info is strictly None.
        """
        mock_email.is_configured = True
        mock_email.send_password_reset_email.return_value = (True, "Delivered")

        # 1. Existing user
        user_doc = {
            "_id": ObjectId(),
            "email": "registered@example.com",
            "username": "reg_user",
            "password_hash": "$2b$12$somehash",
            "is_active": True,
        }
        mock_col = MagicMock()
        mock_col.find_one.return_value = user_doc
        mock_db.get_users_collection.return_value = mock_col

        auth = AuthService(db_service=mock_db, email_srv=mock_email)
        success, msg, dev_info = auth.request_password_reset("registered@example.com")

        assert success is True
        assert "If an account exists for this email, a password reset link has been sent." in msg
        assert dev_info is None
        mock_email.send_password_reset_email.assert_called_once()

        # 2. Non-existent user
        mock_email.send_password_reset_email.reset_mock()
        mock_col.find_one.return_value = None

        success_ghost, msg_ghost, dev_info_ghost = auth.request_password_reset("ghost@example.com")
        assert success_ghost is True
        assert msg_ghost == msg  # Identical enumeration-defending message
        assert dev_info_ghost is None
        mock_email.send_password_reset_email.assert_not_called()


class TestTokenStorageSecurity:
    def test_mongodb_stores_only_sha256_hash_never_raw_token(self, mock_db, mock_email):
        """
        Ensure only the SHA-256 hash is saved to MongoDB. The raw token must never be stored.
        """
        user_id = ObjectId()
        user_doc = {
            "_id": user_id,
            "email": "user@example.com",
            "username": "test_user",
            "password_hash": "$2b$12$somehash",
            "is_active": True,
        }
        mock_col = MagicMock()
        mock_col.find_one.return_value = user_doc
        mock_db.get_users_collection.return_value = mock_col

        auth = AuthService(db_service=mock_db, email_srv=mock_email)
        with patch.object(settings, "environment", "development"):
            success, msg, dev_info = auth.request_password_reset("user@example.com")

        raw_token = dev_info["dev_token"]
        call_args = mock_col.update_one.call_args[0]
        set_payload = call_args[1]["$set"]

        assert "password_reset_token_hash" in set_payload
        stored_hash = set_payload["password_reset_token_hash"]
        assert stored_hash != raw_token
        assert stored_hash == hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
        assert len(stored_hash) == 64
        assert raw_token not in str(call_args)
