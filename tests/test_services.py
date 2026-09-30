"""
tests/test_services.py
Unit tests for service layer logic.
All AI calls are mocked — no real API key required.
"""
import pytest
from unittest.mock import MagicMock, patch, PropertyMock

from models.schemas import (
    AIError,
    ChatMessage,
    ChatRequest,
    CodeGenerationRequest,
    CodeGenerationResponse,
    ConvertRequest,
    DebugRequest,
    ExplainRequest,
    RefactorRequest,
    SecurityRequest,
    SecurityResponse,
    SeverityLevel,
    TestGenerationRequest,
)
from services.code_service import CodeService
from services.security_service import SecurityService


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def mock_llm():
    """Return a MagicMock that stands in for LLMService."""
    return MagicMock()


@pytest.fixture
def code_svc(mock_llm):
    return CodeService(llm=mock_llm)


@pytest.fixture
def security_svc(mock_llm):
    return SecurityService(llm=mock_llm)


# ── CodeService.generate ───────────────────────────────────────────────────────

class TestCodeServiceGenerate:
    def test_valid_request_calls_llm(self, code_svc, mock_llm):
        mock_llm.generate_code.return_value = CodeGenerationResponse(
            generated_code="print('hi')", explanation="A hello world script"
        )
        result = code_svc.generate(
            CodeGenerationRequest(language="Python", requirements="Hello world script")
        )
        mock_llm.generate_code.assert_called_once()
        assert result.generated_code == "print('hi')"

    def test_empty_requirements_returns_error(self, code_svc, mock_llm):
        result = code_svc.generate(
            CodeGenerationRequest(language="Python", requirements="   ")
        )
        assert result.error is not None
        assert result.error.code == "VALIDATION_ERROR"
        mock_llm.generate_code.assert_not_called()

    def test_empty_language_returns_error(self, code_svc, mock_llm):
        result = code_svc.generate(
            CodeGenerationRequest(language="   ", requirements="Build something")
        )
        assert result.error is not None
        assert result.error.code == "VALIDATION_ERROR"

    def test_too_long_requirements_returns_error(self, code_svc, mock_llm):
        long_req = "x" * 4000
        result = code_svc.generate(
            CodeGenerationRequest(language="Python", requirements=long_req)
        )
        assert result.error is not None
        assert result.error.code == "VALIDATION_ERROR"


# ── CodeService.explain ───────────────────────────────────────────────────────

class TestCodeServiceExplain:
    def test_valid_request_calls_llm(self, code_svc, mock_llm):
        from models.schemas import ExplainResponse
        mock_llm.explain_code.return_value = ExplainResponse(
            summary="A function", line_by_line="Line 1: ..."
        )
        result = code_svc.explain(ExplainRequest(code="def foo(): pass"))
        mock_llm.explain_code.assert_called_once()
        assert result.summary == "A function"

    def test_empty_code_returns_error(self, code_svc, mock_llm):
        result = code_svc.explain(ExplainRequest(code="   "))
        assert result.error is not None
        assert result.error.code == "VALIDATION_ERROR"
        mock_llm.explain_code.assert_not_called()

    def test_too_long_code_returns_error(self, code_svc, mock_llm):
        result = code_svc.explain(ExplainRequest(code="x" * 20000))
        assert result.error is not None
        assert result.error.code == "VALIDATION_ERROR"


# ── CodeService.debug ─────────────────────────────────────────────────────────

class TestCodeServiceDebug:
    def test_valid_request_calls_llm(self, code_svc, mock_llm):
        from models.schemas import DebugResponse
        mock_llm.debug_code.return_value = DebugResponse(
            problem_explanation="Bug here",
            root_cause="Off by one",
            corrected_code="x = 1",
            explanation_of_changes="Fixed index",
            prevention_advice="Use assertions",
        )
        result = code_svc.debug(DebugRequest(language="Python", code="x = 0"))
        mock_llm.debug_code.assert_called_once()
        assert result.root_cause == "Off by one"

    def test_empty_code_returns_error(self, code_svc, mock_llm):
        result = code_svc.debug(DebugRequest(language="Python", code=""))
        assert result.error is not None
        mock_llm.debug_code.assert_not_called()


# ── CodeService.refactor ──────────────────────────────────────────────────────

class TestCodeServiceRefactor:
    def test_valid_request_calls_llm(self, code_svc, mock_llm):
        from models.schemas import RefactorResponse
        mock_llm.refactor_code.return_value = RefactorResponse(
            refactored_code="def better(): pass",
            explanation_of_changes="Improved naming",
        )
        result = code_svc.refactor(RefactorRequest(language="Python", code="def x(): pass"))
        mock_llm.refactor_code.assert_called_once()

    def test_empty_code_returns_error(self, code_svc, mock_llm):
        result = code_svc.refactor(RefactorRequest(language="Python", code="  "))
        assert result.error is not None

    def test_same_language_passes(self, code_svc, mock_llm):
        from models.schemas import RefactorResponse
        mock_llm.refactor_code.return_value = RefactorResponse(
            refactored_code="pass", explanation_of_changes=""
        )
        code_svc.refactor(RefactorRequest(language="Python", code="def f(): pass"))
        mock_llm.refactor_code.assert_called_once()


# ── CodeService.convert ───────────────────────────────────────────────────────

class TestCodeServiceConvert:
    def test_valid_request_calls_llm(self, code_svc, mock_llm):
        from models.schemas import ConvertResponse
        mock_llm.convert_code.return_value = ConvertResponse(converted_code="System.out.println();")
        result = code_svc.convert(
            ConvertRequest(source_language="Python", target_language="Java", code="print('hi')")
        )
        mock_llm.convert_code.assert_called_once()

    def test_same_language_returns_error(self, code_svc, mock_llm):
        result = code_svc.convert(
            ConvertRequest(source_language="Python", target_language="Python", code="print('hi')")
        )
        assert result.error is not None
        assert result.error.code == "VALIDATION_ERROR"
        mock_llm.convert_code.assert_not_called()

    def test_empty_code_returns_error(self, code_svc, mock_llm):
        result = code_svc.convert(
            ConvertRequest(source_language="Python", target_language="Java", code="")
        )
        assert result.error is not None


# ── CodeService.generate_tests ────────────────────────────────────────────────

class TestCodeServiceGenerateTests:
    def test_valid_request_calls_llm(self, code_svc, mock_llm):
        from models.schemas import TestGenerationResponse
        mock_llm.generate_tests.return_value = TestGenerationResponse(
            test_code="def test_foo(): assert True"
        )
        result = code_svc.generate_tests(
            TestGenerationRequest(language="Python", code="def foo(): return True")
        )
        mock_llm.generate_tests.assert_called_once()

    def test_empty_code_returns_error(self, code_svc, mock_llm):
        result = code_svc.generate_tests(
            TestGenerationRequest(language="Python", code="")
        )
        assert result.error is not None


# ── SecurityService ───────────────────────────────────────────────────────────

class TestSecurityService:
    def test_valid_request_calls_llm(self, security_svc, mock_llm):
        mock_llm.security_analysis.return_value = SecurityResponse(
            summary="No critical issues"
        )
        result = security_svc.analyze(SecurityRequest(language="Python", code="x = 1"))
        mock_llm.security_analysis.assert_called_once()

    def test_empty_code_returns_error(self, security_svc, mock_llm):
        result = security_svc.analyze(SecurityRequest(language="Python", code="   "))
        assert result.error is not None
        assert result.error.code == "VALIDATION_ERROR"
        mock_llm.security_analysis.assert_not_called()

    def test_too_long_code_returns_error(self, security_svc, mock_llm):
        result = security_svc.analyze(SecurityRequest(language="Python", code="x" * 20000))
        assert result.error is not None


# ── LLMService._make_error (via monkey-patching) ──────────────────────────────

class TestLLMMakeError:
    def test_auth_error(self):
        from services.llm_service import LLMService
        err = LLMService._make_error(Exception("Invalid api_key provided"))
        assert err.code == "AUTH_ERROR"

    def test_rate_limit_error(self):
        from services.llm_service import LLMService
        err = LLMService._make_error(Exception("quota exceeded rate limit"))
        assert err.code == "RATE_LIMIT"

    def test_timeout_error(self):
        from services.llm_service import LLMService
        err = LLMService._make_error(Exception("Request timeout"))
        assert err.code == "TIMEOUT"

    def test_network_error(self):
        from services.llm_service import LLMService
        err = LLMService._make_error(Exception("connection refused network"))
        assert err.code == "NETWORK_ERROR"

    def test_generic_error(self):
        from services.llm_service import LLMService
        err = LLMService._make_error(Exception("something else went wrong"))
        assert err.code in ("AI_SERVICE_ERROR", "LLM_ERROR")


# ── FileService ───────────────────────────────────────────────────────────────

class TestFileService:
    def _make_mock_file(self, name: str, content: bytes):
        mock = MagicMock()
        mock.name = name
        mock.getvalue.return_value = content
        return mock

    def test_valid_python_file(self):
        from services.file_service import FileService
        svc = FileService()
        mock_file = self._make_mock_file("script.py", b"print('hello')")
        result = svc.read_uploaded_file(mock_file)
        assert result.success is True
        assert result.language == "Python"
        assert result.content == "print('hello')"

    def test_unsupported_extension(self):
        from services.file_service import FileService
        svc = FileService()
        mock_file = self._make_mock_file("readme.md", b"# Title")
        result = svc.read_uploaded_file(mock_file)
        assert result.success is False
        assert "Unsupported" in result.error

    def test_empty_file(self):
        from services.file_service import FileService
        svc = FileService()
        mock_file = self._make_mock_file("empty.py", b"")
        result = svc.read_uploaded_file(mock_file)
        assert result.success is False

    def test_oversized_file(self):
        from services.file_service import FileService
        from config.settings import settings
        svc = FileService()
        big_content = b"x" * (settings.max_file_size_bytes + 1)
        mock_file = self._make_mock_file("big.py", big_content)
        result = svc.read_uploaded_file(mock_file)
        assert result.success is False
        assert "too large" in result.error.lower()

    def test_none_file(self):
        from services.file_service import FileService
        svc = FileService()
        result = svc.read_uploaded_file(None)
        assert result.success is False

    def test_path_traversal_in_filename(self):
        from services.file_service import FileService
        svc = FileService()
        mock_file = self._make_mock_file("../../etc/passwd.py", b"x = 1")
        result = svc.read_uploaded_file(mock_file)
        # Should succeed (safe extension) but use sanitised filename
        assert result.success is True
        assert ".." not in result.filename
