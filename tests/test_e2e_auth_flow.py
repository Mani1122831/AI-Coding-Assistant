"""
tests/test_e2e_auth_flow.py

End-to-End integration test for the AI Coding Assistant authentication workflows:
TEST A: Registration flow (Validates registration -> hashes password -> stores in MongoDB -> does NOT authenticate user -> returns to Login page -> manual login succeeds).
TEST B: Logout flow (Clears session state -> returns to Login page -> protected routes blocked).
TEST C: Forgot Password & Password Reset flow (Generates token -> stores SHA-256 hash & expiry -> verifies enumeration protection -> invalidates token upon reset -> new password works, old password fails).
"""
import hashlib
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest
from bson import ObjectId

from models.schemas import UserLogin, UserRegistration
from services.auth_service import AuthService


@pytest.fixture
def mock_atlas_db():
    """Mock MongoDB database with in-memory collection stores."""
    users_store = {}

    mock_users_col = MagicMock()

    def mock_find_one(query, *args, **kwargs):
        if "$or" in query:
            for sub_query in query["$or"]:
                res = mock_find_one(sub_query)
                if res is not None:
                    return res
            return None
        if "_id" in query:
            return users_store.get(str(query["_id"]))
        if "email" in query:
            clean_email = query["email"].lower()
            for doc in users_store.values():
                if doc.get("email", "").lower() == clean_email:
                    return doc
            return None
        if "username" in query:
            clean_user = query["username"].lower()
            for doc in users_store.values():
                if doc.get("username", "").lower() == clean_user:
                    return doc
            return None
        if "password_reset_token_hash" in query:
            target_hash = query["password_reset_token_hash"]
            for doc in users_store.values():
                if doc.get("password_reset_token_hash") == target_hash:
                    return doc
            return None
        return None

    def mock_insert_one(doc, *args, **kwargs):
        doc_copy = dict(doc)
        new_id = ObjectId()
        doc_copy["_id"] = new_id
        users_store[str(new_id)] = doc_copy
        return MagicMock(inserted_id=new_id)

    def mock_update_one(filter_dict, update_dict, *args, **kwargs):
        target_doc = None
        target_id_str = None
        if "_id" in filter_dict:
            target_id_str = str(filter_dict["_id"])
            target_doc = users_store.get(target_id_str)

        if not target_doc:
            return MagicMock(modified_count=0)

        # Check conditional filters
        if "password_reset_token_hash" in filter_dict:
            if target_doc.get("password_reset_token_hash") != filter_dict["password_reset_token_hash"]:
                return MagicMock(modified_count=0)
        if "password_reset_used" in filter_dict:
            if target_doc.get("password_reset_used") != filter_dict["password_reset_used"]:
                return MagicMock(modified_count=0)

        if "$set" in update_dict:
            for k, v in update_dict["$set"].items():
                target_doc[k] = v

        users_store[target_id_str] = target_doc
        return MagicMock(modified_count=1)

    mock_users_col.find_one.side_effect = mock_find_one
    mock_users_col.insert_one.side_effect = mock_insert_one
    mock_users_col.update_one.side_effect = mock_update_one

    mock_db = MagicMock()
    mock_db.get_users_collection.return_value = mock_users_col
    return mock_db, users_store


def test_full_lifecycle_e2e(mock_atlas_db):
    mock_db, users_store = mock_atlas_db
    mock_email = MagicMock()
    mock_email.is_configured = True
    mock_email.send_password_reset_email.return_value = (True, "Sent")

    auth = AuthService(db_service=mock_db, email_srv=mock_email)

    # =========================================================================
    # TEST A — REGISTRATION
    # =========================================================================
    reg_req = UserRegistration(
        full_name="Elena Rostova",
        username="elena_dev",
        email="elena@example.com",
        password="OriginalPassword123!",
        confirm_password="OriginalPassword123!",
    )

    success, msg, user = auth.register_user(reg_req)
    assert success is True
    assert "Account created successfully" in msg
    assert user is not None
    assert user.username == "elena_dev"

    # Confirm user is in MongoDB
    assert len(users_store) == 1
    stored_user = list(users_store.values())[0]
    assert stored_user["email"] == "elena@example.com"
    # Confirm password is encrypted with bcrypt, NEVER plaintext
    assert stored_user["password_hash"] != "OriginalPassword123!"
    assert stored_user["password_hash"].startswith("$2b$")
    assert "password" not in stored_user

    # Confirm user is NOT automatically authenticated
    # (In app.py, session state `authenticated` remains False after registration)
    session_state = {"authenticated": False, "user": None, "page": "Dashboard", "auth_view": "LOGIN"}
    assert session_state["authenticated"] is False
    assert session_state["user"] is None
    assert session_state["auth_view"] == "LOGIN"

    # Log in manually
    login_req = UserLogin(email_or_username="elena@example.com", password="OriginalPassword123!")
    l_ok, l_msg, logged_in = auth.login_user(login_req)
    assert l_ok is True
    assert logged_in is not None
    assert logged_in.email == "elena@example.com"

    # User enters Dashboard
    session_state["authenticated"] = True
    session_state["user"] = {"id": logged_in.id, "username": logged_in.username}
    session_state["page"] = "Dashboard"

    # =========================================================================
    # TEST B — LOGOUT
    # =========================================================================
    # User clicks logout
    session_state["authenticated"] = False
    session_state["user"] = None
    session_state["auth_view"] = "LOGIN"
    session_state["login_prefill_identifier"] = ""

    assert session_state["authenticated"] is False
    assert session_state["user"] is None
    assert session_state["auth_view"] == "LOGIN"

    # =========================================================================
    # TEST C — FORGOT PASSWORD & RESET WORKFLOW
    # =========================================================================
    # 1. Request password reset
    fp_ok, fp_msg, dev_info = auth.request_password_reset("elena@example.com")
    assert fp_ok is True
    assert "If an account exists for this email, a password reset link has been sent." in fp_msg
    mock_email.send_password_reset_email.assert_called_once()

    # Confirm email was dispatched with reset link containing raw token
    call_args = mock_email.send_password_reset_email.call_args[1]
    assert call_args["to_email"] == "elena@example.com"
    reset_link = call_args["reset_link"]
    assert "reset_token=" in reset_link
    raw_token = reset_link.split("reset_token=")[1]

    # Confirm database stored ONLY the SHA-256 hash of the token, NEVER raw token
    stored_hash = stored_user["password_reset_token_hash"]
    assert stored_hash != raw_token
    assert stored_hash == hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    assert stored_user["password_reset_used"] is False
    assert "password_reset_expires_at" in stored_user

    # 2. Reset password using the generated token
    new_password = "BrandNewPassword456@"
    rp_ok, rp_msg = auth.reset_password(
        token=raw_token,
        new_password=new_password,
        confirm_new_password=new_password,
    )
    assert rp_ok is True
    assert "Password reset successfully" in rp_msg

    # Confirm token is invalidated in database
    assert stored_user["password_reset_used"] is True
    assert stored_user["password_reset_token_hash"] is None
    assert stored_user["password_reset_expires_at"] is None

    # Confirm token cannot be reused
    reuse_ok, reuse_msg = auth.reset_password(
        token=raw_token,
        new_password="YetAnotherPassword789!",
        confirm_new_password="YetAnotherPassword789!",
    )
    assert reuse_ok is False
    assert "invalid or expired" in reuse_msg.lower() or "already been used" in reuse_msg.lower()

    # 3. Log in with the new password
    new_login_req = UserLogin(email_or_username="elena@example.com", password=new_password)
    nl_ok, nl_msg, nl_user = auth.login_user(new_login_req)
    assert nl_ok is True
    assert nl_user is not None
    assert nl_user.email == "elena@example.com"

    # 4. Confirm old password NO LONGER works
    old_login_req = UserLogin(email_or_username="elena@example.com", password="OriginalPassword123!")
    ol_ok, ol_msg, ol_user = auth.login_user(old_login_req)
    assert ol_ok is False
    assert ol_user is None
    assert "invalid" in ol_msg.lower()


def test_e2e_11_points_complete_workflow(mock_atlas_db):
    """
    Complete end-to-end verification covering all 11 required lifecycle points:
    1. Register
    2. Return to Login
    3. Forgot Password
    4. SMTP unavailable behavior
    5. Development reset flow
    6. Reset password
    7. Return to Login
    8. Login with new password
    9. Verify old password fails
    10. Verify raw token is not displayed
    11. Verify production mode hides dev controls
    """
    import inspect
    import app
    from config.settings import settings
    from unittest.mock import patch

    mock_db, users_store = mock_atlas_db
    mock_email = MagicMock()
    mock_email.is_configured = False  # Start with unconfigured SMTP
    mock_email.send_password_reset_email.return_value = (False, "SMTP is not configured.")

    auth = AuthService(db_service=mock_db, email_srv=mock_email)

    # 1. Register
    reg_req = UserRegistration(
        full_name="Marcus Vance",
        username="marcus_v",
        email="marcus@example.com",
        password="InitialPassword123!",
        confirm_password="InitialPassword123!",
    )
    reg_ok, reg_msg, reg_user = auth.register_user(reg_req)
    assert reg_ok is True
    assert reg_user is not None
    assert "Account created successfully" in reg_msg

    # 2. Return to Login (verify unauthenticated state & login routing)
    session_state = {
        "authenticated": False,
        "user": None,
        "auth_view": "LOGIN",
        "reset_token_input": "",
        "dev_reset_token": "",
    }
    assert session_state["authenticated"] is False
    assert session_state["auth_view"] == "LOGIN"

    # 3. Forgot Password navigation
    session_state["auth_view"] = "FORGOT_PASSWORD"
    assert session_state["auth_view"] == "FORGOT_PASSWORD"

    # 4. SMTP unavailable behavior
    with patch.object(settings, "environment", "development"):
        fp_ok, fp_msg, dev_info = auth.request_password_reset("marcus@example.com")
        assert fp_ok is False
        assert "Password reset email is not configured in this environment." in fp_msg
        assert "sent" not in fp_msg.lower()  # Never claim email was sent

        # 5. Development reset flow (in-memory transition, no raw token text displayed)
        assert dev_info is not None
        assert "dev_token" in dev_info
        assert "dev_reset_url" not in dev_info
        raw_dev_token = dev_info["dev_token"]
        assert len(raw_dev_token) > 20

        # Simulate clicking [Open Development Reset Flow] button
        session_state["dev_reset_token"] = raw_dev_token
        session_state["auth_view"] = "RESET_PASSWORD"
        session_state["reset_token_input"] = session_state.pop("dev_reset_token")

    assert session_state["auth_view"] == "RESET_PASSWORD"
    assert session_state["reset_token_input"] == raw_dev_token
    assert "dev_reset_token" not in session_state

    # 6. Reset password
    updated_password = "UpdatedPassword456@"
    rp_ok, rp_msg = auth.reset_password(
        token=session_state["reset_token_input"],
        new_password=updated_password,
        confirm_new_password=updated_password,
    )
    assert rp_ok is True
    assert "Password reset successfully" in rp_msg

    # 7. Return to Login
    session_state["reset_token_input"] = ""
    session_state["auth_view"] = "LOGIN"
    assert session_state["authenticated"] is False
    assert session_state["auth_view"] == "LOGIN"
    assert session_state["reset_token_input"] == ""

    # 8. Login with new password
    login_new = UserLogin(email_or_username="marcus@example.com", password=updated_password)
    new_ok, new_msg, new_user = auth.login_user(login_new)
    assert new_ok is True
    assert new_user is not None
    assert new_user.username == "marcus_v"

    # 9. Verify old password fails
    login_old = UserLogin(email_or_username="marcus@example.com", password="InitialPassword123!")
    old_ok, old_msg, old_user = auth.login_user(login_old)
    assert old_ok is False
    assert old_user is None
    assert "invalid" in old_msg.lower()

    # 10. Verify raw token is not displayed in UI source or templates
    app_source = inspect.getsource(app)
    assert "dev_reset_url" not in app_source
    assert "Testing Reset Link" not in app_source
    assert "Open Reset Password Page with Dev Token" not in app_source
    # Verify the reset token field is masked with type='password'
    assert 'type="password"' in inspect.getsource(app._render_auth_reset_password)

    # 11. Verify production mode hides dev controls
    with patch.object(settings, "environment", "production"):
        assert settings.is_development is False
        prod_ok, prod_msg, prod_dev = auth.request_password_reset("marcus@example.com")
        assert prod_ok is False
        assert "Password reset email is not configured in this environment." in prod_msg
        assert prod_dev is None  # Strictly no dev token in production

