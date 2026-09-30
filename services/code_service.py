"""
services/code_service.py

High-level orchestration service for code-related features.
Wraps LLMService and adds input validation before calling the AI.
"""
from __future__ import annotations

from models.schemas import (
    AIError,
    CodeGenerationRequest,
    CodeGenerationResponse,
    ConvertRequest,
    ConvertResponse,
    DebugRequest,
    DebugResponse,
    ExplainRequest,
    ExplainResponse,
    RefactorRequest,
    RefactorResponse,
    TestGenerationRequest,
    TestGenerationResponse,
)
from services.llm_service import LLMService
from utils.logger import get_logger

logger = get_logger(__name__)

# Character limits for input validation
_MAX_CODE_CHARS = 15_000
_MAX_REQUIREMENTS_CHARS = 3_000


def _validation_error(message: str) -> AIError:
    return AIError(code="VALIDATION_ERROR", message=message)


class CodeService:
    """
    Orchestrates code-related AI features with input validation.
    Creates its own LLMService instance on demand.
    """

    def __init__(self, llm: LLMService) -> None:
        self._llm = llm

    # ── Generate ───────────────────────────────────────────────────────────────

    def generate(self, request: CodeGenerationRequest) -> CodeGenerationResponse:
        """Validate and generate code from requirements."""
        if not request.requirements.strip():
            return CodeGenerationResponse(
                generated_code="",
                explanation="",
                error=_validation_error("Requirements cannot be empty."),
            )
        if len(request.requirements) > _MAX_REQUIREMENTS_CHARS:
            return CodeGenerationResponse(
                generated_code="",
                explanation="",
                error=_validation_error(
                    f"Requirements too long (max {_MAX_REQUIREMENTS_CHARS} characters)."
                ),
            )
        if not request.language.strip():
            return CodeGenerationResponse(
                generated_code="",
                explanation="",
                error=_validation_error("Programming language must be specified."),
            )
        return self._llm.generate_code(request)

    # ── Explain ────────────────────────────────────────────────────────────────

    def explain(self, request: ExplainRequest) -> ExplainResponse:
        """Validate and explain code."""
        if not request.code.strip():
            return ExplainResponse(
                summary="",
                line_by_line="",
                error=_validation_error("Code cannot be empty."),
            )
        if len(request.code) > _MAX_CODE_CHARS:
            return ExplainResponse(
                summary="",
                line_by_line="",
                error=_validation_error(
                    f"Code too long (max {_MAX_CODE_CHARS} characters). "
                    "Please paste a smaller snippet."
                ),
            )
        return self._llm.explain_code(request)

    # ── Debug ──────────────────────────────────────────────────────────────────

    def debug(self, request: DebugRequest) -> DebugResponse:
        """Validate and debug code."""
        if not request.code.strip():
            return DebugResponse(
                problem_explanation="",
                root_cause="",
                corrected_code="",
                explanation_of_changes="",
                prevention_advice="",
                error=_validation_error("Code cannot be empty."),
            )
        if len(request.code) > _MAX_CODE_CHARS:
            return DebugResponse(
                problem_explanation="",
                root_cause="",
                corrected_code="",
                explanation_of_changes="",
                prevention_advice="",
                error=_validation_error(
                    f"Code too long (max {_MAX_CODE_CHARS} characters)."
                ),
            )
        return self._llm.debug_code(request)

    # ── Refactor ───────────────────────────────────────────────────────────────

    def refactor(self, request: RefactorRequest) -> RefactorResponse:
        """Validate and refactor code."""
        if not request.code.strip():
            return RefactorResponse(
                refactored_code="",
                explanation_of_changes="",
                error=_validation_error("Code cannot be empty."),
            )
        if len(request.code) > _MAX_CODE_CHARS:
            return RefactorResponse(
                refactored_code="",
                explanation_of_changes="",
                error=_validation_error(f"Code too long (max {_MAX_CODE_CHARS} characters)."),
            )
        return self._llm.refactor_code(request)

    # ── Convert ────────────────────────────────────────────────────────────────

    def convert(self, request: ConvertRequest) -> ConvertResponse:
        """Validate and convert code between languages."""
        if not request.code.strip():
            return ConvertResponse(
                converted_code="",
                error=_validation_error("Code cannot be empty."),
            )
        if request.source_language.strip().lower() == request.target_language.strip().lower():
            return ConvertResponse(
                converted_code="",
                error=_validation_error("Source and target languages must be different."),
            )
        if len(request.code) > _MAX_CODE_CHARS:
            return ConvertResponse(
                converted_code="",
                error=_validation_error(f"Code too long (max {_MAX_CODE_CHARS} characters)."),
            )
        return self._llm.convert_code(request)

    # ── Generate Tests ─────────────────────────────────────────────────────────

    def generate_tests(self, request: TestGenerationRequest) -> TestGenerationResponse:
        """Validate and generate unit tests."""
        if not request.code.strip():
            return TestGenerationResponse(
                test_code="",
                error=_validation_error("Code cannot be empty."),
            )
        if len(request.code) > _MAX_CODE_CHARS:
            return TestGenerationResponse(
                test_code="",
                error=_validation_error(f"Code too long (max {_MAX_CODE_CHARS} characters)."),
            )
        return self._llm.generate_tests(request)
