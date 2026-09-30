"""
app.py
AI Coding Assistant — Streamlit application entry point with secure authentication,
MongoDB Atlas persistence, user profile, coding history, activity audit logging,
and multi-feature AI coding tools powered by Google Gemini.
"""
from __future__ import annotations

import streamlit as st

# ── Page config (must be first Streamlit call) ────────────────────────────────
st.set_page_config(
    page_title="AI Coding Assistant",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Imports (after page config) ────────────────────────────────────────────────
from typing import Any, Dict, Optional

from config.settings import settings
from models.schemas import (
    ChatMessage,
    ChatRequest,
    CodeGenerationRequest,
    ConvertRequest,
    DebugRequest,
    ExplainRequest,
    PasswordChange,
    PasswordResetConfirm,
    PasswordResetRequest,
    RefactorRequest,
    SecurityRequest,
    TestGenerationRequest,
    User,
    UserLogin,
    UserProfileUpdate,
    UserRegistration,
)
from services.activity_service import activity_service
from services.auth_service import auth_service
from services.code_service import CodeService
from services.file_service import FileService
from services.history_service import history_service
from services.llm_service import LLMService, RECOMMENDED_MODELS
from services.mongo_service import mongo_service
from services.security_service import SecurityService
from utils.helpers import build_language_list, format_file_size

# ── Custom CSS ─────────────────────────────────────────────────────────────────

def _inject_css() -> None:
    st.markdown(
        """
        <style>
        /* ── Base Theme ── */
        .stApp { background-color: #0e1117; }

        /* ── Sidebar ── */
        [data-testid="stSidebar"] {
            background-color: #161b22;
            border-right: 1px solid #30363d;
        }
        [data-testid="stSidebar"] .stMarkdown h1 {
            color: #58a6ff;
            font-size: 1.3rem;
            font-weight: 700;
        }

        /* ── Code blocks ── */
        .stCodeBlock {
            border: 1px solid #30363d;
            border-radius: 8px;
        }

        /* ── Buttons ── */
        .stButton > button {
            border-radius: 6px;
            font-weight: 600;
            transition: all 0.15s ease;
        }
        .stButton > button:hover { opacity: 0.85; }

        /* ── Severity Badges ── */
        .badge-critical { background:#da3633; color:#fff; padding:2px 8px; border-radius:4px; font-weight:700; font-size:0.8rem; }
        .badge-high     { background:#e3b341; color:#000; padding:2px 8px; border-radius:4px; font-weight:700; font-size:0.8rem; }
        .badge-medium   { background:#d29922; color:#000; padding:2px 8px; border-radius:4px; font-weight:700; font-size:0.8rem; }
        .badge-low      { background:#388bfd; color:#fff; padding:2px 8px; border-radius:4px; font-weight:700; font-size:0.8rem; }
        .badge-info     { background:#3d444d; color:#e6edf3; padding:2px 8px; border-radius:4px; font-weight:700; font-size:0.8rem; }

        /* ── Section Headers ── */
        .feature-header {
            border-bottom: 2px solid #21262d;
            padding-bottom: 0.5rem;
            margin-bottom: 1.5rem;
            color: #e6edf3;
        }

        /* ── User & Assistant Chat ── */
        .chat-user { background:#1c2128; border-left:3px solid #58a6ff; padding:0.75rem 1rem; border-radius:4px; margin-bottom:0.5rem; }
        .chat-assistant { background:#161b22; border-left:3px solid #3fb950; padding:0.75rem 1rem; border-radius:4px; margin-bottom:0.5rem; }

        /* ── History Card ── */
        .history-card {
            background-color: #161b22;
            border: 1px solid #30363d;
            border-radius: 8px;
            padding: 1rem;
            margin-bottom: 1rem;
        }

        /* ── Auth Card ── */
        .auth-container {
            max-width: 480px;
            margin: 2rem auto;
            background: #161b22;
            border: 1px solid #30363d;
            border-radius: 12px;
            padding: 2rem;
            box-shadow: 0 8px 24px rgba(0,0,0,0.5);
        }

        /* ── Empty state ── */
        .empty-state { text-align:center; padding:3rem; color:#8b949e; }
        </style>
        """,
        unsafe_allow_html=True,
    )


# ── Session State Management ───────────────────────────────────────────────────

def _init_session() -> None:
    """Initialise all session state variables and detect password reset URL tokens."""
    defaults = {
        "authenticated": False,
        "user": None,  # Dict with id, full_name, username, email
        "auth_view": "LOGIN",  # Routing states: "LOGIN", "REGISTER", "FORGOT_PASSWORD", "RESET_PASSWORD"
        "login_prefill_identifier": "",
        "auth_flash_success": "",
        "auth_flash_error": "",
        "reset_token_input": "",
        "page": "Dashboard",
        "chat_history": [],  # List[ChatMessage]
        "chat_context_code": "",
        "chat_context_language": "",
        "file_content": "",
        "file_language": "",
        "file_name": "",
        "session_api_key": "",
        "session_model": settings.active_model,
        "api_status_cached": None,
        "db_status_cached": None,
        "viewing_history_record": None,
        "dev_reset_token": "",
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

    # Detect reset_token from URL query parameters (e.g. ?reset_token=xyz)
    try:
        url_token = st.query_params.get("reset_token")
        if url_token and not st.session_state.get("authenticated", False):
            st.session_state["auth_view"] = "RESET_PASSWORD"
            st.session_state["reset_token_input"] = str(url_token).strip()
            # Clean URL query parameter so token is not exposed in the browser address bar
            st.query_params.clear()
    except Exception:
        pass



def _get_current_user_id() -> str:
    """Return logged-in user's string ID, or empty string."""
    if st.session_state.user and isinstance(st.session_state.user, dict):
        return str(st.session_state.user.get("id", ""))
    return ""


def _get_active_api_key() -> str:
    """Return active API key (session override or settings)."""
    return (st.session_state.get("session_api_key") or settings.api_key).strip()


def _get_active_model() -> str:
    """Return active model name (session override or settings)."""
    return (st.session_state.get("session_model") or settings.active_model).strip()


def _get_api_status(force_check: bool = False) -> tuple[str, str]:
    """Check API configuration and connectivity."""
    if st.session_state.api_status_cached is not None and not force_check:
        return st.session_state.api_status_cached

    api_key = _get_active_api_key()
    model = _get_active_model()

    if not api_key:
        status = ("NOT_CONFIGURED", "❌ Not configured")
    else:
        status = LLMService.check_api_status(api_key=api_key, model=model)

    st.session_state.api_status_cached = status
    return status


def _get_db_status(force_check: bool = False) -> tuple[bool, str]:
    """Check MongoDB Atlas connectivity."""
    if st.session_state.db_status_cached is not None and not force_check:
        return st.session_state.db_status_cached

    status = mongo_service.test_connection()
    st.session_state.db_status_cached = status
    return status


def _require_llm() -> LLMService | None:
    """Validate LLM readiness and return LLMService instance or None."""
    api_key = _get_active_api_key()
    if not api_key:
        st.warning(
            "⚙️ **API key not configured.** "
            "Go to **Settings** in the sidebar to add your `GEMINI_API_KEY`, "
            "or set it in your `.env` file and restart the app.",
            icon="🔑",
        )
        return None

    status_code, status_msg = _get_api_status()
    if status_code == "AUTH_FAILED":
        st.error(f"**Authentication Error:** {status_msg}. Please check your GEMINI_API_KEY in Settings.")
        return None
    if status_code == "MODEL_ERROR":
        st.error(f"**Model Error:** {status_msg}. Please select a valid GEMINI_MODEL in Settings.")
        return None

    try:
        return LLMService(api_key=api_key, model=_get_active_model())
    except Exception as exc:
        st.error(f"Failed to initialize AI service: {exc}")
        return None


def _record_ai_action(
    operation: str,
    language: str,
    summary: str,
    input_code: Optional[str] = None,
    generated_code: Optional[str] = None,
    explanation: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    """Save history record and audit log for authenticated user."""
    user_id = _get_current_user_id()
    if not user_id:
        return

    record_id, secret_detected = history_service.save_history(
        user_id=user_id,
        operation=operation,
        language=language,
        input_summary=summary,
        input_code=input_code,
        generated_code=generated_code,
        explanation=explanation,
        metadata=metadata,
    )

    activity_service.log_activity(
        user_id=user_id,
        action=f"{operation.replace('_', ' ').title()} used",
        details={"language": language, "has_code": bool(generated_code)},
    )

    if secret_detected:
        st.info("ℹ️ **Security Notice:** Potential credential/token detected in input was redacted before saving to your history.")


# ── Authentication Screens (Login & Register) ──────────────────────────────────

def _render_auth_login() -> None:
    st.markdown("#### Welcome Back")
    prefill = st.session_state.get("login_prefill_identifier", "")
    with st.form("login_form"):
        identifier = st.text_input(
            "Email or Username",
            value=prefill,
            placeholder="e.g. alex@example.com or alex",
        )
        password = st.text_input("Password", type="password", placeholder="••••••••")
        submitted = st.form_submit_button("Log In", use_container_width=True, type="primary")

    if submitted:
        if not identifier or not password:
            st.error("Please enter both email/username and password.")
        else:
            with st.spinner("Authenticating..."):
                success, message, user = auth_service.login_user(
                    UserLogin(email_or_username=identifier, password=password)
                )
            if success and user:
                st.session_state.authenticated = True
                st.session_state.user = {
                    "id": user.id,
                    "full_name": user.full_name,
                    "username": user.username,
                    "email": user.email,
                    "created_at": user.created_at,
                }
                # Clear prefill and transient state
                st.session_state.login_prefill_identifier = ""
                st.session_state.auth_flash_success = ""
                st.session_state.auth_flash_error = ""
                st.session_state.page = "Dashboard"
                activity_service.log_activity(user.id, "User logged in")
                st.rerun()
            else:
                st.error(message)
                if "network access" in message.lower() or "ip address" in message.lower():
                    st.info(
                        "💡 **Atlas Network Access Fix:**\n"
                        "1. Open [MongoDB Atlas Console](https://cloud.mongodb.com)\n"
                        "2. Navigate to **Security** → **Network Access**\n"
                        "3. Click **Add IP Address**\n"
                        "4. Add `0.0.0.0/0` (Allow Access from Anywhere) or your current public IP\n"
                        "5. Click **Confirm** and wait 1–2 minutes for the changes to apply.",
                        icon="ℹ️",
                    )

    # Forgot password action link
    if st.button("Forgot Password?", key="btn_nav_forgot_pwd", use_container_width=True):
        st.session_state.auth_view = "FORGOT_PASSWORD"
        st.rerun()



def _render_auth_register() -> None:
    st.markdown("#### Create Your Workspace Account")
    with st.form("register_form"):
        full_name = st.text_input("Full Name", placeholder="e.g. Alex Johnson")
        username = st.text_input("Username", placeholder="e.g. alex_dev (3-30 chars)")
        email = st.text_input("Email Address", placeholder="alex@example.com")
        reg_password = st.text_input("Password", type="password", placeholder="••••••••")
        confirm_password = st.text_input("Confirm Password", type="password", placeholder="••••••••")

        st.caption(
            "🔒 **Password Requirements:**\n"
            "- Minimum 8 characters\n"
            "- At least one uppercase (A-Z) & lowercase (a-z) letter\n"
            "- At least one number (0-9) & special character (!@#$%...)"
        )
        reg_submitted = st.form_submit_button("Create Account", use_container_width=True, type="primary")

    if reg_submitted:
        req = UserRegistration(
            full_name=full_name,
            username=username,
            email=email,
            password=reg_password,
            confirm_password=confirm_password,
        )
        with st.spinner("Creating account..."):
            success, message, user = auth_service.register_user(req)

        if success and user:
            activity_service.log_activity(user.id, "User registered")
            # Clear authentication / session state
            st.session_state.authenticated = False
            st.session_state.user = None
            # Pre-fill email/username for the Login page
            st.session_state.login_prefill_identifier = username or email
            # Set flash success message
            st.session_state.auth_flash_success = (
                "Account created successfully. Please log in with your new account."
            )
            # Switch view to Login
            st.session_state.auth_view = "LOGIN"
            st.rerun()
        else:
            # Keep user on the registration page with specific safe error
            st.error(message)
            if "network access" in message.lower() or "ip address" in message.lower():
                st.info(
                    "💡 **Atlas Network Access Fix:**\n"
                    "1. Open [MongoDB Atlas Console](https://cloud.mongodb.com)\n"
                    "2. Navigate to **Security** → **Network Access**\n"
                    "3. Click **Add IP Address**\n"
                    "4. Add `0.0.0.0/0` (Allow Access from Anywhere) or your current public IP\n"
                    "5. Click **Confirm** and wait 1–2 minutes for the changes to apply.",
                    icon="ℹ️",
                )



def _render_auth_forgot_password() -> None:
    st.markdown("#### 🔐 Forgot Password?")
    st.markdown(
        "Enter your registered email address below. If an account exists, a secure single-use "
        "password reset link will be sent to your inbox."
    )

    with st.form("forgot_password_form"):
        fp_email = st.text_input("Registered Email Address", placeholder="e.g. alex@example.com")
        fp_submitted = st.form_submit_button("Send Reset Link", use_container_width=True, type="primary")

    if fp_submitted:
        if not fp_email or "@" not in fp_email:
            st.error("Please enter a valid email address.")
        else:
            with st.spinner("Processing request..."):
                success, message, dev_info = auth_service.request_password_reset(fp_email)
            if success:
                st.success(f"✅ {message}")
                st.session_state.pop("dev_reset_token", None)
            elif not auth_service.is_smtp_configured or "not configured" in message.lower():
                st.warning(f"⚠️ {message}")
                if dev_info and settings.is_development and dev_info.get("dev_token"):
                    st.session_state["dev_reset_token"] = dev_info["dev_token"]
                else:
                    st.session_state.pop("dev_reset_token", None)
            else:
                st.error(f"❌ {message}")
                st.session_state.pop("dev_reset_token", None)

    # Safe development reset flow (ENVIRONMENT=development only, NO raw token or URL displayed)
    if settings.is_development and st.session_state.get("dev_reset_token"):
        st.markdown("<br>", unsafe_allow_html=True)
        st.info(
            "🛠️ **DEVELOPMENT ONLY**\n\n"
            "SMTP is not configured. Use the development reset action below to test password reset."
        )
        if st.button("Open Development Reset Flow", key="btn_open_dev_reset_flow", type="primary", use_container_width=True):
            st.session_state.auth_view = "RESET_PASSWORD"
            st.session_state.reset_token_input = st.session_state.pop("dev_reset_token", "")
            st.rerun()

    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("← Back to Login", key="btn_fp_back_to_login", use_container_width=True):
        st.session_state.pop("dev_reset_token", None)
        st.session_state.auth_view = "LOGIN"
        st.rerun()


def _render_auth_reset_password() -> None:
    st.markdown("#### 🔑 Reset Your Password")
    st.markdown(
        "Enter your secure reset token (automatically populated if you clicked an email link) "
        "and choose a new password."
    )

    preset_token = st.session_state.get("reset_token_input", "")

    with st.form("reset_password_form"):
        token_input = st.text_input(
            "Reset Token",
            value=preset_token,
            type="password",
            help="The secure reset token provided in your reset email or URL link.",
        )
        new_password = st.text_input("New Password", type="password", placeholder="••••••••")
        confirm_new_password = st.text_input("Confirm New Password", type="password", placeholder="••••••••")

        st.caption(
            "🔒 **Password Requirements:**\n"
            "- Minimum 8 characters\n"
            "- At least one uppercase (A-Z) & lowercase (a-z) letter\n"
            "- At least one number (0-9) & special character (!@#$%...)"
        )
        reset_submitted = st.form_submit_button("Reset Password", use_container_width=True, type="primary")

    if reset_submitted:
        if not token_input or not token_input.strip():
            st.error("Please provide the reset token.")
        elif not new_password or not confirm_new_password:
            st.error("Please enter and confirm your new password.")
        else:
            with st.spinner("Validating token and updating password..."):
                success, message = auth_service.reset_password(
                    token=token_input,
                    new_password=new_password,
                    confirm_new_password=confirm_new_password,
                )

            if success:
                # Clear URL query parameters and reset token input
                try:
                    st.query_params.clear()
                except Exception:
                    pass
                st.session_state.reset_token_input = ""
                st.session_state.auth_view = "LOGIN"
                st.session_state.auth_flash_success = (
                    "Password reset successfully. Please log in with your new password."
                )
                st.rerun()
            else:
                st.error(f"❌ {message}")

    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("← Back to Login", key="btn_rp_back_to_login", use_container_width=True):
        st.session_state.auth_view = "LOGIN"
        st.rerun()


def render_auth_screen() -> None:
    """Display centered authentication screen for unauthenticated visitors."""
    st.markdown("<br>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 2, 1])

    with col2:
        st.markdown(
            """
            <div style="text-align: center; margin-bottom: 1.5rem;">
                <h1 style="color: #58a6ff; font-size: 2.2rem; margin-bottom: 0.2rem;">🤖 AI Coding Assistant</h1>
                <p style="color: #8b949e; font-size: 1.05rem;">Your intelligent development workspace</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        db_ok, db_msg = _get_db_status()
        if not db_ok:
            st.warning(f"⚠️ **Database Status:** {db_msg}", icon="⚠️")

        # Display flash success / error messages if present
        if st.session_state.get("auth_flash_success"):
            st.success(f"✅ {st.session_state.auth_flash_success}")
            st.session_state.auth_flash_success = ""

        if st.session_state.get("auth_flash_error"):
            st.error(f"❌ {st.session_state.auth_flash_error}")
            st.session_state.auth_flash_error = ""

        current_view = st.session_state.get("auth_view", "LOGIN")

        # Top switcher between Login and Register if on standard views
        if current_view in ("LOGIN", "REGISTER"):
            col_t1, col_t2 = st.columns(2)
            with col_t1:
                t1_type = "primary" if current_view == "LOGIN" else "secondary"
                if st.button("🔑 Login", key="tab_nav_login", use_container_width=True, type=t1_type):
                    st.session_state.auth_view = "LOGIN"
                    st.rerun()
            with col_t2:
                t2_type = "primary" if current_view == "REGISTER" else "secondary"
                if st.button("📄 Create Account", key="tab_nav_register", use_container_width=True, type=t2_type):
                    st.session_state.auth_view = "REGISTER"
                    st.rerun()
            st.markdown("---")

        if current_view == "LOGIN":
            _render_auth_login()
        elif current_view == "REGISTER":
            _render_auth_register()
        elif current_view == "FORGOT_PASSWORD":
            _render_auth_forgot_password()
        elif current_view == "RESET_PASSWORD":
            _render_auth_reset_password()
        else:
            _render_auth_login()



# ── Feature Pages ──────────────────────────────────────────────────────────────

def page_dashboard() -> None:
    st.markdown('<h1 class="feature-header">🏠 Dashboard</h1>', unsafe_allow_html=True)

    user = st.session_state.user or {}
    user_name = user.get("full_name") or user.get("username") or "Developer"
    user_id = _get_current_user_id()

    st.markdown(f"### 👋 Welcome back, **{user_name}**!")

    status_code, status_text = _get_api_status()
    db_connected, db_msg = _get_db_status()
    active_model = _get_active_model()

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("AI Provider", settings.ai_provider.upper())
    with col2:
        st.metric("Gemini Model", active_model)
    with col3:
        st.metric("API Status", status_text)
    with col4:
        st.metric("MongoDB", "✅ Connected" if db_connected else "❌ Disconnected")

    st.markdown("---")

    col_act, col_quick = st.columns([1.4, 1])

    with col_act:
        st.markdown("### 🕒 Recent Coding Activity")
        recent_history = history_service.get_user_history(user_id=user_id, limit=5)
        if not recent_history:
            st.info("No coding history recorded yet. Use any tool below to generate, debug, or convert code!", icon="ℹ️")
        else:
            for item in recent_history:
                with st.container():
                    op_title = item.operation.replace("_", " ").title()
                    st.markdown(
                        f"""
                        <div class="history-card">
                            <div style="display:flex; justify-content:space-between; align-items:center;">
                                <strong>⚡ {op_title} ({item.language})</strong>
                                <small style="color:#8b949e;">{item.created_at[:16].replace('T', ' ')}</small>
                            </div>
                            <p style="margin-top:0.4rem; margin-bottom:0.4rem; color:#c9d1d9; font-size:0.92rem;">
                                {item.input_summary[:140]}{'...' if len(item.input_summary) > 140 else ''}
                            </p>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

    with col_quick:
        st.markdown("### 🚀 Quick Launch")
        quick_tools = [
            ("✨ Generate Code", "Generate Code", "Build functions or full modules from scratch"),
            ("🐛 Debug Code", "Debug Code", "Locate root causes and obtain verified bugfixes"),
            ("🔄 Convert Code", "Convert Code", "Translate code cleanly across programming languages"),
            ("🔐 Security Analysis", "Security Analysis", "Inspect source code for security risks"),
            ("💬 AI Coding Chat", "AI Coding Chat", "Ask questions and iterate with your code in context"),
        ]
        for label, page_name, desc in quick_tools:
            if st.button(f"{label}", key=f"quick_{page_name}", use_container_width=True):
                st.session_state.page = page_name
                st.rerun()


def page_generate() -> None:
    st.markdown('<h1 class="feature-header">✨ Generate Code</h1>', unsafe_allow_html=True)
    st.caption("Describe what you want to build. The AI will generate production-ready code.")

    languages = build_language_list()

    with st.form("generate_form"):
        col1, col2 = st.columns(2)
        with col1:
            language = st.selectbox("Programming Language *", languages)
        with col2:
            framework = st.text_input("Framework / Library (optional)", placeholder="e.g. FastAPI, React, Django")

        requirements = st.text_area(
            "Requirements *",
            height=150,
            placeholder="e.g. Create a Python FastAPI REST API for managing a student database with CRUD endpoints.",
        )
        constraints = st.text_input(
            "Constraints / Style (optional)",
            placeholder="e.g. Use type hints, follow PEP 8, no external databases",
        )
        submitted = st.form_submit_button("✨ Generate Code", use_container_width=True)

    if submitted:
        llm = _require_llm()
        if not llm:
            return
        if not requirements.strip():
            st.error("Please enter your requirements.")
            return

        svc = CodeService(llm)
        with st.spinner("Generating code..."):
            result = svc.generate(
                CodeGenerationRequest(
                    language=language,
                    requirements=requirements,
                    framework=framework or None,
                    constraints=constraints or None,
                )
            )

        if result.error:
            st.error(f"**{result.error.code}:** {result.error.message}")
            return

        st.success("Code generated successfully!", icon="✅")

        _record_ai_action(
            operation="generate",
            language=language,
            summary=requirements[:200],
            input_code=None,
            generated_code=result.generated_code,
            explanation=result.explanation,
            metadata={"framework": framework, "constraints": constraints},
        )

        tab1, tab2, tab3 = st.tabs(["📄 Code", "📋 Details", "🔧 How to Run"])

        with tab1:
            lang_key = language.lower().split("/")[0].strip()
            st.code(result.generated_code, language=lang_key)

        with tab2:
            if result.explanation:
                st.markdown("#### Explanation")
                st.markdown(result.explanation)
            if result.dependencies:
                st.markdown("#### Dependencies")
                for dep in result.dependencies:
                    st.markdown(f"- `{dep}`")
            if result.potential_improvements:
                st.markdown("#### Potential Improvements")
                for imp in result.potential_improvements:
                    st.markdown(f"- {imp}")

        with tab3:
            if result.how_to_run:
                st.markdown(result.how_to_run)
            else:
                st.info("No run instructions provided.")

        if st.button("💬 Chat about this code", key="gen_to_chat"):
            st.session_state.chat_context_code = result.generated_code
            st.session_state.chat_context_language = language
            st.session_state.page = "AI Coding Chat"
            st.rerun()


def page_debug() -> None:
    st.markdown('<h1 class="feature-header">🐛 Debug Code</h1>', unsafe_allow_html=True)
    st.caption("Paste your buggy code and error message. The AI will find and fix the issue.")

    languages = build_language_list()

    with st.form("debug_form"):
        col1, col2 = st.columns([1, 3])
        with col1:
            language = st.selectbox("Language *", languages)
        with col2:
            error_message = st.text_input(
                "Error Message (optional)",
                placeholder="e.g. TypeError: 'NoneType' object is not iterable",
            )

        code = st.text_area("Code *", height=250, placeholder="Paste your code here...")
        expected = st.text_input(
            "Expected Behavior (optional)",
            placeholder="e.g. The function should return a sorted list",
        )
        submitted = st.form_submit_button("🐛 Debug Code", use_container_width=True)

    if submitted:
        llm = _require_llm()
        if not llm:
            return
        if not code.strip():
            st.error("Please paste your code.")
            return

        svc = CodeService(llm)
        with st.spinner("Analysing your code..."):
            result = svc.debug(
                DebugRequest(
                    language=language,
                    code=code,
                    error_message=error_message or None,
                    expected_behavior=expected or None,
                )
            )

        if result.error:
            st.error(f"**{result.error.code}:** {result.error.message}")
            return

        st.success("Debug analysis complete!", icon="✅")

        _record_ai_action(
            operation="debug",
            language=language,
            summary=f"Debug {language} code: {error_message or 'Logic bug'}"[:200],
            input_code=code,
            generated_code=result.corrected_code,
            explanation=f"Problem: {result.problem_explanation}\n\nRoot Cause: {result.root_cause}",
            metadata={"error_message": error_message, "expected": expected},
        )

        tab1, tab2, tab3 = st.tabs(["🔍 Analysis", "✅ Fixed Code", "💡 Prevention"])

        with tab1:
            st.markdown("#### Problem")
            st.markdown(result.problem_explanation)
            st.markdown("#### Root Cause")
            st.markdown(result.root_cause)
            if result.explanation_of_changes:
                st.markdown("#### Changes Made")
                st.markdown(result.explanation_of_changes)

        with tab2:
            lang_key = language.lower().split("/")[0].strip()
            st.code(result.corrected_code, language=lang_key)

        with tab3:
            st.markdown(result.prevention_advice)


def page_explain() -> None:
    st.markdown('<h1 class="feature-header">📖 Explain Code</h1>', unsafe_allow_html=True)
    st.caption("Paste any code to get a clear, beginner-friendly explanation.")

    languages = ["Auto-detect"] + build_language_list()

    with st.form("explain_form"):
        language = st.selectbox("Language", languages)
        code = st.text_area("Code *", height=250, placeholder="Paste your code here...")
        submitted = st.form_submit_button("📖 Explain Code", use_container_width=True)

    if submitted:
        llm = _require_llm()
        if not llm:
            return
        if not code.strip():
            st.error("Please paste your code.")
            return

        lang = None if language == "Auto-detect" else language
        svc = CodeService(llm)
        with st.spinner("Analysing code..."):
            result = svc.explain(ExplainRequest(code=code, language=lang))

        if result.error:
            st.error(f"**{result.error.code}:** {result.error.message}")
            return

        st.success("Explanation ready!", icon="📖")

        _record_ai_action(
            operation="explain",
            language=language,
            summary=f"Explain: {result.summary[:150]}",
            input_code=code,
            generated_code=None,
            explanation=result.summary,
            metadata={"complexity": result.complexity},
        )

        tab1, tab2, tab3 = st.tabs(["📋 Summary", "🔍 Detailed", "🎓 Beginner"])

        with tab1:
            st.markdown("#### Summary")
            st.markdown(result.summary)
            if result.inputs:
                st.markdown("**Inputs:**")
                st.markdown(result.inputs)
            if result.outputs:
                st.markdown("**Outputs:**")
                st.markdown(result.outputs)
            if result.complexity:
                st.markdown(f"**Complexity:** {result.complexity}")
            if result.important_concepts:
                st.markdown("**Key Concepts:**")
                for c in result.important_concepts:
                    st.markdown(f"- {c}")

        with tab2:
            st.markdown(result.line_by_line)
            if result.potential_problems:
                st.markdown("#### ⚠️ Potential Problems")
                for p in result.potential_problems:
                    if "none" not in p.lower():
                        st.warning(p)

        with tab3:
            st.markdown(result.beginner_explanation)


def page_refactor() -> None:
    st.markdown('<h1 class="feature-header">🔧 Refactor Code</h1>', unsafe_allow_html=True)
    st.caption("Improve your code quality — naming, structure, performance — without changing behavior.")

    languages = build_language_list()

    with st.form("refactor_form"):
        col1, col2 = st.columns([1, 2])
        with col1:
            language = st.selectbox("Language *", languages)
        with col2:
            focus = st.text_input(
                "Focus Area (optional)",
                placeholder="e.g. readability, performance, naming",
            )
        code = st.text_area("Code *", height=250, placeholder="Paste your code here...")
        submitted = st.form_submit_button("🔧 Refactor Code", use_container_width=True)

    if submitted:
        llm = _require_llm()
        if not llm:
            return
        if not code.strip():
            st.error("Please paste your code.")
            return

        svc = CodeService(llm)
        with st.spinner("Analysing and refactoring..."):
            result = svc.refactor(
                RefactorRequest(language=language, code=code, focus=focus or None)
            )

        if result.error:
            st.error(f"**{result.error.code}:** {result.error.message}")
            return

        st.success("Refactoring complete!", icon="✅")

        _record_ai_action(
            operation="refactor",
            language=language,
            summary=f"Refactor {language} code (Focus: {focus or 'general'})"[:200],
            input_code=code,
            generated_code=result.refactored_code,
            explanation=result.explanation_of_changes,
            metadata={"issues_count": len(result.issues_found)},
        )

        tab1, tab2 = st.tabs(["⚠️ Issues Found", "✅ Refactored Code"])

        with tab1:
            if result.issues_found:
                for issue in result.issues_found:
                    sev = issue.severity.upper()
                    color = {"HIGH": "🔴", "MEDIUM": "🟡", "LOW": "🔵"}.get(sev, "⚪")
                    with st.expander(f"{color} [{sev}] {issue.issue}"):
                        st.markdown(issue.reason)
            else:
                st.info("No significant issues detected.")

            st.markdown("#### Summary of Changes")
            st.markdown(result.explanation_of_changes)

        with tab2:
            lang_key = language.lower().split("/")[0].strip()
            st.code(result.refactored_code, language=lang_key)


def page_convert() -> None:
    st.markdown('<h1 class="feature-header">🔄 Convert Code</h1>', unsafe_allow_html=True)
    st.caption("Convert code between programming languages while preserving behavior.")

    languages = build_language_list()

    with st.form("convert_form"):
        col1, col2 = st.columns(2)
        with col1:
            source_lang = st.selectbox("From Language *", languages, index=0)
        with col2:
            target_lang = st.selectbox("To Language *", languages, index=3)  # Java default
        code = st.text_area(
            "Code to Convert *",
            height=250,
            value="""def add_numbers(a, b):
    return a + b

result = add_numbers(10, 20)
print(result)""",
        )
        submitted = st.form_submit_button("🔄 Convert Code", use_container_width=True)

    if submitted:
        llm = _require_llm()
        if not llm:
            return
        if not code.strip():
            st.error("Please paste your code.")
            return
        if source_lang == target_lang:
            st.error("Source and target languages must be different.")
            return

        svc = CodeService(llm)
        with st.spinner(f"Converting {source_lang} → {target_lang}..."):
            result = svc.convert(
                ConvertRequest(source_language=source_lang, target_language=target_lang, code=code)
            )

        if result.error:
            st.error(f"**{result.error.code}:** {result.error.message}")
            return

        st.success(f"Converted {source_lang} → {target_lang} successfully!", icon="✅")

        _record_ai_action(
            operation="convert",
            language=f"{source_lang} -> {target_lang}",
            summary=f"Convert {source_lang} to {target_lang}"[:200],
            input_code=code,
            generated_code=result.converted_code,
            explanation=result.behavior_notes,
            metadata={"source_language": source_lang, "target_language": target_lang},
        )

        tab1, tab2 = st.tabs(["📄 Converted Code", "📋 Notes & Differences"])

        with tab1:
            lang_key = target_lang.lower().split("/")[0].strip()
            st.code(result.converted_code, language=lang_key)

        with tab2:
            if result.important_differences:
                st.markdown("#### Key Differences")
                for d in result.important_differences:
                    st.markdown(f"- {d}")
            if result.dependencies:
                st.markdown("#### Dependencies")
                for dep in result.dependencies:
                    st.markdown(f"- `{dep}`")
            if result.behavior_notes:
                st.markdown("#### Behavior Notes")
                st.markdown(result.behavior_notes)


def page_tests() -> None:
    st.markdown('<h1 class="feature-header">🧪 Generate Tests</h1>', unsafe_allow_html=True)
    st.caption("Auto-generate comprehensive unit tests for your code.")

    languages = build_language_list()
    frameworks = ["pytest", "unittest", "jest", "mocha"]

    with st.form("tests_form"):
        col1, col2 = st.columns(2)
        with col1:
            language = st.selectbox("Language *", languages)
        with col2:
            framework = st.selectbox("Test Framework *", frameworks)
        code = st.text_area("Code to Test *", height=250, placeholder="Paste your code here...")
        submitted = st.form_submit_button("🧪 Generate Tests", use_container_width=True)

    if submitted:
        llm = _require_llm()
        if not llm:
            return
        if not code.strip():
            st.error("Please paste your code.")
            return

        svc = CodeService(llm)
        with st.spinner("Generating tests..."):
            result = svc.generate_tests(
                TestGenerationRequest(language=language, code=code, test_framework=framework)
            )

        if result.error:
            st.error(f"**{result.error.code}:** {result.error.message}")
            return

        st.success("Tests generated!", icon="✅")

        _record_ai_action(
            operation="tests",
            language=language,
            summary=f"Generate {framework} unit tests for {language}"[:200],
            input_code=code,
            generated_code=result.test_code,
            explanation=None,
            metadata={"framework": framework, "cases_count": len(result.test_cases_covered)},
        )

        tab1, tab2 = st.tabs(["🧪 Test Code", "📋 Coverage"])

        with tab1:
            lang_key = language.lower().split("/")[0].strip()
            st.code(result.test_code, language=lang_key)

        with tab2:
            if result.test_cases_covered:
                st.markdown("#### Test Cases Covered")
                for c in result.test_cases_covered:
                    st.markdown(f"- ✅ {c}")
            if result.edge_cases:
                st.markdown("#### Edge Cases")
                for e in result.edge_cases:
                    st.markdown(f"- 🔍 {e}")
            if result.missing_cases:
                st.markdown("#### Missing Cases")
                for m in result.missing_cases:
                    if "none" not in m.lower():
                        st.markdown(f"- ⚠️ {m}")


def page_security() -> None:
    st.markdown('<h1 class="feature-header">🔐 Security Analysis</h1>', unsafe_allow_html=True)
    st.caption(
        "Scan your code for security vulnerabilities. "
        "**Advisory only** — always review with a qualified security professional."
    )

    languages = build_language_list()

    with st.form("security_form"):
        language = st.selectbox("Language *", languages)
        code = st.text_area("Code to Analyse *", height=250, placeholder="Paste your code here...")
        submitted = st.form_submit_button("🔐 Run Security Analysis", use_container_width=True)

    if submitted:
        llm = _require_llm()
        if not llm:
            return
        if not code.strip():
            st.error("Please paste your code.")
            return

        svc = SecurityService(llm)
        with st.spinner("Running security analysis..."):
            result = svc.analyze(SecurityRequest(language=language, code=code))

        if result.error:
            st.error(f"**{result.error.code}:** {result.error.message}")
            return

        risk = result.overall_risk.value
        risk_colors = {
            "CRITICAL": "🔴",
            "HIGH": "🟠",
            "MEDIUM": "🟡",
            "LOW": "🔵",
            "INFO": "⚪",
        }
        icon = risk_colors.get(risk, "⚪")
        st.markdown(f"### Overall Risk: {icon} **{risk}**")

        _record_ai_action(
            operation="security",
            language=language,
            summary=f"Security scan ({language}): Risk {risk}, {len(result.findings)} findings"[:200],
            input_code=code,
            generated_code=None,
            explanation=result.summary,
            metadata={"overall_risk": risk, "findings_count": len(result.findings)},
        )

        if result.summary:
            st.markdown(result.summary)

        st.info(result.disclaimer, icon="ℹ️")
        st.markdown("---")

        if not result.findings:
            st.success("No security issues identified in the provided code.", icon="✅")
        else:
            severity_order = ["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"]
            sorted_findings = sorted(
                result.findings,
                key=lambda f: severity_order.index(f.severity.value)
                if f.severity.value in severity_order
                else 99,
            )
            for finding in sorted_findings:
                sev = finding.severity.value
                icon = risk_colors.get(sev, "⚪")
                with st.expander(f"{icon} [{sev}] {finding.title}", expanded=(sev in ("CRITICAL", "HIGH"))):
                    if finding.location:
                        st.markdown(f"**Location:** `{finding.location}`")
                    st.markdown(f"**Description:** {finding.description}")
                    st.markdown(f"**Remediation:** {finding.remediation}")


def page_file_analyze() -> None:
    st.markdown('<h1 class="feature-header">📁 Analyze File</h1>', unsafe_allow_html=True)
    st.caption("Upload a source code file for AI-powered analysis.")

    file_svc = FileService()
    uploaded = st.file_uploader(
        "Upload Source Code File",
        type=["py", "js", "ts", "java", "cpp", "c", "html", "css", "json", "sql"],
        help=f"Max file size: {settings.max_file_size_mb} MB",
    )

    if uploaded:
        result = file_svc.read_uploaded_file(uploaded)
        if not result.success:
            st.error(result.error)
            return

        st.session_state.file_content = result.content
        st.session_state.file_language = result.language or "Unknown"
        st.session_state.file_name = result.filename

        st.success(
            f"**{result.filename}** ({result.language}, {format_file_size(result.file_size)})",
            icon="📁",
        )

        with st.expander("📄 Source Code", expanded=True):
            lang_key = (result.language or "").lower()
            st.code(result.content, language=lang_key)

        st.markdown("### Analyse With AI")
        action = st.radio(
            "Choose action:",
            ["📖 Explain", "🐛 Debug", "🔧 Refactor", "🔐 Security Analysis", "🧪 Generate Tests"],
            horizontal=True,
        )

        file_debug_err = None
        if action == "🐛 Debug":
            file_debug_err = st.text_input("Error message (optional):", key="file_debug_err_input")

        llm = _require_llm()
        if not llm:
            return

        if st.button(f"▶ Run {action}", use_container_width=True):
            language = result.language or "Unknown"
            code = result.content

            if action == "📖 Explain":
                from services.code_service import CodeService as CS
                with st.spinner("Explaining..."):
                    r = CS(llm).explain(ExplainRequest(code=code, language=language))
                if r.error:
                    st.error(r.error.message)
                else:
                    st.markdown("#### Summary")
                    st.markdown(r.summary)
                    st.markdown("#### Detailed Explanation")
                    st.markdown(r.line_by_line)
                    _record_ai_action("explain_file", language, f"Explain file {result.filename}", code, None, r.summary)

            elif action == "🐛 Debug":
                from services.code_service import CodeService as CS
                with st.spinner("Debugging..."):
                    r = CS(llm).debug(DebugRequest(language=language, code=code, error_message=file_debug_err or None))
                if r.error:
                    st.error(r.error.message)
                else:
                    st.markdown("#### Problem")
                    st.markdown(r.problem_explanation)
                    st.markdown("#### Fixed Code")
                    st.code(r.corrected_code, language=language.lower())
                    _record_ai_action("debug_file", language, f"Debug file {result.filename}", code, r.corrected_code, r.root_cause)

            elif action == "🔧 Refactor":
                from services.code_service import CodeService as CS
                with st.spinner("Refactoring..."):
                    r = CS(llm).refactor(RefactorRequest(language=language, code=code))
                if r.error:
                    st.error(r.error.message)
                else:
                    st.markdown("#### Refactored Code")
                    st.code(r.refactored_code, language=language.lower())
                    _record_ai_action("refactor_file", language, f"Refactor file {result.filename}", code, r.refactored_code, r.explanation_of_changes)

            elif action == "🔐 Security Analysis":
                with st.spinner("Running security analysis..."):
                    r = SecurityService(llm).analyze(SecurityRequest(language=language, code=code))
                if r.error:
                    st.error(r.error.message)
                else:
                    st.markdown(f"**Overall Risk:** {r.overall_risk.value}")
                    for f in r.findings:
                        st.warning(f"**[{f.severity.value}] {f.title}:** {f.description}")
                    _record_ai_action("security_file", language, f"Security scan file {result.filename}", code, None, r.summary)

            elif action == "🧪 Generate Tests":
                from services.code_service import CodeService as CS
                with st.spinner("Generating tests..."):
                    r = CS(llm).generate_tests(TestGenerationRequest(language=language, code=code))
                if r.error:
                    st.error(r.error.message)
                else:
                    st.code(r.test_code, language=language.lower())
                    _record_ai_action("tests_file", language, f"Generate tests for file {result.filename}", code, r.test_code, None)

        if st.button("💬 Chat about this file"):
            st.session_state.chat_context_code = result.content
            st.session_state.chat_context_language = result.language or ""
            st.session_state.page = "AI Coding Chat"
            st.rerun()

    else:
        st.markdown(
            '<div class="empty-state">📁 Upload a source-code file to begin analysis.</div>',
            unsafe_allow_html=True,
        )


def page_chat() -> None:
    st.markdown('<h1 class="feature-header">💬 AI Coding Chat</h1>', unsafe_allow_html=True)
    st.caption("Chat with the AI about code. Context from uploaded files or generated code is preserved.")

    languages = ["None"] + build_language_list()

    with st.expander("📎 Code Context (optional)", expanded=bool(st.session_state.chat_context_code)):
        col1, col2 = st.columns([3, 1])
        with col1:
            context_code = st.text_area(
                "Attach code for context:",
                value=st.session_state.chat_context_code,
                height=150,
                key="chat_ctx_code",
            )
        with col2:
            ctx_lang_idx = 0
            if st.session_state.chat_context_language in languages:
                ctx_lang_idx = languages.index(st.session_state.chat_context_language)
            context_lang = st.selectbox("Language:", languages, index=ctx_lang_idx, key="chat_ctx_lang")
            if st.button("Clear Context", key="clear_ctx"):
                st.session_state.chat_context_code = ""
                st.session_state.chat_context_language = ""
                st.rerun()

        st.session_state.chat_context_code = context_code
        st.session_state.chat_context_language = context_lang if context_lang != "None" else ""

    history: list[ChatMessage] = st.session_state.chat_history
    chat_container = st.container()
    with chat_container:
        if not history:
            st.markdown(
                '<div class="empty-state">👋 Start a conversation. Ask anything about your code.</div>',
                unsafe_allow_html=True,
            )
        for msg in history:
            if msg.role == "user":
                st.markdown(
                    f'<div class="chat-user">🧑‍💻 **You:** {msg.content}</div>',
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(f'<div class="chat-assistant">🤖 **AI:** {msg.content}</div>', unsafe_allow_html=True)

    with st.form("chat_form", clear_on_submit=True):
        user_input = st.text_area(
            "Your message:",
            placeholder="e.g. Why does this function return None? / Optimize this. / Add error handling.",
            height=100,
            label_visibility="collapsed",
        )
        col1, col2 = st.columns([5, 1])
        with col1:
            submitted = st.form_submit_button("Send 📨", use_container_width=True)
        with col2:
            clear = st.form_submit_button("🗑 Clear", use_container_width=True)

    if clear:
        st.session_state.chat_history = []
        st.rerun()

    if submitted and user_input.strip():
        llm = _require_llm()
        if not llm:
            return

        history.append(ChatMessage(role="user", content=user_input.strip()))

        ctx_code = st.session_state.chat_context_code or None
        ctx_lang = st.session_state.chat_context_language or None

        with st.spinner("Thinking..."):
            response = llm.chat(
                ChatRequest(
                    message=user_input.strip(),
                    history=history,
                    context_code=ctx_code,
                    context_language=ctx_lang,
                )
            )

        if response.error:
            st.error(f"**{response.error.code}:** {response.error.message}")
            history.pop()
        else:
            history.append(ChatMessage(role="assistant", content=response.reply))
            st.session_state.chat_history = history
            _record_ai_action(
                operation="chat",
                language=ctx_lang or "General",
                summary=user_input.strip()[:150],
                input_code=ctx_code,
                generated_code=response.reply,
            )
            st.rerun()


# ── History & Profile Pages ───────────────────────────────────────────────────

def page_history() -> None:
    st.markdown('<h1 class="feature-header">📚 Coding History</h1>', unsafe_allow_html=True)
    st.caption("View, search, reopen, or manage your saved AI coding generations and fixes.")

    user_id = _get_current_user_id()
    if not user_id:
        st.error("User session not found.")
        return

    # Filter & Search bar
    col1, col2, col3 = st.columns([2, 1.2, 1])
    with col1:
        search_query = st.text_input("🔍 Search History:", placeholder="Search by prompt, keyword, or code snippet...")
    with col2:
        op_options = ["All", "generate", "debug", "explain", "refactor", "convert", "tests", "security", "chat"]
        selected_op = st.selectbox("Filter Operation:", op_options)
    with col3:
        st.write("")
        st.write("")
        if st.button("🗑 Clear All History", use_container_width=True):
            deleted = history_service.clear_user_history(user_id)
            activity_service.log_activity(user_id, "Cleared all coding history")
            st.success(f"Cleared {deleted} history records.")
            st.rerun()

    # Query history
    records = history_service.get_user_history(
        user_id=user_id,
        limit=50,
        operation=selected_op if selected_op != "All" else None,
        search_query=search_query or None,
    )

    if not records:
        st.markdown(
            '<div class="empty-state">📭 No coding history found matching your filters.</div>',
            unsafe_allow_html=True,
        )
        return

    st.markdown(f"**Showing {len(records)} history records:**")

    for rec in records:
        with st.container():
            op_label = rec.operation.replace("_", " ").title()
            date_str = rec.created_at[:19].replace("T", " ")

            col_a, col_b = st.columns([4, 1])
            with col_a:
                st.markdown(f"#### ⚡ {op_label} — `{rec.language}` <small style='color:#8b949e;'>({date_str})</small>", unsafe_allow_html=True)
                st.markdown(f"**Summary:** {rec.input_summary}")
            with col_b:
                if st.button("🗑 Delete", key=f"del_{rec.id}", use_container_width=True):
                    history_service.delete_history_item(user_id, rec.id)
                    activity_service.log_activity(user_id, "Deleted history item", {"record_id": rec.id})
                    st.success("Record deleted.")
                    st.rerun()

            with st.expander("👁️ View Full Code & Output"):
                if rec.input_code:
                    st.markdown("##### Input Code:")
                    st.code(rec.input_code, language=rec.language.lower().split(" ")[0])

                if rec.generated_code:
                    st.markdown("##### AI Output / Generated Code:")
                    st.code(rec.generated_code, language=rec.language.lower().split(" ")[0])

                if rec.explanation:
                    st.markdown("##### Explanation / Notes:")
                    st.markdown(rec.explanation)

                if st.button("💬 Load into Chat Context", key=f"chat_load_{rec.id}"):
                    st.session_state.chat_context_code = rec.generated_code or rec.input_code or ""
                    st.session_state.chat_context_language = rec.language
                    st.session_state.page = "AI Coding Chat"
                    st.rerun()

            st.markdown("---")


def page_profile() -> None:
    st.markdown('<h1 class="feature-header">👤 User Profile</h1>', unsafe_allow_html=True)

    user_id = _get_current_user_id()
    if not user_id:
        st.error("User session not found.")
        return

    user_doc = auth_service.get_user_by_id(user_id)
    if not user_doc:
        sess_user = st.session_state.user or {}
        if sess_user and isinstance(sess_user, dict):
            user_doc = User(
                id=user_id,
                full_name=sess_user.get("full_name", ""),
                username=sess_user.get("username", ""),
                email=sess_user.get("email", ""),
                created_at=str(sess_user.get("created_at", "")),
            )
            st.warning("⚠️ Database connection is unavailable. Displaying cached session profile.", icon="⚠️")
        else:
            st.error("Could not load user profile from database.")
            return

    col1, col2 = st.columns([1, 1])

    with col1:
        st.markdown("### 📋 Account Information")
        st.markdown(f"**Full Name:** {user_doc.full_name}")
        st.markdown(f"**Username:** `@{user_doc.username}`")
        st.markdown(f"**Email:** `{user_doc.email}`")
        created_display = user_doc.created_at[:10] if user_doc.created_at else "Recently"
        st.markdown(f"**Account Created:** {created_display}")

        st.markdown("---")
        st.markdown("### ✏️ Edit Profile")
        with st.form("edit_profile_form"):
            new_name = st.text_input("Full Name", value=user_doc.full_name)
            new_username = st.text_input("Username", value=user_doc.username)
            save_profile = st.form_submit_button("Save Profile Changes", use_container_width=True)

        if save_profile:
            success, msg, updated_u = auth_service.update_profile(
                user_id, UserProfileUpdate(full_name=new_name, username=new_username)
            )
            if success and updated_u:
                if isinstance(st.session_state.user, dict):
                    st.session_state.user["full_name"] = updated_u.full_name
                    st.session_state.user["username"] = updated_u.username
                activity_service.log_activity(user_id, "Profile updated")
                st.success(msg)
                st.rerun()
            else:
                st.error(msg)

    with col2:
        st.markdown("### 🔒 Change Password")
        with st.form("change_pwd_form"):
            curr_pwd = st.text_input("Current Password", type="password")
            new_pwd = st.text_input("New Password", type="password")
            confirm_new_pwd = st.text_input("Confirm New Password", type="password")
            change_submitted = st.form_submit_button("Update Password", use_container_width=True)

        if change_submitted:
            req = PasswordChange(
                current_password=curr_pwd,
                new_password=new_pwd,
                confirm_new_password=confirm_new_pwd,
            )
            success, msg = auth_service.change_password(user_id, req)
            if success:
                activity_service.log_activity(user_id, "Password changed")
                st.success(msg)
            else:
                st.error(msg)

        st.markdown("---")
        st.markdown("### 🕒 Recent Activity Audit")
        activities = activity_service.get_recent_activities(user_id, limit=6)
        if not activities:
            st.info("No activity logs yet.")
        else:
            for act in activities:
                t_str = act.timestamp[:19].replace("T", " ")
                st.markdown(f"- **{act.action}** <small style='color:#8b949e;'>({t_str})</small>", unsafe_allow_html=True)


def page_settings() -> None:
    st.markdown('<h1 class="feature-header">⚙️ Settings</h1>', unsafe_allow_html=True)

    active_key = _get_active_api_key()
    active_model = _get_active_model()
    status_code, status_msg = _get_api_status()
    db_connected, db_msg = _get_db_status()

    st.markdown("### 🔌 System Diagnostics & Status")

    col1, col2 = st.columns(2)
    with col1:
        st.metric("AI Provider", settings.ai_provider.upper())
        st.metric("Active Model", active_model)
        st.metric("API Status", status_msg)
    with col2:
        st.metric("Database", settings.mongodb_database)
        st.metric("MongoDB Connection", "✅ Connected" if db_connected else "❌ Disconnected")
        key_source = "Session Override" if st.session_state.get("session_api_key") else (".env file" if settings.is_configured() else "Not set")
        st.metric("API Key Source", key_source)

    st.markdown("---")
    st.markdown("### 🛠️ Interactive Configuration")

    # Model selector
    available_models = LLMService.get_available_models(api_key=active_key)
    current_idx = available_models.index(active_model) if active_model in available_models else 0
    selected_model = st.selectbox("Gemini Model (GEMINI_MODEL):", available_models, index=current_idx)

    if selected_model != st.session_state.session_model:
        st.session_state.session_model = selected_model
        st.session_state.api_status_cached = None
        st.rerun()

    # Diagnostic buttons
    col_t1, col_t2 = st.columns(2)
    with col_t1:
        if st.button("🔄 Test Live Gemini API Connection", use_container_width=True):
            with st.spinner("Testing API connection..."):
                code, msg = _get_api_status(force_check=True)
                if code == "CONFIGURED":
                    st.success(f"Connection Successful: {msg} using `{active_model}`", icon="✅")
                elif code == "NOT_CONFIGURED":
                    st.warning("API key is not configured.", icon="⚠️")
                elif code == "AUTH_FAILED":
                    st.error("Authentication failed. Check your API key.", icon="❌")
                else:
                    st.error(f"Configuration issue: {msg}", icon="⚠️")

    with col_t2:
        if st.button("🔄 Test MongoDB Atlas Connection", use_container_width=True):
            with st.spinner("Testing database connection..."):
                ok, msg = _get_db_status(force_check=True)
                if ok:
                    st.success(msg, icon="✅")
                else:
                    st.error(msg, icon="❌")

    # Session API key override
    with st.expander("🔑 Override API Key in Current Session", expanded=not bool(active_key)):
        st.caption("Provide an API key for the current browser session. It is never stored on disk or logged.")
        temp_key = st.text_input(
            "Enter GEMINI_API_KEY (Session only):",
            value=st.session_state.session_api_key,
            type="password",
            placeholder="AIzaSy...",
        )
        col_s1, col_s2 = st.columns([1, 1])
        with col_s1:
            if st.button("Apply Key to Session", use_container_width=True):
                st.session_state.session_api_key = temp_key.strip()
                st.session_state.api_status_cached = None
                st.success("Session API key applied!")
                st.rerun()
        with col_s2:
            if st.button("Clear Session Key", use_container_width=True):
                st.session_state.session_api_key = ""
                st.session_state.api_status_cached = None
                st.rerun()

    st.markdown("---")
    st.markdown("### 📄 Persistent Environment Setup (`.env`)")
    st.code(
        f"""# .env
# AI Configuration
AI_PROVIDER=gemini
GEMINI_MODEL={active_model}
GEMINI_API_KEY=your_gemini_api_key_here

# MongoDB Atlas Persistence
MONGODB_URI=your_mongodb_atlas_connection_string
MONGODB_DATABASE=ai_coding_assistant

# File Upload Settings
MAX_FILE_SIZE_MB=2
LOG_LEVEL=INFO""",
        language="bash",
    )


# ── Sidebar Navigation (Protected) ─────────────────────────────────────────────

def render_sidebar() -> str:
    """Render sidebar for logged-in users."""
    with st.sidebar:
        st.markdown("# 🤖 AI Coding\nAssistant")

        # Current user badge
        user = st.session_state.user or {}
        display_name = user.get("full_name") or user.get("username") or "User"
        st.markdown(f"**Logged in as:**\n👤 **{display_name}** (`@{user.get('username', '')}`)")
        st.markdown("---")

        pages = {
            "🏠 Dashboard": "Dashboard",
            "✨ Generate Code": "Generate Code",
            "🐛 Debug Code": "Debug Code",
            "📖 Explain Code": "Explain Code",
            "🔧 Refactor Code": "Refactor Code",
            "🔄 Convert Code": "Convert Code",
            "🧪 Generate Tests": "Generate Tests",
            "🔐 Security Analysis": "Security Analysis",
            "📁 Analyze File": "Analyze File",
            "💬 AI Coding Chat": "AI Coding Chat",
            "📚 Coding History": "Coding History",
            "👤 Profile": "Profile",
            "⚙️ Settings": "Settings",
        }

        current = st.session_state.get("page", "Dashboard")
        for label, page_name in pages.items():
            is_active = current == page_name
            btn_type = "primary" if is_active else "secondary"
            if st.button(label, key=f"nav_{page_name}", use_container_width=True, type=btn_type):
                st.session_state.page = page_name
                st.rerun()

        st.markdown("---")
        # Live status badges
        status_code, status_text = _get_api_status()
        active_model = _get_active_model()
        if status_code == "CONFIGURED":
            st.success(f"{status_text}\n\n`{active_model}`")
        elif status_code == "AUTH_FAILED":
            st.error("⚠️ Auth Failed")
        elif status_code == "MODEL_ERROR":
            st.warning("⚠️ Model Error")
        else:
            st.error("❌ Key Missing")

        # Logout button
        st.markdown("---")
        if st.button("🚪 Log Out", use_container_width=True):
            user_id = _get_current_user_id()
            if user_id:
                activity_service.log_activity(user_id, "User logged out")
            st.session_state.authenticated = False
            st.session_state.user = None
            st.session_state.chat_history = []
            st.session_state.chat_context_code = ""
            st.session_state.page = "Dashboard"
            st.session_state.auth_view = "LOGIN"
            st.session_state.login_prefill_identifier = ""
            st.session_state.auth_flash_success = ""
            st.session_state.auth_flash_error = ""
            st.rerun()

    return st.session_state.get("page", "Dashboard")


# ── Page Router ────────────────────────────────────────────────────────────────

PAGE_MAP = {
    "Dashboard": page_dashboard,
    "Generate Code": page_generate,
    "Debug Code": page_debug,
    "Explain Code": page_explain,
    "Refactor Code": page_refactor,
    "Convert Code": page_convert,
    "Generate Tests": page_tests,
    "Security Analysis": page_security,
    "Analyze File": page_file_analyze,
    "AI Coding Chat": page_chat,
    "Coding History": page_history,
    "Profile": page_profile,
    "Settings": page_settings,
}


# ── Application Main Entry Point ───────────────────────────────────────────────

def main() -> None:
    _inject_css()
    _init_session()

    # 1. Guard: If not authenticated, force Login/Register view
    if not st.session_state.authenticated:
        render_auth_screen()
        return

    # 2. Render authenticated sidebar and route to selected protected page
    current_page = render_sidebar()
    page_fn = PAGE_MAP.get(current_page, page_dashboard)
    page_fn()


if __name__ == "__main__":
    main()
