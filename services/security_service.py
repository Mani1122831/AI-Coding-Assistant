"""
services/security_service.py

Security analysis orchestration service.
Wraps LLMService with input validation for the security feature.
"""
from __future__ import annotations

from models.schemas import AIError, SecurityRequest, SecurityResponse
from services.llm_service import LLMService
from utils.logger import get_logger

logger = get_logger(__name__)

_MAX_CODE_CHARS = 15_000


def _validation_error(message: str) -> AIError:
    return AIError(code="VALIDATION_ERROR", message=message)


class SecurityService:
    """
    Validates and dispatches security analysis requests.
    """

    def __init__(self, llm: LLMService) -> None:
        self._llm = llm

    def analyze(self, request: SecurityRequest) -> SecurityResponse:
        """Validate input and run security analysis."""
        if not request.code.strip():
            return SecurityResponse(
                error=_validation_error("Code cannot be empty."),
            )
        if len(request.code) > _MAX_CODE_CHARS:
            return SecurityResponse(
                error=_validation_error(
                    f"Code too long (max {_MAX_CODE_CHARS} characters). "
                    "Please analyse smaller sections."
                ),
            )
        return self._llm.security_analysis(request)
