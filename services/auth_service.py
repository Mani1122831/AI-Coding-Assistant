"""
services/auth_service.py

Authentication and user account service for AI Coding Assistant.
Handles secure bcrypt password hashing, policy verification, user registration,
credential validation, and profile management backed by MongoDB Atlas.
"""
from __future__ import annotations

import hashlib
import re
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Tuple

import bcrypt
from bson import ObjectId
from pymongo.errors import (
    AutoReconnect,
    ConnectionFailure,
    DuplicateKeyError,
    OperationFailure,
    PyMongoError,
    ServerSelectionTimeoutError,
)

from config.settings import settings
from models.schemas import (
    PasswordChange,
    User,
    UserLogin,
    UserProfileUpdate,
    UserRegistration,
)
from services.email_service import email_service
from services.mongo_service import DatabaseUnavailableError, MongoService, mongo_service
from utils.logger import get_logger

logger = get_logger(__name__)

# Password complexity regex rules
_UPPERCASE_RE = re.compile(r"[A-Z]")
_LOWERCASE_RE = re.compile(r"[a-z]")
_DIGIT_RE = re.compile(r"\d")
_SPECIAL_RE = re.compile(r'[!@#$%^&*(),.?":{}|<>_\-+=\[\]\\/`~]')
_USERNAME_RE = re.compile(r"^[a-zA-Z0-9_-]{3,30}$")
_EMAIL_RE = re.compile(r"^[\w\.-]+@[\w\.-]+\.\w+$")


class AuthService:
    """
    Manages user authentication, bcrypt password hashing, and user accounts in MongoDB.
    """

    def __init__(
        self,
        db_service: Optional[MongoService] = None,
        email_srv: Optional[Any] = None,
    ) -> None:
        self._db_service = db_service or mongo_service
        self._email_service = email_srv or email_service

    # ── Password Hashing & Verification ────────────────────────────────────────

    @staticmethod
    def hash_password(password: str) -> str:
        """
        Hash a plaintext password using bcrypt with a generated salt.
        Never logs or stores the plaintext password.
        """
        salt = bcrypt.gensalt(rounds=12)
        hashed = bcrypt.hashpw(password.encode("utf-8"), salt)
        return hashed.decode("utf-8")

    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """
        Verify a plaintext password against a stored bcrypt hash.
        """
        try:
            return bcrypt.checkpw(
                plain_password.encode("utf-8"),
                hashed_password.encode("utf-8"),
            )
        except Exception as exc:
            logger.warning("Password verification exception: %s", exc)
            return False

    @staticmethod
    def validate_password_strength(password: str) -> Tuple[bool, Optional[str]]:
        """
        Validate that the password satisfies minimum security requirements:
        - At least 8 characters
        - At least one uppercase letter
        - At least one lowercase letter
        - At least one number
        - At least one special character
        """
        if len(password) < 8:
            return False, "Password must be at least 8 characters long."
        if not _UPPERCASE_RE.search(password):
            return False, "Password must contain at least one uppercase letter (A-Z)."
        if not _LOWERCASE_RE.search(password):
            return False, "Password must contain at least one lowercase letter (a-z)."
        if not _DIGIT_RE.search(password):
            return False, "Password must contain at least one number (0-9)."
        if not _SPECIAL_RE.search(password):
            return False, "Password must contain at least one special character (!@#$%^&*...)."
        return True, None

    # ── Registration ───────────────────────────────────────────────────────────

    def register_user(self, req: UserRegistration) -> Tuple[bool, str, Optional[User]]:
        """
        Register a new user account in MongoDB.

        Returns:
            Tuple of (success: bool, message: str, user: Optional[User])
        """
        # 1. Basic field presence checks
        full_name = req.full_name.strip()
        username = req.username.strip().lower()
        email = req.email.strip().lower()

        if not full_name:
            return False, "Invalid registration data: Full name is required.", None
        if not username:
            return False, "Invalid registration data: Username is required.", None
        if not email:
            return False, "Invalid registration data: Email address is required.", None

        # 2. Format validation
        if not _USERNAME_RE.match(username):
            return (
                False,
                "Invalid registration data: Username must be 3-30 characters with only letters, numbers, hyphens, or underscores.",
                None,
            )

        if not _EMAIL_RE.match(email):
            return False, "Invalid registration data: Please provide a valid email address.", None

        # 3. Password matching and strength
        if req.password != req.confirm_password:
            return False, "Invalid registration data: Passwords do not match.", None

        valid_pwd, pwd_error = self.validate_password_strength(req.password)
        if not valid_pwd:
            return False, f"Invalid registration data: {pwd_error}", None

        # 4. Check database availability and duplicate accounts
        try:
            users_col = self._db_service.get_users_collection()
        except DatabaseUnavailableError as exc:
            return False, f"MongoDB unavailable: {exc}", None
        except Exception as exc:
            logger.error("Database connection error during registration: %s", exc)
            return False, "MongoDB unavailable: Could not connect to the database. Please verify your connection.", None

        try:
            # Check existing email
            if users_col.find_one({"email": email}):
                return False, "Email already exists. Please log in or use another email address.", None

            # Check existing username
            if users_col.find_one({"username": username}):
                return False, "Username already exists. Please choose another username.", None

            # 5. Hash password and insert user record
            now_iso = datetime.now(timezone.utc).isoformat()
            password_hash = self.hash_password(req.password)

            # Security: stored document contains password_hash, NEVER plaintext password
            doc: Dict[str, Any] = {
                "full_name": full_name,
                "username": username,
                "email": email,
                "password_hash": password_hash,
                "created_at": now_iso,
                "updated_at": now_iso,
                "is_active": True,
            }

            result = users_col.insert_one(doc)
            user_id = str(result.inserted_id)

            created_user = User(
                id=user_id,
                full_name=full_name,
                username=username,
                email=email,
                created_at=now_iso,
                updated_at=now_iso,
                is_active=True,
            )
            logger.info("User registered successfully: %s (%s)", username, user_id)
            return True, "Account created successfully! You can now log in.", created_user

        except DuplicateKeyError as exc:
            err_str = str(exc).lower()
            if "email" in err_str:
                return False, "Email already exists. Please log in or use another email address.", None
            if "username" in err_str:
                return False, "Username already exists. Please choose another username.", None
            return False, "Username or email already exists.", None

        except (ServerSelectionTimeoutError, ConnectionFailure, AutoReconnect) as exc:
            err_str = str(exc).lower()
            logger.warning("MongoDB connectivity failure during registration: %s", exc)
            if "tlsv1 alert internal error" in err_str or "ssl handshake failed" in err_str:
                return (
                    False,
                    "MongoDB unavailable: Connection rejected by MongoDB Atlas. Please ensure your current IP address is added to the Atlas Network Access IP allowlist.",
                    None,
                )
            return False, "MongoDB unavailable: Connection timed out. Please check your network and cluster status.", None

        except OperationFailure as exc:
            err_str = str(exc).lower()
            logger.error("MongoDB OperationFailure during registration: %s", exc)
            if "auth" in err_str or "authentication" in err_str:
                return False, "MongoDB unavailable: Authentication failed. Please check your MongoDB user credentials.", None
            return False, "MongoDB unavailable: Database operation was rejected.", None

        except PyMongoError as exc:
            logger.error("PyMongoError during registration: %s", exc)
            return False, "MongoDB unavailable: A database error occurred. Please try again later.", None

        except Exception as exc:
            logger.error("Unexpected error during registration: %s", exc)
            return False, "Authentication/session error: Unable to complete registration. Please try again.", None

    # ── Login ──────────────────────────────────────────────────────────────────

    def login_user(self, req: UserLogin) -> Tuple[bool, str, Optional[User]]:
        """
        Authenticate a user by email or username and password.

        Returns:
            Tuple of (success: bool, message: str, user: Optional[User])
        """
        identifier = req.email_or_username.strip().lower()
        password = req.password

        if not identifier or not password:
            return False, "Please enter both your email/username and password.", None

        try:
            users_col = self._db_service.get_users_collection()
        except DatabaseUnavailableError as exc:
            return False, f"MongoDB unavailable: {exc}", None
        except Exception as exc:
            logger.error("Database connection error during login: %s", exc)
            return False, "MongoDB unavailable: Could not connect to the database. Please verify your connection.", None

        try:
            # Look up by email or username
            doc = users_col.find_one(
                {"$or": [{"email": identifier}, {"username": identifier}]}
            )

            if not doc:
                return False, "Invalid email/username or password.", None

            if not doc.get("is_active", True):
                return False, "This account has been disabled. Please contact support.", None

            stored_hash = doc.get("password_hash", "")
            if not self.verify_password(password, stored_hash):
                return False, "Invalid email/username or password.", None

            user = User(
                id=str(doc["_id"]),
                full_name=doc.get("full_name", ""),
                username=doc.get("username", ""),
                email=doc.get("email", ""),
                created_at=str(doc.get("created_at", "")),
                updated_at=str(doc.get("updated_at", "")),
                is_active=doc.get("is_active", True),
            )
            logger.info("User authenticated: %s (%s)", user.username, user.id)
            return True, "Login successful.", user

        except (ServerSelectionTimeoutError, ConnectionFailure, AutoReconnect) as exc:
            err_str = str(exc).lower()
            logger.warning("MongoDB connectivity failure during login: %s", exc)
            if "tlsv1 alert internal error" in err_str or "ssl handshake failed" in err_str:
                return (
                    False,
                    "MongoDB unavailable: Connection rejected by MongoDB Atlas. Please ensure your current IP address is added to the Atlas Network Access IP allowlist.",
                    None,
                )
            return False, "MongoDB unavailable: Connection timed out. Please check your network and cluster status.", None

        except OperationFailure as exc:
            err_str = str(exc).lower()
            logger.error("MongoDB OperationFailure during login: %s", exc)
            if "auth" in err_str or "authentication" in err_str:
                return False, "MongoDB unavailable: Authentication failed. Please check your database user credentials.", None
            return False, "MongoDB unavailable: Database operation was rejected.", None

        except PyMongoError as exc:
            logger.error("PyMongoError during login: %s", exc)
            return False, "MongoDB unavailable: A database error occurred. Please try again later.", None

        except Exception as exc:
            logger.error("Unexpected error during login: %s", exc)
            return False, "Authentication/session error occurred during login. Please try again.", None

    # ── Profile & Password Management ──────────────────────────────────────────

    def get_user_by_id(self, user_id: str) -> Optional[User]:
        """Fetch user by string ID."""
        try:
            users_col = self._db_service.get_users_collection()
            doc = users_col.find_one({"_id": ObjectId(user_id)})
            if not doc:
                return None
            return User(
                id=str(doc["_id"]),
                full_name=doc.get("full_name", ""),
                username=doc.get("username", ""),
                email=doc.get("email", ""),
                created_at=str(doc.get("created_at", "")),
                updated_at=str(doc.get("updated_at", "")),
                is_active=doc.get("is_active", True),
            )
        except Exception as exc:
            logger.warning("Error fetching user %s: %s", user_id, exc)
            return None

    def update_profile(
        self, user_id: str, req: UserProfileUpdate
    ) -> Tuple[bool, str, Optional[User]]:
        """
        Update user's full name or username.
        """
        full_name = req.full_name.strip()
        new_username = req.username.strip().lower()

        if not full_name:
            return False, "Full name cannot be empty.", None
        if not new_username:
            return False, "Username cannot be empty.", None

        if not _USERNAME_RE.match(new_username):
            return (
                False,
                "Username must be 3-30 characters with only letters, numbers, hyphens, or underscores.",
                None,
            )

        try:
            users_col = self._db_service.get_users_collection()
            obj_id = ObjectId(user_id)

            current_doc = users_col.find_one({"_id": obj_id})
            if not current_doc:
                return False, "User account not found.", None

            # If changing username, ensure uniqueness
            if new_username != current_doc.get("username", "").lower():
                existing = users_col.find_one({"username": new_username, "_id": {"$ne": obj_id}})
                if existing:
                    return False, "This username is already in use.", None

            now_iso = datetime.now(timezone.utc).isoformat()
            users_col.update_one(
                {"_id": obj_id},
                {"$set": {"full_name": full_name, "username": new_username, "updated_at": now_iso}},
            )

            updated_user = User(
                id=user_id,
                full_name=full_name,
                username=new_username,
                email=current_doc.get("email", ""),
                created_at=str(current_doc.get("created_at", "")),
                updated_at=now_iso,
                is_active=current_doc.get("is_active", True),
            )
            return True, "Profile updated successfully.", updated_user

        except DuplicateKeyError:
            return False, "This username is already taken. Please choose another.", None
        except DatabaseUnavailableError as exc:
            return False, f"MongoDB unavailable: {exc}", None
        except (ServerSelectionTimeoutError, ConnectionFailure, AutoReconnect):
            return False, "MongoDB unavailable: Could not reach database to update profile.", None
        except Exception as exc:
            logger.error("Failed to update profile for user %s: %s", user_id, exc)
            return False, "Failed to update profile due to a database error.", None

    def change_password(self, user_id: str, req: PasswordChange) -> Tuple[bool, str]:
        """
        Change user password after verifying the current password and validating strength.
        """
        if not req.current_password:
            return False, "Current password is required."

        if req.new_password != req.confirm_new_password:
            return False, "New password and confirmation do not match."

        valid_pwd, pwd_error = self.validate_password_strength(req.new_password)
        if not valid_pwd:
            return False, pwd_error or "New password does not meet security requirements."

        try:
            users_col = self._db_service.get_users_collection()
            obj_id = ObjectId(user_id)
            doc = users_col.find_one({"_id": obj_id})

            if not doc:
                return False, "User account not found."

            if not self.verify_password(req.current_password, doc.get("password_hash", "")):
                return False, "Incorrect current password."

            # Hash new password
            new_hash = self.hash_password(req.new_password)
            now_iso = datetime.now(timezone.utc).isoformat()

            users_col.update_one(
                {"_id": obj_id},
                {"$set": {"password_hash": new_hash, "updated_at": now_iso}},
            )
            logger.info("Password updated for user %s", user_id)
            return True, "Password changed successfully."

        except DatabaseUnavailableError as exc:
            return False, f"MongoDB unavailable: {exc}"
        except (ServerSelectionTimeoutError, ConnectionFailure, AutoReconnect):
            return False, "MongoDB unavailable: Could not reach database to change password."
        except Exception as exc:
            logger.error("Error changing password for user %s: %s", user_id, exc)
            return False, "Failed to change password due to a database error."

    # ── Forgot Password & Reset Token Management ───────────────────────────────

    @property
    def is_smtp_configured(self) -> bool:
        """Return True if SMTP email delivery is configured."""
        if hasattr(self._email_service, "is_configured"):
            val = getattr(self._email_service, "is_configured")
            return bool(val() if callable(val) else val)
        return settings.is_smtp_configured

    def request_password_reset(
        self, email: str
    ) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        """
        Initiate a password reset flow for the given email address.
        Generates a cryptographically secure token, stores its SHA-256 hash
        and expiration time in MongoDB, and dispatches the reset email via SMTP.

        If SMTP is NOT configured:
          - Does NOT claim an email was sent.
          - Returns an honest notification: "Password reset email is not configured in this environment."
          - In development mode (ENVIRONMENT=development), safely generates the token in MongoDB
            and returns dev_token ONLY for in-memory transition (never displayed in UI).
          - In production mode, returns None for dev_token.

        If SMTP IS configured:
          - If user exists: generates token, updates DB, sends reset email.
          - If email sending succeeds: returns generic success message to prevent account enumeration.
          - If email sending fails: returns delivery error.
          - If user not registered: returns identical generic success message to prevent account enumeration.

        Returns:
            Tuple of:
              - success: bool
              - message: str
              - dev_info: Optional[Dict[str, Any]] (contains 'dev_token' for development in-memory transition only)
        """
        clean_email = email.strip().lower()
        if not clean_email or not _EMAIL_RE.match(clean_email):
            return False, "Please provide a valid email address.", None

        try:
            users_col = self._db_service.get_users_collection()
            user_doc = users_col.find_one({"email": clean_email})
        except DatabaseUnavailableError as exc:
            logger.error("Database unavailable during password reset request: %s", exc)
            return False, "Unable to process password reset. Database is unavailable.", None
        except Exception as exc:
            logger.error("Error connecting to database during password reset request: %s", exc)
            return False, "Unable to connect to the database. Please try again later.", None

        # ── Branch 1: SMTP is NOT configured ────────────────────────────────
        if not self.is_smtp_configured:
            unconfigured_msg = "Password reset email is not configured in this environment."
            # In development mode, safely generate the token in MongoDB so developers can test the reset flow
            if settings.is_development and user_doc:
                raw_token = secrets.token_urlsafe(32)
                token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
                expiry_minutes = settings.password_reset_token_expiry_minutes
                expires_at = datetime.now(timezone.utc) + timedelta(minutes=expiry_minutes)

                try:
                    users_col.update_one(
                        {"_id": user_doc["_id"]},
                        {
                            "$set": {
                                "password_reset_token_hash": token_hash,
                                "password_reset_expires_at": expires_at.isoformat(),
                                "password_reset_used": False,
                                "updated_at": datetime.now(timezone.utc).isoformat(),
                            }
                        },
                    )
                except Exception as exc:
                    logger.error("Failed to store password reset token: %s", exc)
                    return False, "Failed to initiate password reset due to a database error.", None

                return False, unconfigured_msg, {"dev_token": raw_token}

            return False, unconfigured_msg, None

        # ── Branch 2: SMTP IS configured ────────────────────────────────────
        generic_message = (
            "If an account exists for this email, a password reset link has been sent."
        )

        # Account enumeration prevention: return identical success message if user not found
        if not user_doc:
            logger.info("Password reset requested for unregistered email address.")
            return True, generic_message, None

        # Generate cryptographically secure random token (256 bits of entropy)
        raw_token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
        expiry_minutes = settings.password_reset_token_expiry_minutes
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=expiry_minutes)

        try:
            users_col.update_one(
                {"_id": user_doc["_id"]},
                {
                    "$set": {
                        "password_reset_token_hash": token_hash,
                        "password_reset_expires_at": expires_at.isoformat(),
                        "password_reset_used": False,
                        "updated_at": datetime.now(timezone.utc).isoformat(),
                    }
                },
            )
        except Exception as exc:
            logger.error("Failed to store password reset token: %s", exc)
            return False, "Failed to initiate password reset due to a database error.", None

        reset_link = f"{settings.app_base_url.rstrip('/')}/?reset_token={raw_token}"
        user_name = user_doc.get("full_name") or user_doc.get("username") or "Developer"

        email_sent, _ = self._email_service.send_password_reset_email(
            to_email=clean_email,
            user_name=user_name,
            reset_link=reset_link,
            expiry_minutes=expiry_minutes,
        )

        if not email_sent:
            return False, "Unable to deliver password reset email. Please try again later.", None

        return True, generic_message, None

    def verify_reset_token(
        self, raw_token: str
    ) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        """
        Validate whether a raw reset token exists, matches its stored hash,
        is not expired, and has not yet been used.

        Returns:
            Tuple of:
              - valid: bool
              - message: str
              - user_info: Optional[Dict[str, Any]] with user_id, email, username
        """
        if not raw_token or not raw_token.strip():
            return False, "Invalid or missing reset token.", None

        token_hash = hashlib.sha256(raw_token.strip().encode("utf-8")).hexdigest()

        try:
            users_col = self._db_service.get_users_collection()
            user_doc = users_col.find_one({"password_reset_token_hash": token_hash})
        except Exception as exc:
            logger.error("Database error verifying reset token: %s", exc)
            return False, "Unable to verify reset link due to a database error.", None

        if not user_doc:
            return False, "Invalid or expired reset link.", None

        if user_doc.get("password_reset_used", False):
            return False, "This reset link has already been used. Please request a new one.", None

        expires_str = user_doc.get("password_reset_expires_at")
        if not expires_str:
            return False, "Invalid or expired reset link.", None

        try:
            expires_at = datetime.fromisoformat(expires_str)
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            if datetime.now(timezone.utc) > expires_at:
                return False, "This reset link has expired. Please request a new one.", None
        except Exception as exc:
            logger.warning("Error parsing token expiration timestamp: %s", exc)
            return False, "Invalid reset token expiration format.", None

        return True, "Reset token is valid.", {
            "user_id": str(user_doc["_id"]),
            "email": user_doc.get("email", ""),
            "username": user_doc.get("username", ""),
        }

    def reset_password(
        self,
        token: str,
        new_password: str,
        confirm_new_password: str,
    ) -> Tuple[bool, str]:
        """
        Complete password reset:
        1. Validates password equality and strength requirements
        2. Verifies token validity, expiry, and single-use status
        3. Hashes the new password with bcrypt
        4. Updates MongoDB and invalidates the reset token immediately
        """
        if not token or not token.strip():
            return False, "Invalid or missing reset token."

        if not new_password:
            return False, "New password is required."

        if new_password != confirm_new_password:
            return False, "New password and confirmation do not match."

        valid_pwd, pwd_error = self.validate_password_strength(new_password)
        if not valid_pwd:
            return False, pwd_error or "Password does not meet security requirements."

        valid, msg, user_info = self.verify_reset_token(token)
        if not valid or not user_info:
            return False, msg

        token_hash = hashlib.sha256(token.strip().encode("utf-8")).hexdigest()
        new_hash = self.hash_password(new_password)
        now_iso = datetime.now(timezone.utc).isoformat()

        try:
            users_col = self._db_service.get_users_collection()
            # Atomically update password and invalidate reset token
            result = users_col.update_one(
                {
                    "_id": ObjectId(user_info["user_id"]),
                    "password_reset_token_hash": token_hash,
                    "password_reset_used": False,
                },
                {
                    "$set": {
                        "password_hash": new_hash,
                        "password_reset_used": True,
                        "password_reset_token_hash": None,
                        "password_reset_expires_at": None,
                        "updated_at": now_iso,
                    }
                },
            )
            if result.modified_count == 0:
                return False, "This reset link has already been used or has expired."

            logger.info("Password successfully reset for user %s", user_info["user_id"])
            return True, "Password reset successfully. Please log in with your new password."

        except DatabaseUnavailableError as exc:
            return False, f"MongoDB unavailable: {exc}"
        except Exception as exc:
            logger.error("Error resetting password: %s", exc)
            return False, "Failed to reset password due to a database error."


# Singleton instance
auth_service = AuthService()

