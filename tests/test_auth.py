"""
tests/test_auth.py
Unit tests for authentication, password hashing, and user management.
Tests run completely in isolation using mocked database services.
"""
import hashlib
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest
from bson import ObjectId

from config.settings import settings
from models.schemas import (
    PasswordChange,
    PasswordResetConfirm,
    PasswordResetRequest,
    User,
    UserLogin,
    UserProfileUpdate,
    UserRegistration,
)
from services.auth_service import AuthService
from services.email_service import EmailService
from services.mongo_service import DatabaseUnavailableError


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def mock_db_service():
    """Create a mock MongoService."""
    mock = MagicMock()
    mock.is_connected = True
    return mock


@pytest.fixture
def mock_email_service():
    """Create a mock EmailService."""
    mock = MagicMock()
    mock.is_configured = True
    mock.send_password_reset_email.return_value = (True, "Password reset email sent successfully.")
    return mock


@pytest.fixture
def auth_service(mock_db_service, mock_email_service):
    """Create an AuthService instance with mock DB and mock email service."""
    return AuthService(db_service=mock_db_service, email_srv=mock_email_service)



# ── Password Hashing & Verification Tests ─────────────────────────────────────

class TestPasswordHashing:
    def test_hash_password_generates_bcrypt_hash(self):
        password = "SecurePassword123!"
        hashed = AuthService.hash_password(password)

        assert hashed != password
        assert hashed.startswith("$2b$") or hashed.startswith("$2a$")

    def test_hash_password_unique_salts(self):
        password = "SecurePassword123!"
        h1 = AuthService.hash_password(password)
        h2 = AuthService.hash_password(password)

        assert h1 != h2
        assert AuthService.verify_password(password, h1)
        assert AuthService.verify_password(password, h2)

    def test_verify_password_correct(self):
        password = "MyP@ssw0rd!2026"
        hashed = AuthService.hash_password(password)
        assert AuthService.verify_password(password, hashed) is True

    def test_verify_password_incorrect(self):
        password = "MyP@ssw0rd!2026"
        hashed = AuthService.hash_password(password)
        assert AuthService.verify_password("WrongPassword123!", hashed) is False

    def test_verify_password_invalid_hash_safe(self):
        assert AuthService.verify_password("Password123!", "invalid_hash") is False


# ── Password Strength Validation Tests ────────────────────────────────────────

class TestPasswordStrength:
    def test_strong_password_passes(self):
        valid, err = AuthService.validate_password_strength("Str0ng!Passw0rd")
        assert valid is True
        assert err is None

    def test_too_short_fails(self):
        valid, err = AuthService.validate_password_strength("S1!a")
        assert valid is False
        assert "at least 8 characters" in err

    def test_missing_uppercase_fails(self):
        valid, err = AuthService.validate_password_strength("lowercase123!@#")
        assert valid is False
        assert "uppercase" in err

    def test_missing_lowercase_fails(self):
        valid, err = AuthService.validate_password_strength("UPPERCASE123!@#")
        assert valid is False
        assert "lowercase" in err

    def test_missing_digit_fails(self):
        valid, err = AuthService.validate_password_strength("NoDigitsHere!@#")
        assert valid is False
        assert "number" in err

    def test_missing_special_fails(self):
        valid, err = AuthService.validate_password_strength("NoSpecialChar123")
        assert valid is False
        assert "special character" in err


# ── User Registration Tests ───────────────────────────────────────────────────

class TestUserRegistration:
    def test_register_success(self, auth_service, mock_db_service):
        mock_collection = MagicMock()
        mock_collection.find_one.return_value = None
        fake_id = ObjectId()
        mock_collection.insert_one.return_value = MagicMock(inserted_id=fake_id)
        mock_db_service.get_users_collection.return_value = mock_collection

        reg_data = UserRegistration(
            full_name="Alice Developer",
            username="alice_dev",
            email="alice@example.com",
            password="Str0ng!Password123",
            confirm_password="Str0ng!Password123",
        )

        success, msg, user = auth_service.register_user(reg_data)

        assert success is True
        assert "successful" in msg.lower()
        assert user is not None
        assert user.email == "alice@example.com"
        assert user.username == "alice_dev"
        assert user.id == str(fake_id)
        mock_collection.insert_one.assert_called_once()

    def test_register_duplicate_email(self, auth_service, mock_db_service):
        mock_collection = MagicMock()
        mock_collection.find_one.return_value = {"email": "existing@example.com", "username": "other"}
        mock_db_service.get_users_collection.return_value = mock_collection

        reg_data = UserRegistration(
            full_name="Alice Developer",
            username="alice_dev",
            email="existing@example.com",
            password="Str0ng!Password123",
            confirm_password="Str0ng!Password123",
        )

        success, msg, user = auth_service.register_user(reg_data)

        assert success is False
        assert "email" in msg.lower()
        assert user is None

    def test_register_duplicate_username(self, auth_service, mock_db_service):
        mock_collection = MagicMock()
        mock_collection.find_one.side_effect = [None, {"username": "alice_dev"}]
        mock_db_service.get_users_collection.return_value = mock_collection

        reg_data = UserRegistration(
            full_name="Alice Developer",
            username="alice_dev",
            email="alice@example.com",
            password="Str0ng!Password123",
            confirm_password="Str0ng!Password123",
        )

        success, msg, user = auth_service.register_user(reg_data)

        assert success is False
        assert "username" in msg.lower()
        assert user is None

    def test_register_password_mismatch(self, auth_service):
        reg_data = UserRegistration(
            full_name="Alice Developer",
            username="alice_dev",
            email="alice@example.com",
            password="Str0ng!Password123",
            confirm_password="DifferentPassword123!",
        )

        success, msg, user = auth_service.register_user(reg_data)
        assert success is False
        assert "match" in msg.lower()
        assert user is None

    def test_register_weak_password(self, auth_service):
        reg_data = UserRegistration(
            full_name="Alice Developer",
            username="alice_dev",
            email="alice@example.com",
            password="weak",
            confirm_password="weak",
        )

        success, msg, user = auth_service.register_user(reg_data)
        assert success is False
        assert user is None

    def test_register_database_unavailable(self, auth_service, mock_db_service):
        mock_db_service.get_users_collection.side_effect = DatabaseUnavailableError("MongoDB is unavailable.")

        reg_data = UserRegistration(
            full_name="Alice Developer",
            username="alice_dev",
            email="alice@example.com",
            password="Str0ng!Password123",
            confirm_password="Str0ng!Password123",
        )

        success, msg, user = auth_service.register_user(reg_data)
        assert success is False
        assert "unavailable" in msg.lower()
        assert user is None


# ── User Authentication (Login) Tests ─────────────────────────────────────────

class TestUserAuthentication:
    def test_authenticate_success(self, auth_service, mock_db_service):
        password = "Str0ng!Password123"
        hashed = AuthService.hash_password(password)
        fake_id = ObjectId()
        user_doc = {
            "_id": fake_id,
            "email": "alice@example.com",
            "username": "alice_dev",
            "full_name": "Alice Developer",
            "password_hash": hashed,
            "is_active": True,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        mock_collection = MagicMock()
        mock_collection.find_one.return_value = user_doc
        mock_db_service.get_users_collection.return_value = mock_collection

        req = UserLogin(email_or_username="alice@example.com", password=password)
        success, msg, user = auth_service.login_user(req)

        assert success is True
        assert "successful" in msg.lower()
        assert user is not None
        assert user.email == "alice@example.com"
        assert user.id == str(fake_id)

    def test_authenticate_wrong_password(self, auth_service, mock_db_service):
        hashed = AuthService.hash_password("CorrectPassword123!")
        user_doc = {
            "_id": ObjectId(),
            "email": "alice@example.com",
            "username": "alice_dev",
            "full_name": "Alice Developer",
            "password_hash": hashed,
            "is_active": True,
        }

        mock_collection = MagicMock()
        mock_collection.find_one.return_value = user_doc
        mock_db_service.get_users_collection.return_value = mock_collection

        req = UserLogin(email_or_username="alice@example.com", password="WrongPassword123!")
        success, msg, user = auth_service.login_user(req)

        assert success is False
        assert "invalid" in msg.lower()
        assert user is None

    def test_authenticate_user_not_found(self, auth_service, mock_db_service):
        mock_collection = MagicMock()
        mock_collection.find_one.return_value = None
        mock_db_service.get_users_collection.return_value = mock_collection

        req = UserLogin(email_or_username="nonexistent@example.com", password="Password123!")
        success, msg, user = auth_service.login_user(req)

        assert success is False
        assert "invalid" in msg.lower()
        assert user is None

    def test_authenticate_disabled_account(self, auth_service, mock_db_service):
        password = "Str0ng!Password123"
        hashed = AuthService.hash_password(password)
        user_doc = {
            "_id": ObjectId(),
            "email": "alice@example.com",
            "username": "alice_dev",
            "full_name": "Alice Developer",
            "password_hash": hashed,
            "is_active": False,
        }

        mock_collection = MagicMock()
        mock_collection.find_one.return_value = user_doc
        mock_db_service.get_users_collection.return_value = mock_collection

        req = UserLogin(email_or_username="alice@example.com", password=password)
        success, msg, user = auth_service.login_user(req)

        assert success is False
        assert "disabled" in msg.lower()
        assert user is None


# ── Profile & Password Management Tests ───────────────────────────────────────

class TestProfileAndPasswordManagement:
    def test_update_profile_success(self, auth_service, mock_db_service):
        user_id = str(ObjectId())
        mock_collection = MagicMock()
        mock_collection.find_one.side_effect = [
            {"_id": ObjectId(user_id), "username": "alice_old", "email": "alice@example.com"},  # current_doc
            None,  # uniqueness check: no other user has alice_new
        ]
        mock_db_service.get_users_collection.return_value = mock_collection

        update_req = UserProfileUpdate(full_name="Alice New Name", username="alice_new")
        success, msg, updated_user = auth_service.update_profile(user_id, update_req)

        assert success is True
        assert updated_user is not None
        assert updated_user.full_name == "Alice New Name"
        assert updated_user.username == "alice_new"

    def test_change_password_success(self, auth_service, mock_db_service):
        user_id = str(ObjectId())
        old_password = "OldPassword123!"
        new_password = "NewPassword123!"
        hashed_old = AuthService.hash_password(old_password)

        mock_collection = MagicMock()
        mock_collection.find_one.return_value = {
            "_id": ObjectId(user_id),
            "email": "alice@example.com",
            "password_hash": hashed_old,
        }
        mock_db_service.get_users_collection.return_value = mock_collection

        req = PasswordChange(
            current_password=old_password,
            new_password=new_password,
            confirm_new_password=new_password,
        )
        success, msg = auth_service.change_password(user_id, req)

        assert success is True
        assert "successfully" in msg.lower()
        mock_collection.update_one.assert_called_once()

    def test_change_password_wrong_current(self, auth_service, mock_db_service):
        user_id = str(ObjectId())
        hashed_old = AuthService.hash_password("RealOldPassword123!")

        mock_collection = MagicMock()
        mock_collection.find_one.return_value = {
            "_id": ObjectId(user_id),
            "email": "alice@example.com",
            "password_hash": hashed_old,
        }
        mock_db_service.get_users_collection.return_value = mock_collection

        new_password = "NewPassword123!"
        req = PasswordChange(
            current_password="WrongOldPassword123!",
            new_password=new_password,
            confirm_new_password=new_password,
        )
        success, msg = auth_service.change_password(user_id, req)

        assert success is False
        assert "current password" in msg.lower()
        mock_collection.update_one.assert_not_called()


# ── Registration Flow Isolation Tests ─────────────────────────────────────────

class TestRegistrationFlowIsolation:
    def test_registration_does_not_authenticate_user(self, auth_service, mock_db_service):
        """
        Verify that registering a user only inserts the user record into the database,
        and does NOT set authentication state or log the user in automatically.
        """
        mock_collection = MagicMock()
        mock_collection.find_one.return_value = None
        fake_id = ObjectId()
        mock_collection.insert_one.return_value = MagicMock(inserted_id=fake_id)
        mock_db_service.get_users_collection.return_value = mock_collection

        reg_data = UserRegistration(
            full_name="Bob Developer",
            username="bob_dev",
            email="bob@example.com",
            password="Str0ng!Password123",
            confirm_password="Str0ng!Password123",
        )

        success, msg, user = auth_service.register_user(reg_data)

        assert success is True
        assert "account created successfully" in msg.lower()
        assert user is not None
        assert user.username == "bob_dev"
        # The user object is returned for ID reference, but no authenticated session is created
        mock_collection.insert_one.assert_called_once()
        inserted_doc = mock_collection.insert_one.call_args[0][0]
        # Password must be hashed with bcrypt, NEVER plaintext
        assert inserted_doc["password_hash"] != "Str0ng!Password123"
        assert inserted_doc["password_hash"].startswith("$2b$")
        assert "password" not in inserted_doc


# ── Forgot Password & Reset Token Tests ───────────────────────────────────────

class TestForgotPasswordAndReset:
    def test_request_reset_existing_user(self, auth_service, mock_db_service, mock_email_service):
        """
        When an existing user requests a password reset:
        1. A cryptographically secure random token is generated.
        2. Its SHA-256 hash is saved to MongoDB (raw token is NEVER saved).
        3. Expiration time is stored.
        4. Reset email is sent.
        5. Generic success message is returned to prevent account enumeration.
        """
        user_id = ObjectId()
        user_doc = {
            "_id": user_id,
            "email": "alice@example.com",
            "username": "alice_dev",
            "full_name": "Alice Developer",
            "password_hash": "$2b$12$somehash",
            "is_active": True,
        }
        mock_collection = MagicMock()
        mock_collection.find_one.return_value = user_doc
        mock_db_service.get_users_collection.return_value = mock_collection

        success, message, dev_info = auth_service.request_password_reset("alice@example.com")

        assert success is True
        assert "If an account exists for this email, a password reset link has been sent." in message
        mock_collection.update_one.assert_called_once()

        # Inspect the database update
        call_args = mock_collection.update_one.call_args
        filter_dict = call_args[0][0]
        update_dict = call_args[0][1]["$set"]

        assert filter_dict == {"_id": user_id}
        assert "password_reset_token_hash" in update_dict
        token_hash = update_dict["password_reset_token_hash"]
        # SHA-256 hex digest is exactly 64 characters
        assert len(token_hash) == 64
        assert update_dict["password_reset_used"] is False
        assert "password_reset_expires_at" in update_dict

        # Email service must be dispatched
        mock_email_service.send_password_reset_email.assert_called_once()
        email_args = mock_email_service.send_password_reset_email.call_args[1]
        assert email_args["to_email"] == "alice@example.com"
        assert "reset_token=" in email_args["reset_link"]

    def test_request_reset_nonexistent_user_prevents_enumeration(
        self, auth_service, mock_db_service, mock_email_service
    ):
        """
        When a non-registered email requests a password reset:
        - Return the identical generic success message.
        - Do not dispatch an email.
        - Do not update any database records.
        """
        mock_collection = MagicMock()
        mock_collection.find_one.return_value = None
        mock_db_service.get_users_collection.return_value = mock_collection

        success, message, dev_info = auth_service.request_password_reset("ghost@example.com")

        assert success is True
        assert "If an account exists for this email, a password reset link has been sent." in message
        mock_collection.update_one.assert_not_called()
        mock_email_service.send_password_reset_email.assert_not_called()
        assert dev_info is None

    def test_request_reset_invalid_email_format(self, auth_service):
        success, message, dev_info = auth_service.request_password_reset("not-an-email")
        assert success is False
        assert "valid email" in message.lower()
        assert dev_info is None

    def test_verify_reset_token_valid(self, auth_service, mock_db_service):
        raw_token = "secure_test_token_1234567890abcdef"
        token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
        future_iso = (datetime.now(timezone.utc) + timedelta(minutes=30)).isoformat()
        user_id = ObjectId()

        user_doc = {
            "_id": user_id,
            "email": "alice@example.com",
            "username": "alice_dev",
            "password_reset_token_hash": token_hash,
            "password_reset_expires_at": future_iso,
            "password_reset_used": False,
        }

        mock_collection = MagicMock()
        mock_collection.find_one.return_value = user_doc
        mock_db_service.get_users_collection.return_value = mock_collection

        valid, msg, user_info = auth_service.verify_reset_token(raw_token)

        assert valid is True
        assert "valid" in msg.lower()
        assert user_info is not None
        assert user_info["user_id"] == str(user_id)
        assert user_info["email"] == "alice@example.com"

    def test_verify_reset_token_expired(self, auth_service, mock_db_service):
        raw_token = "expired_token_123"
        token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
        past_iso = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()

        user_doc = {
            "_id": ObjectId(),
            "email": "alice@example.com",
            "password_reset_token_hash": token_hash,
            "password_reset_expires_at": past_iso,
            "password_reset_used": False,
        }

        mock_collection = MagicMock()
        mock_collection.find_one.return_value = user_doc
        mock_db_service.get_users_collection.return_value = mock_collection

        valid, msg, user_info = auth_service.verify_reset_token(raw_token)

        assert valid is False
        assert "expired" in msg.lower()
        assert user_info is None

    def test_verify_reset_token_already_used(self, auth_service, mock_db_service):
        raw_token = "used_token_123"
        token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
        future_iso = (datetime.now(timezone.utc) + timedelta(minutes=30)).isoformat()

        user_doc = {
            "_id": ObjectId(),
            "email": "alice@example.com",
            "password_reset_token_hash": token_hash,
            "password_reset_expires_at": future_iso,
            "password_reset_used": True,
        }

        mock_collection = MagicMock()
        mock_collection.find_one.return_value = user_doc
        mock_db_service.get_users_collection.return_value = mock_collection

        valid, msg, user_info = auth_service.verify_reset_token(raw_token)

        assert valid is False
        assert "already been used" in msg.lower()
        assert user_info is None

    def test_verify_reset_token_invalid_hash(self, auth_service, mock_db_service):
        mock_collection = MagicMock()
        mock_collection.find_one.return_value = None
        mock_db_service.get_users_collection.return_value = mock_collection

        valid, msg, user_info = auth_service.verify_reset_token("nonexistent_token")

        assert valid is False
        assert "invalid or expired" in msg.lower()
        assert user_info is None

    def test_reset_password_mismatched_confirmation(self, auth_service):
        success, msg = auth_service.reset_password(
            token="token123",
            new_password="NewPassword123!",
            confirm_new_password="DifferentPassword123!",
        )
        assert success is False
        assert "do not match" in msg.lower()

    def test_reset_password_weak_password(self, auth_service):
        success, msg = auth_service.reset_password(
            token="token123",
            new_password="weak",
            confirm_new_password="weak",
        )
        assert success is False
        assert "at least 8 characters" in msg.lower()

    def test_reset_password_success_and_token_invalidation(self, auth_service, mock_db_service):
        """
        Verify that resetting the password:
        1. Hashes the new password with bcrypt.
        2. Sets password_reset_used = True.
        3. Clears password_reset_token_hash and password_reset_expires_at.
        4. Makes the token immediately invalid for any subsequent attempt.
        """
        raw_token = "valid_reset_token_xyz"
        token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
        future_iso = (datetime.now(timezone.utc) + timedelta(minutes=30)).isoformat()
        user_id = ObjectId()

        user_doc = {
            "_id": user_id,
            "email": "alice@example.com",
            "username": "alice_dev",
            "password_reset_token_hash": token_hash,
            "password_reset_expires_at": future_iso,
            "password_reset_used": False,
        }

        mock_collection = MagicMock()
        mock_collection.find_one.return_value = user_doc
        mock_collection.update_one.return_value = MagicMock(modified_count=1)
        mock_db_service.get_users_collection.return_value = mock_collection

        new_password = "BrandNewPassword123!"
        success, msg = auth_service.reset_password(
            token=raw_token,
            new_password=new_password,
            confirm_new_password=new_password,
        )

        assert success is True
        assert "password reset successfully" in msg.lower()
        mock_collection.update_one.assert_called_once()

        # Check atomic update payload
        call_args = mock_collection.update_one.call_args
        filter_dict = call_args[0][0]
        set_dict = call_args[0][1]["$set"]

        assert filter_dict["_id"] == user_id
        assert filter_dict["password_reset_token_hash"] == token_hash
        assert filter_dict["password_reset_used"] is False

        # Token must be invalidated
        assert set_dict["password_reset_used"] is True
        assert set_dict["password_reset_token_hash"] is None
        assert set_dict["password_reset_expires_at"] is None

        # New password must be hashed with bcrypt
        assert set_dict["password_hash"] != new_password
        assert set_dict["password_hash"].startswith("$2b$")
        assert AuthService.verify_password(new_password, set_dict["password_hash"])

    def test_reset_password_cannot_be_reused(self, auth_service, mock_db_service):
        """
        If a token was already marked used in MongoDB, update_one matches 0 documents
        and reset_password returns failure.
        """
        raw_token = "valid_token_but_already_modified"
        token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
        future_iso = (datetime.now(timezone.utc) + timedelta(minutes=30)).isoformat()
        user_id = ObjectId()

        user_doc = {
            "_id": user_id,
            "email": "alice@example.com",
            "password_reset_token_hash": token_hash,
            "password_reset_expires_at": future_iso,
            "password_reset_used": False,
        }

        mock_collection = MagicMock()
        mock_collection.find_one.return_value = user_doc
        # Simulate race condition or already consumed token
        mock_collection.update_one.return_value = MagicMock(modified_count=0)
        mock_db_service.get_users_collection.return_value = mock_collection

        new_password = "BrandNewPassword123!"
        success, msg = auth_service.reset_password(
            token=raw_token,
            new_password=new_password,
            confirm_new_password=new_password,
        )

        assert success is False
        assert "already been used or has expired" in msg.lower()

    def test_dev_mode_unconfigured_smtp_returns_dev_token_only(
        self, auth_service, mock_db_service, mock_email_service
    ):
        """
        When SMTP is unconfigured in development:
        - Return honest warning message (never claim email was sent)
        - Return 'dev_token' ONLY for in-memory UI transition
        - Never expose raw reset URLs or links in dev_info
        """
        user_id = ObjectId()
        user_doc = {
            "_id": user_id,
            "email": "alice@example.com",
            "username": "alice_dev",
            "password_hash": "$2b$12$somehash",
            "is_active": True,
        }
        mock_collection = MagicMock()
        mock_collection.find_one.return_value = user_doc
        mock_db_service.get_users_collection.return_value = mock_collection

        # Simulate SMTP unconfigured
        mock_email_service.is_configured = False

        with patch.object(settings, "environment", "development"):
            success, msg, dev_info = auth_service.request_password_reset("alice@example.com")

        assert success is False
        assert "Password reset email is not configured in this environment." in msg
        assert dev_info is not None
        assert "dev_token" in dev_info
        assert "dev_reset_url" not in dev_info  # Raw URL must NEVER be exposed
        assert bool(dev_info["dev_token"]) is True
        mock_collection.update_one.assert_called_once()

    def test_production_mode_unconfigured_smtp_hides_dev_token(
        self, auth_service, mock_db_service, mock_email_service
    ):
        """
        In production environment when SMTP is unconfigured:
        - Return honest warning message
        - Strictly return None for dev_info (no tokens or dev actions)
        """
        user_id = ObjectId()
        user_doc = {
            "_id": user_id,
            "email": "alice@example.com",
            "username": "alice_dev",
            "password_hash": "$2b$12$somehash",
            "is_active": True,
        }
        mock_collection = MagicMock()
        mock_collection.find_one.return_value = user_doc
        mock_db_service.get_users_collection.return_value = mock_collection

        mock_email_service.is_configured = False

        with patch.object(settings, "environment", "production"):
            success, msg, dev_info = auth_service.request_password_reset("alice@example.com")

        assert success is False
        assert "Password reset email is not configured in this environment." in msg
        assert dev_info is None
        mock_collection.update_one.assert_not_called()

    def test_smtp_configured_sending_failure(
        self, auth_service, mock_db_service, mock_email_service
    ):
        """
        When SMTP is configured but email delivery fails:
        - Return error message: 'Unable to deliver password reset email. Please try again later.'
        - dev_info must be None
        """
        user_id = ObjectId()
        user_doc = {
            "_id": user_id,
            "email": "alice@example.com",
            "username": "alice_dev",
            "password_hash": "$2b$12$somehash",
            "is_active": True,
        }
        mock_collection = MagicMock()
        mock_collection.find_one.return_value = user_doc
        mock_db_service.get_users_collection.return_value = mock_collection

        mock_email_service.is_configured = True
        mock_email_service.send_password_reset_email.return_value = (False, "SMTP auth failure")

        success, msg, dev_info = auth_service.request_password_reset("alice@example.com")

        assert success is False
        assert "Unable to deliver password reset email. Please try again later." in msg
        assert dev_info is None


# ── Email Service Unit Tests ──────────────────────────────────────────────────

class TestEmailServiceUnit:
    def test_email_service_unconfigured_smtp(self):
        email_svc = EmailService()
        with patch.object(settings, "smtp_host", ""):
            success, msg = email_svc.send_password_reset_email(
                to_email="test@example.com",
                user_name="Tester",
                reset_link="http://localhost:8501/?reset_token=xyz",
            )
            assert success is False
            assert "not configured" in msg.lower()

    def test_email_service_invalid_recipient(self):
        email_svc = EmailService()
        success, msg = email_svc.send_password_reset_email(
            to_email="invalid-email",
            user_name="Tester",
            reset_link="http://localhost:8501/?reset_token=xyz",
        )
        assert success is False
        assert "invalid recipient" in msg.lower()

    def test_email_service_sends_email_with_smtp_mock(self):
        email_svc = EmailService()
        with patch.object(settings, "smtp_host", "smtp.test.com"), \
             patch.object(settings, "smtp_port", 587), \
             patch.object(settings, "smtp_username", "testuser"), \
             patch.object(settings, "smtp_password", "secretpwd"), \
             patch.object(settings, "smtp_use_tls", True), \
             patch("smtplib.SMTP") as mock_smtp_class:

            mock_server = MagicMock()
            mock_smtp_class.return_value.__enter__.return_value = mock_server

            success, msg = email_svc.send_password_reset_email(
                to_email="user@example.com",
                user_name="Alice",
                reset_link="http://localhost:8501/?reset_token=tok123",
                expiry_minutes=30,
            )

            assert success is True
            assert "sent successfully" in msg.lower()
            mock_server.starttls.assert_called_once()
            mock_server.login.assert_called_once_with("testuser", "secretpwd")
            mock_server.send_message.assert_called_once()
            sent_msg = mock_server.send_message.call_args[0][0]
            assert sent_msg["Subject"] == "Reset your AI Coding Assistant password"
            assert sent_msg["To"] == "user@example.com"

