"""
services/llm_service.py

The LLM service abstraction layer.
All AI calls go through this module — app.py and other services never
import google-genai directly.

Design:
  - GeminiProvider implements the low-level API calls via google-genai SDK.
  - LLMService wraps the provider and exposes clean, task-specific methods.
  - Adding a new provider (e.g. OpenAI-compatible) only requires a new
    provider class and a one-line change in LLMService.__init__.
"""
from __future__ import annotations

import re
from typing import Any, List, Optional, Tuple

from config.settings import settings
from models.schemas import (
    AIError,
    ChatMessage,
    ChatRequest,
    ChatResponse,
    CodeGenerationRequest,
    CodeGenerationResponse,
    ConvertRequest,
    ConvertResponse,
    DebugRequest,
    DebugResponse,
    ExplainRequest,
    ExplainResponse,
    RefactorIssue,
    RefactorRequest,
    RefactorResponse,
    SecurityFinding,
    SecurityRequest,
    SecurityResponse,
    SeverityLevel,
    TestGenerationRequest,
    TestGenerationResponse,
)
from prompts import (
    build_convert_prompt,
    build_debug_prompt,
    build_explain_prompt,
    build_generate_prompt,
    build_refactor_prompt,
    build_security_prompt,
    build_tests_prompt,
)
from utils.helpers import clean_code_fence, extract_section, truncate_text
from utils.logger import get_logger

logger = get_logger(__name__)

# ── Chat system instruction ────────────────────────────────────────────────────

_CHAT_SYSTEM = (
    "You are an expert AI coding assistant. "
    "Your role is to help developers write, understand, debug, optimize, and review code. "
    "Be concise, accurate, and technical. "
    "Format code in markdown code blocks with the correct language tag. "
    "Never fabricate libraries or APIs that do not exist. "
    "If you are unsure, say so clearly."
)

_MAX_CHAT_HISTORY = 20  # keep last N messages to prevent context bloat

# Standard recommended Gemini models in order of preference
RECOMMENDED_MODELS = [
    "gemini-flash-latest",
    "gemini-3.8-flash",
    "gemini-3.5-flash-lite",
    "gemini-3.1-pro-preview",
    "gemini-flash-lite-latest",
    "gemini-pro-latest",
]


# ── Gemini Provider ────────────────────────────────────────────────────────────


class GeminiProvider:
    """
    Wrapper around the official google-genai SDK.
    Uses client.models.generate_content() and client.interactions.create().
    Reuses the client instance rather than recreating it on every call.
    """

    def __init__(self, api_key: str, model: str) -> None:
        if not api_key or not api_key.strip():
            raise ValueError("API key must not be empty.")

        try:
            from google import genai
        except ImportError as exc:
            raise ImportError(
                "google-genai package is not installed. Run: pip install google-genai"
            ) from exc

        self._api_key = api_key.strip().strip("\"'")
        self._model = model.strip() if model and model.strip() else "gemini-flash-latest"
        self._client = genai.Client(api_key=self._api_key)
        logger.info("GeminiProvider initialized with model: %s", self._model)

    @classmethod
    def validate_connection(cls, api_key: str, model: str) -> Tuple[str, str]:
        """
        Validate the API key and model against the live Gemini API.

        Returns:
            Tuple of (status_code, display_message)
            - ("CONFIGURED", "✅ Configured")
            - ("NOT_CONFIGURED", "❌ Not configured")
            - ("AUTH_FAILED", "⚠️ Authentication failed")
            - ("MODEL_ERROR", "⚠️ Model configuration error")
        """
        if not api_key or not api_key.strip():
            return "NOT_CONFIGURED", "❌ Not configured"

        try:
            from google import genai
            from google.genai.errors import ClientError, ServerError
        except ImportError:
            return "NOT_CONFIGURED", "❌ SDK not installed"

        clean_key = api_key.strip().strip("\"'")
        clean_model = model.strip() if model and model.strip() else "gemini-flash-latest"

        try:
            client = genai.Client(api_key=clean_key)
            # Lightweight verification: query model metadata
            client.models.get(model=clean_model)
            return "CONFIGURED", "✅ Configured"
        except Exception as exc:
            err_str = str(exc).lower()
            logger.warning("Connection validation check result: %s", exc)

            if "not_found" in err_str or "404" in err_str or "is not found" in err_str:
                return "MODEL_ERROR", "⚠️ Model configuration error"
            if any(w in err_str for w in ["auth", "key", "permission", "401", "403", "unauthenticated", "invalid_argument"]):
                return "AUTH_FAILED", "⚠️ Authentication failed"
            if "503" in err_str or "unavailable" in err_str or "high demand" in err_str:
                return "CONFIGURED", "✅ Configured (High Demand)"
            return "AUTH_FAILED", "⚠️ Authentication failed"

    @classmethod
    def list_available_models(cls, api_key: str) -> List[str]:
        """
        Query available models from the Gemini API using the SDK.
        Returns a fallback list if listing fails.
        """
        if not api_key or not api_key.strip():
            return RECOMMENDED_MODELS

        try:
            from google import genai
            client = genai.Client(api_key=api_key.strip().strip("\"'"))
            discovered = []
            for m in client.models.list():
                name = m.name or ""
                if name.startswith("models/"):
                    name = name[len("models/"):]
                if "gemini" in name and not any(k in name for k in ["embed", "vision", "imagen", "tts", "transcribe"]):
                    discovered.append(name)
            return discovered if discovered else RECOMMENDED_MODELS
        except Exception as exc:
            logger.debug("Could not dynamically list models: %s", exc)
            return RECOMMENDED_MODELS

    def complete(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        temperature: float = 0.2,
    ) -> str:
        """
        Send a prompt to Gemini and return the text response.
        Uses generate_content with automatic candidate model fallbacks if a model is busy.
        """
        from google.genai import types

        # Models to try in order of preference
        candidate_models = [self._model]
        for fb in ["gemini-flash-latest", "gemini-3.5-flash-lite", "gemini-flash-lite-latest", "gemini-3.8-flash"]:
            if fb not in candidate_models:
                candidate_models.append(fb)

        last_error: Optional[Exception] = None

        for model_name in candidate_models:
            try:
                cfg = types.GenerateContentConfig(
                    temperature=temperature,
                    system_instruction=system_instruction if system_instruction else None,
                )
                res = self._client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                    config=cfg,
                )
                text = res.text or ""
                if text.strip():
                    return text
            except Exception as exc:
                logger.warning("generate_content failed for %s (%s): %s", model_name, type(exc).__name__, exc)
                last_error = exc
                # Try next candidate model

        if last_error:
            raise last_error
        raise RuntimeError("No response was returned from the AI model.")

    def chat(
        self,
        messages: List[ChatMessage],
        system_instruction: str = _CHAT_SYSTEM,
        temperature: float = 0.3,
    ) -> str:
        """
        Multi-turn chat using the Gemini provider.
        """
        conversation_parts = []
        for msg in messages[-(2 * _MAX_CHAT_HISTORY):]:
            role_label = "User" if msg.role == "user" else "Assistant"
            conversation_parts.append(f"{role_label}: {msg.content}")

        full_prompt = "\n\n".join(conversation_parts)
        full_prompt += "\n\nAssistant:"

        return self.complete(
            prompt=full_prompt,
            system_instruction=system_instruction,
            temperature=temperature,
        )


# ── LLM Service ───────────────────────────────────────────────────────────────


class LLMService:
    """
    High-level service that maps application features to LLM calls.
    Prompt building and response parsing happen here; app.py stays clean.
    """

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None) -> None:
        key = api_key or settings.api_key
        mod = model or settings.active_model

        if not key or not key.strip():
            raise ValueError(
                "API key is not configured. Please set GEMINI_API_KEY in your .env file or Settings."
            )

        if settings.ai_provider == "gemini":
            self._provider = GeminiProvider(
                api_key=key,
                model=mod,
            )
        else:
            raise ValueError(f"Unsupported AI provider: {settings.ai_provider}")

    @classmethod
    def check_api_status(cls, api_key: Optional[str] = None, model: Optional[str] = None) -> Tuple[str, str]:
        """Check API configuration and connectivity."""
        key = api_key or settings.api_key
        mod = model or settings.active_model
        return GeminiProvider.validate_connection(key, mod)

    @classmethod
    def get_available_models(cls, api_key: Optional[str] = None) -> List[str]:
        """Return list of available models for selection."""
        key = api_key or settings.api_key
        return GeminiProvider.list_available_models(key)

    # ── Public task methods ────────────────────────────────────────────────────

    def generate_code(self, request: CodeGenerationRequest) -> CodeGenerationResponse:
        """Generate code from natural-language requirements."""
        try:
            prompt = build_generate_prompt(request)
            raw = self._provider.complete(prompt, temperature=0.3)
            return self._parse_generate_response(raw)
        except Exception as exc:
            logger.error("generate_code error: %s", exc)
            return CodeGenerationResponse(
                generated_code="",
                explanation="",
                error=self._make_error(exc),
            )

    def explain_code(self, request: ExplainRequest) -> ExplainResponse:
        """Explain what a piece of code does."""
        try:
            request.code = truncate_text(request.code)
            prompt = build_explain_prompt(request)
            raw = self._provider.complete(prompt, temperature=0.1)
            return self._parse_explain_response(raw)
        except Exception as exc:
            logger.error("explain_code error: %s", exc)
            return ExplainResponse(
                summary="",
                line_by_line="",
                error=self._make_error(exc),
            )

    def debug_code(self, request: DebugRequest) -> DebugResponse:
        """Identify and fix bugs in code."""
        try:
            request.code = truncate_text(request.code)
            prompt = build_debug_prompt(request)
            raw = self._provider.complete(prompt, temperature=0.1)
            return self._parse_debug_response(raw)
        except Exception as exc:
            logger.error("debug_code error: %s", exc)
            return DebugResponse(
                problem_explanation="",
                root_cause="",
                corrected_code="",
                explanation_of_changes="",
                prevention_advice="",
                error=self._make_error(exc),
            )

    def refactor_code(self, request: RefactorRequest) -> RefactorResponse:
        """Suggest and apply code refactoring improvements."""
        try:
            request.code = truncate_text(request.code)
            prompt = build_refactor_prompt(request)
            raw = self._provider.complete(prompt, temperature=0.2)
            return self._parse_refactor_response(raw)
        except Exception as exc:
            logger.error("refactor_code error: %s", exc)
            return RefactorResponse(
                refactored_code="",
                explanation_of_changes="",
                error=self._make_error(exc),
            )

    def convert_code(self, request: ConvertRequest) -> ConvertResponse:
        """Convert code from one programming language to another."""
        try:
            request.code = truncate_text(request.code)
            prompt = build_convert_prompt(request)
            raw = self._provider.complete(prompt, temperature=0.2)
            return self._parse_convert_response(raw)
        except Exception as exc:
            logger.error("convert_code error: %s", exc)
            return ConvertResponse(
                converted_code="",
                error=self._make_error(exc),
            )

    def generate_tests(self, request: TestGenerationRequest) -> TestGenerationResponse:
        """Generate unit tests for provided code."""
        try:
            request.code = truncate_text(request.code)
            prompt = build_tests_prompt(request)
            raw = self._provider.complete(prompt, temperature=0.2)
            return self._parse_tests_response(raw)
        except Exception as exc:
            logger.error("generate_tests error: %s", exc)
            return TestGenerationResponse(
                test_code="",
                error=self._make_error(exc),
            )

    def security_analysis(self, request: SecurityRequest) -> SecurityResponse:
        """Analyze code for security vulnerabilities."""
        try:
            request.code = truncate_text(request.code)
            prompt = build_security_prompt(request)
            raw = self._provider.complete(prompt, temperature=0.1)
            return self._parse_security_response(raw)
        except Exception as exc:
            logger.error("security_analysis error: %s", exc)
            return SecurityResponse(
                error=self._make_error(exc),
            )

    def chat(self, request: ChatRequest) -> ChatResponse:
        """Multi-turn AI coding chat."""
        try:
            if request.context_code:
                lang = request.context_language or ""
                ctx_msg = ChatMessage(
                    role="user",
                    content=(
                        f"[Context — {lang} code:]\n```{lang.lower()}\n"
                        f"{truncate_text(request.context_code, 4000)}\n```"
                    ),
                )
                messages = [ctx_msg] + request.history
            else:
                messages = request.history

            reply = self._provider.chat(messages, temperature=0.4)
            return ChatResponse(reply=reply)
        except Exception as exc:
            logger.error("chat error: %s", exc)
            return ChatResponse(reply="", error=self._make_error(exc))

    # ── Response parsers ───────────────────────────────────────────────────────

    def _parse_generate_response(self, raw: str) -> CodeGenerationResponse:
        code = self._extract_code_block(raw, section="Generated Code")
        explanation = extract_section(raw, "Explanation")
        deps_raw = extract_section(raw, "Dependencies")
        how_to_run = extract_section(raw, "How to Run")
        improvements_raw = extract_section(raw, "Potential Improvements")

        deps = self._parse_bullet_list(deps_raw)
        improvements = self._parse_bullet_list(improvements_raw)

        return CodeGenerationResponse(
            generated_code=code or raw,
            explanation=explanation,
            dependencies=[d for d in deps if d.lower() != "none"],
            how_to_run=how_to_run,
            potential_improvements=improvements,
        )

    def _parse_explain_response(self, raw: str) -> ExplainResponse:
        return ExplainResponse(
            summary=extract_section(raw, "Summary"),
            line_by_line=extract_section(raw, "Line-by-Line Explanation"),
            important_concepts=self._parse_bullet_list(
                extract_section(raw, "Important Concepts")
            ),
            inputs=extract_section(raw, "Inputs"),
            outputs=extract_section(raw, "Outputs"),
            complexity=extract_section(raw, "Complexity") or None,
            potential_problems=self._parse_bullet_list(
                extract_section(raw, "Potential Problems")
            ),
            beginner_explanation=extract_section(raw, "Beginner Explanation"),
        )

    def _parse_debug_response(self, raw: str) -> DebugResponse:
        return DebugResponse(
            problem_explanation=extract_section(raw, "Problem Explanation"),
            root_cause=extract_section(raw, "Root Cause"),
            corrected_code=self._extract_code_block(raw, "Corrected Code"),
            explanation_of_changes=extract_section(raw, "Explanation of Changes"),
            prevention_advice=extract_section(raw, "Prevention Advice"),
        )

    def _parse_refactor_response(self, raw: str) -> RefactorResponse:
        issues_raw = extract_section(raw, "Issues Found")
        issues = self._parse_refactor_issues(issues_raw)
        return RefactorResponse(
            issues_found=issues,
            refactored_code=self._extract_code_block(raw, "Refactored Code"),
            explanation_of_changes=extract_section(raw, "Explanation of Changes"),
        )

    def _parse_convert_response(self, raw: str) -> ConvertResponse:
        code = self._extract_code_block(raw)
        diff_raw = extract_section(raw, "Important Differences")
        deps_raw = extract_section(raw, "Dependencies")
        notes = extract_section(raw, "Behavior Notes")
        return ConvertResponse(
            converted_code=code or raw,
            important_differences=self._parse_bullet_list(diff_raw),
            dependencies=[d for d in self._parse_bullet_list(deps_raw) if d.lower() != "none"],
            behavior_notes=notes,
        )

    def _parse_tests_response(self, raw: str) -> TestGenerationResponse:
        return TestGenerationResponse(
            test_code=self._extract_code_block(raw, "Test Code"),
            test_cases_covered=self._parse_bullet_list(
                extract_section(raw, "Test Cases Covered")
            ),
            edge_cases=self._parse_bullet_list(extract_section(raw, "Edge Cases")),
            missing_cases=self._parse_bullet_list(extract_section(raw, "Missing Cases")),
        )

    def _parse_security_response(self, raw: str) -> SecurityResponse:
        findings_raw = extract_section(raw, "Findings")
        findings = self._parse_security_findings(findings_raw)
        risk_raw = extract_section(raw, "Overall Risk").strip().upper()
        try:
            overall_risk = SeverityLevel(risk_raw)
        except ValueError:
            overall_risk = SeverityLevel.INFO
        return SecurityResponse(
            findings=findings,
            overall_risk=overall_risk,
            summary=extract_section(raw, "Summary"),
        )

    # ── Helper methods ─────────────────────────────────────────────────────────

    @staticmethod
    def _extract_code_block(text: str, section: Optional[str] = None) -> str:
        """
        Extract code block from markdown text.
        """
        target_text = text
        if section:
            section_text = extract_section(text, section)
            if section_text:
                target_text = section_text

        pattern = re.compile(r"```[a-zA-Z0-9_+-]*\n?(.*?)```", re.DOTALL)
        match = pattern.search(target_text)
        if match:
            return match.group(1).strip()

        if not section:
            return clean_code_fence(text)

        match_any = pattern.search(text)
        return match_any.group(1).strip() if match_any else clean_code_fence(target_text)

    @staticmethod
    def _parse_bullet_list(text: str) -> List[str]:
        """Parse a markdown bullet list into a Python list of strings."""
        lines = []
        for line in text.splitlines():
            line = line.strip()
            if line.startswith(("- ", "* ", "• ")):
                item = line[2:].strip()
                if item:
                    lines.append(item)
            elif re.match(r"^\d+\.\s", line):
                item = re.sub(r"^\d+\.\s+", "", line).strip()
                if item:
                    lines.append(item)
        return lines

    @staticmethod
    def _parse_refactor_issues(text: str) -> List[RefactorIssue]:
        """Parse structured refactor issue blocks from the response."""
        issues: List[RefactorIssue] = []
        blocks = re.split(r"\n(?=\*\*Issue\*\*)", text)
        for block in blocks:
            issue_match = re.search(r"\*\*Issue\*\*:\s*(.+)", block)
            sev_match = re.search(r"\*\*Severity\*\*:\s*(.+)", block)
            reason_match = re.search(r"\*\*Reason\*\*:\s*(.+)", block, re.DOTALL)
            if issue_match:
                issues.append(
                    RefactorIssue(
                        issue=issue_match.group(1).strip(),
                        severity=(sev_match.group(1).strip() if sev_match else "MEDIUM"),
                        reason=(reason_match.group(1).strip() if reason_match else ""),
                    )
                )
        return issues

    @staticmethod
    def _parse_security_findings(text: str) -> List[SecurityFinding]:
        """Parse security finding blocks from the response."""
        findings: List[SecurityFinding] = []
        blocks = re.split(r"\n---\n|\n(?=\*\*(?:CRITICAL|HIGH|MEDIUM|LOW|INFO)\*\*)", text)

        severity_pattern = re.compile(
            r"\*\*\s*(CRITICAL|HIGH|MEDIUM|LOW|INFO)\s*\*\*\s*[—-]\s*(.+)", re.IGNORECASE
        )

        for block in blocks:
            block = block.strip()
            if not block:
                continue

            sev_match = severity_pattern.search(block)
            if not sev_match:
                continue

            try:
                severity = SeverityLevel(sev_match.group(1).upper())
            except ValueError:
                severity = SeverityLevel.INFO

            title = sev_match.group(2).strip()
            loc_match = re.search(r"\*\*Location\*\*:\s*(.+)", block)
            desc_match = re.search(r"\*\*Description\*\*:\s*(.+?)(?=\*\*|$)", block, re.DOTALL)
            rem_match = re.search(r"\*\*Remediation\*\*:\s*(.+?)(?=\*\*|$)", block, re.DOTALL)

            findings.append(
                SecurityFinding(
                    severity=severity,
                    title=title,
                    location=(loc_match.group(1).strip() if loc_match else None),
                    description=(desc_match.group(1).strip() if desc_match else ""),
                    remediation=(rem_match.group(1).strip() if rem_match else ""),
                )
            )

        return findings

    @staticmethod
    def _make_error(exc: Exception) -> AIError:
        """Convert an exception into a user-friendly AIError model."""
        exc_str = str(exc)
        exc_lower = exc_str.lower()
        exc_type = type(exc).__name__

        logger.error("LLM execution error [%s]: %s", exc_type, exc_str)

        if any(w in exc_lower for w in ["api_key", "unauthenticated", "invalid_argument", "permission", "401", "403"]):
            return AIError(
                code="AUTH_ERROR",
                message="Authentication failed. Please check your GEMINI_API_KEY in .env or Settings.",
                details=exc_str,
            )
        if any(w in exc_lower for w in ["not_found", "404", "is not found"]):
            return AIError(
                code="MODEL_ERROR",
                message="Configured model not found or unavailable. Please check GEMINI_MODEL in Settings.",
                details=exc_str,
            )
        if any(w in exc_lower for w in ["quota", "rate", "429", "resource_exhausted"]):
            return AIError(
                code="RATE_LIMIT",
                message="API rate limit or quota exceeded. Please wait a moment and try again.",
                details=exc_str,
            )
        if any(w in exc_lower for w in ["503", "unavailable", "high demand"]):
            return AIError(
                code="SERVICE_UNAVAILABLE",
                message="The model is currently experiencing high demand. Please try again in a few moments.",
                details=exc_str,
            )
        if any(w in exc_lower for w in ["timeout", "timed out", "deadline_exceeded"]):
            return AIError(
                code="TIMEOUT",
                message="The request timed out. Please try again with a shorter code snippet.",
                details=exc_str,
            )
        if any(w in exc_lower for w in ["network", "connect", "connection", "socket"]):
            return AIError(
                code="NETWORK_ERROR",
                message="Network error connecting to Gemini API. Please check your internet connection.",
                details=exc_str,
            )

        return AIError(
            code="AI_SERVICE_ERROR",
            message=f"An error occurred while contacting the AI service: {exc_str[:120]}",
            details=exc_str,
        )
