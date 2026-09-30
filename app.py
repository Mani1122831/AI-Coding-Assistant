"""
app.py
AI Coding Assistant — Streamlit application entry point.

This file handles:
- Page configuration and custom CSS
- Sidebar navigation
- Routing to feature pages
- High-level session state management and live API status check

Business logic lives in services/.
Prompt engineering lives in prompts/.
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
from config.settings import settings
from models.schemas import (
    ChatMessage,
    ChatRequest,
    CodeGenerationRequest,
    ConvertRequest,
    DebugRequest,
    ExplainRequest,
    RefactorRequest,
    SecurityRequest,
    TestGenerationRequest,
)
from services.file_service import FileService
from services.llm_service import LLMService, RECOMMENDED_MODELS
from services.code_service import CodeService
from services.security_service import SecurityService
from utils.helpers import (
    build_language_list,
    format_file_size,
)

# ── Custom CSS ─────────────────────────────────────────────────────────────────

def _inject_css() -> None:
    st.markdown(
        """
        <style>
        /* ── Base ── */
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

        /* ── Info / success / error boxes ── */
        .st-emotion-cache-1kyxreq { border-radius: 8px; }

        /* ── Buttons ── */
        .stButton > button {
            border-radius: 6px;
            font-weight: 600;
            transition: all 0.15s ease;
        }
        .stButton > button:hover { opacity: 0.85; }

        /* ── Severity badges ── */
        .badge-critical { background:#da3633; color:#fff; padding:2px 8px; border-radius:4px; font-weight:700; font-size:0.8rem; }
        .badge-high     { background:#e3b341; color:#000; padding:2px 8px; border-radius:4px; font-weight:700; font-size:0.8rem; }
        .badge-medium   { background:#d29922; color:#000; padding:2px 8px; border-radius:4px; font-weight:700; font-size:0.8rem; }
        .badge-low      { background:#388bfd; color:#fff; padding:2px 8px; border-radius:4px; font-weight:700; font-size:0.8rem; }
        .badge-info     { background:#3d444d; color:#e6edf3; padding:2px 8px; border-radius:4px; font-weight:700; font-size:0.8rem; }

        /* ── Section headers ── */
        .feature-header {
            border-bottom: 2px solid #21262d;
            padding-bottom: 0.5rem;
            margin-bottom: 1.5rem;
            color: #e6edf3;
        }

        /* ── Chat messages ── */
        .chat-user { background:#1c2128; border-left:3px solid #58a6ff; padding:0.75rem 1rem; border-radius:4px; margin-bottom:0.5rem; }
        .chat-assistant { background:#161b22; border-left:3px solid #3fb950; padding:0.75rem 1rem; border-radius:4px; margin-bottom:0.5rem; }

        /* ── Empty state ── */
        .empty-state { text-align:center; padding:3rem; color:#8b949e; }
        </style>
        """,
        unsafe_allow_html=True,
    )


# ── Session state helpers ──────────────────────────────────────────────────────

def _init_session() -> None:
    """Initialise all required session state keys."""
    defaults = {
        "page": "Dashboard",
        "chat_history": [],   # List[ChatMessage]
        "chat_context_code": "",
        "chat_context_language": "",
        "file_content": "",
        "file_language": "",
        "file_name": "",
        "session_api_key": "",
        "session_model": settings.active_model,
        "api_status_cached": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def _get_active_api_key() -> str:
    """Return active API key (session override or settings)."""
    return (st.session_state.get("session_api_key") or settings.api_key).strip()


def _get_active_model() -> str:
    """Return active model name (session override or settings)."""
    return (st.session_state.get("session_model") or settings.active_model).strip()


def _get_api_status(force_check: bool = False) -> tuple[str, str]:
    """
    Check API status and cache the result in session state.
    Returns: (status_code, display_text)
    """
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


def _get_llm() -> LLMService | None:
    """Return an initialized LLMService, or None if key is missing."""
    api_key = _get_active_api_key()
    model = _get_active_model()
    if not api_key:
        return None
    try:
        return LLMService(api_key=api_key, model=model)
    except Exception as exc:
        st.error(f"Failed to initialise AI service: {exc}")
        return None


def _require_llm() -> LLMService | None:
    """Show appropriate warning and return None if LLM is not ready."""
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

    llm = _get_llm()
    return llm


# ── Pages ──────────────────────────────────────────────────────────────────────

def page_dashboard() -> None:
    st.markdown('<h1 class="feature-header">🏠 Dashboard</h1>', unsafe_allow_html=True)

    status_code, status_text = _get_api_status()
    active_model = _get_active_model()

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("AI Provider", settings.ai_provider.upper())
    with col2:
        st.metric("Model", active_model)
    with col3:
        st.metric("API Status", status_text)

    st.markdown("---")
    st.markdown("### 🚀 Quick Start")

    if status_code == "NOT_CONFIGURED":
        st.info(
            "**Get started in 2 steps:**\n\n"
            "1. Set `GEMINI_API_KEY` in your `.env` file (or enter it in **Settings**)\n"
            "2. Get your free API key at [Google AI Studio](https://aistudio.google.com/app/apikey)\n\n"
            "Then select any feature from the sidebar to begin.",
            icon="ℹ️",
        )
    elif status_code == "AUTH_FAILED":
        st.error(
            "⚠️ **API Key Authentication Failed.** "
            "Please verify that your `GEMINI_API_KEY` is correct in `.env` or in **Settings**.",
            icon="⚠️",
        )
    elif status_code == "MODEL_ERROR":
        st.warning(
            f"⚠️ **Model Configuration Issue.** Model `{active_model}` could not be resolved. "
            "Please select a recommended model (e.g. `gemini-flash-latest`) in **Settings**.",
            icon="⚠️",
        )
    else:
        st.success(f"AI service is connected and ready using `{active_model}`.", icon="✅")

    st.markdown("---")
    st.markdown("### ✨ Features")
    features = [
        ("✨ Generate Code", "Describe what you want — get production-ready code"),
        ("🐛 Debug Code", "Paste buggy code + error message → get the fix"),
        ("📖 Explain Code", "Understand any code snippet in plain English"),
        ("🔧 Refactor Code", "Improve code quality without changing behavior"),
        ("🔄 Convert Code", "Translate code between programming languages"),
        ("🧪 Generate Tests", "Auto-generate pytest, unittest, or Jest tests"),
        ("🔐 Security Analysis", "Scan code for vulnerabilities and get fixes"),
        ("📁 Analyze File", "Upload source files for AI-powered analysis"),
        ("💬 AI Coding Chat", "Chat with AI about your code in context"),
    ]
    cols = st.columns(3)
    for i, (name, desc) in enumerate(features):
        with cols[i % 3]:
            st.markdown(f"**{name}**\n\n{desc}")


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

        # Overall risk badge
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
                    if r.beginner_explanation:
                        with st.expander("🎓 Beginner Explanation"):
                            st.markdown(r.beginner_explanation)

            elif action == "🐛 Debug":
                err_msg = st.text_input("Error message (optional):", key="file_debug_err")
                from services.code_service import CodeService as CS
                with st.spinner("Debugging..."):
                    r = CS(llm).debug(DebugRequest(language=language, code=code, error_message=err_msg or None))
                if r.error:
                    st.error(r.error.message)
                else:
                    st.markdown("#### Problem")
                    st.markdown(r.problem_explanation)
                    st.markdown("#### Fixed Code")
                    st.code(r.corrected_code, language=language.lower())

            elif action == "🔧 Refactor":
                from services.code_service import CodeService as CS
                with st.spinner("Refactoring..."):
                    r = CS(llm).refactor(RefactorRequest(language=language, code=code))
                if r.error:
                    st.error(r.error.message)
                else:
                    st.markdown("#### Refactored Code")
                    st.code(r.refactored_code, language=language.lower())
                    st.markdown("#### Changes")
                    st.markdown(r.explanation_of_changes)

            elif action == "🔐 Security Analysis":
                with st.spinner("Running security analysis..."):
                    r = SecurityService(llm).analyze(SecurityRequest(language=language, code=code))
                if r.error:
                    st.error(r.error.message)
                else:
                    st.markdown(f"**Overall Risk:** {r.overall_risk.value}")
                    for f in r.findings:
                        st.warning(f"**[{f.severity.value}] {f.title}:** {f.description}")

            elif action == "🧪 Generate Tests":
                from services.code_service import CodeService as CS
                with st.spinner("Generating tests..."):
                    r = CS(llm).generate_tests(TestGenerationRequest(language=language, code=code))
                if r.error:
                    st.error(r.error.message)
                else:
                    st.code(r.test_code, language=language.lower())

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
            st.rerun()


def page_settings() -> None:
    st.markdown('<h1 class="feature-header">⚙️ Settings</h1>', unsafe_allow_html=True)

    active_key = _get_active_api_key()
    active_model = _get_active_model()
    status_code, status_msg = _get_api_status()

    st.markdown("### 🔌 AI Provider & Model Configuration")

    col1, col2 = st.columns(2)
    with col1:
        st.metric("AI Provider", settings.ai_provider.upper())
        st.metric("Active Model", active_model)
    with col2:
        st.metric("API Status", status_msg)
        key_source = "Session Override" if st.session_state.get("session_api_key") else (".env file" if settings.is_configured() else "Not set")
        st.metric("Key Source", key_source)

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

    # Optional runtime API key configuration
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

    # Test Connection button
    if st.button("🔄 Test Live API Connection", use_container_width=True, type="primary"):
        with st.spinner("Testing connection to Gemini API..."):
            code, msg = _get_api_status(force_check=True)
            if code == "CONFIGURED":
                st.success(f"Connection Successful: {msg} using `{active_model}`", icon="✅")
            elif code == "NOT_CONFIGURED":
                st.warning("API key is not configured.", icon="⚠️")
            elif code == "AUTH_FAILED":
                st.error("Authentication failed. Check your API key.", icon="❌")
            else:
                st.error(f"Configuration issue: {msg}", icon="⚠️")

    st.markdown("---")
    st.markdown("### 📄 Persistent Configuration via `.env`")
    st.markdown(
        "To configure the API key permanently without entering it every time, set it in your `.env` file:"
    )
    st.code(
        f"""# .env
AI_PROVIDER=gemini
GEMINI_MODEL={active_model}
GEMINI_API_KEY=your_actual_api_key_here
MAX_FILE_SIZE_MB=2
LOG_LEVEL=INFO""",
        language="bash",
    )

    st.info(
        "Get your free Gemini API key at [Google AI Studio](https://aistudio.google.com/app/apikey)",
        icon="🔑",
    )


# ── Sidebar navigation ─────────────────────────────────────────────────────────

def render_sidebar() -> str:
    with st.sidebar:
        st.markdown("# 🤖 AI Coding\nAssistant")
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
        # Live status indicator
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

    return st.session_state.get("page", "Dashboard")


# ── Router ─────────────────────────────────────────────────────────────────────

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
    "Settings": page_settings,
}


# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    _inject_css()
    _init_session()
    current_page = render_sidebar()
    page_fn = PAGE_MAP.get(current_page, page_dashboard)
    page_fn()


if __name__ == "__main__":
    main()
