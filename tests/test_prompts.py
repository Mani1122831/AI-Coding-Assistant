"""
tests/test_prompts.py
Unit tests for prompt generation functions.
Validates that prompts are correctly structured and contain
the expected information. No API key required.
"""
import pytest
from models.schemas import (
    CodeGenerationRequest,
    ConvertRequest,
    DebugRequest,
    ExplainRequest,
    RefactorRequest,
    SecurityRequest,
    TestGenerationRequest,
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


class TestGeneratePrompt:
    def _make_request(self, **kwargs):
        defaults = {"language": "Python", "requirements": "Build a hello world script"}
        defaults.update(kwargs)
        return CodeGenerationRequest(**defaults)

    def test_contains_language(self):
        prompt = build_generate_prompt(self._make_request(language="Java"))
        assert "Java" in prompt

    def test_contains_requirements(self):
        req = "Build a FastAPI server"
        prompt = build_generate_prompt(self._make_request(requirements=req))
        assert req in prompt

    def test_contains_framework_when_provided(self):
        prompt = build_generate_prompt(self._make_request(framework="Django"))
        assert "Django" in prompt

    def test_no_framework_section_when_omitted(self):
        prompt = build_generate_prompt(self._make_request(framework=None))
        assert "Framework/library" not in prompt

    def test_contains_constraints_when_provided(self):
        prompt = build_generate_prompt(self._make_request(constraints="Use type hints"))
        assert "Use type hints" in prompt

    def test_contains_required_sections(self):
        prompt = build_generate_prompt(self._make_request())
        assert "Generated Code" in prompt
        assert "Explanation" in prompt
        assert "Dependencies" in prompt
        assert "How to Run" in prompt
        assert "Potential Improvements" in prompt

    def test_prompt_is_string(self):
        prompt = build_generate_prompt(self._make_request())
        assert isinstance(prompt, str)
        assert len(prompt) > 50


class TestExplainPrompt:
    def _make_request(self, **kwargs):
        defaults = {"code": "def hello():\n    print('hello')"}
        defaults.update(kwargs)
        return ExplainRequest(**defaults)

    def test_contains_code(self):
        code = "def foo(): pass"
        prompt = build_explain_prompt(self._make_request(code=code))
        assert code in prompt

    def test_contains_language_when_provided(self):
        prompt = build_explain_prompt(self._make_request(language="Python"))
        assert "Python" in prompt

    def test_required_sections_present(self):
        prompt = build_explain_prompt(self._make_request())
        sections = ["Summary", "Inputs", "Outputs", "Complexity", "Potential Problems", "Beginner"]
        for s in sections:
            assert s in prompt, f"Missing section: {s}"

    def test_no_language_clause_when_none(self):
        prompt = build_explain_prompt(self._make_request(language=None))
        assert "Language: None" not in prompt


class TestDebugPrompt:
    def _make_request(self, **kwargs):
        defaults = {"language": "Python", "code": "x = 1 / 0"}
        defaults.update(kwargs)
        return DebugRequest(**defaults)

    def test_contains_code(self):
        code = "print(undefined_var)"
        prompt = build_debug_prompt(self._make_request(code=code))
        assert code in prompt

    def test_contains_error_message_when_provided(self):
        err = "NameError: name 'undefined_var' is not defined"
        prompt = build_debug_prompt(self._make_request(error_message=err))
        assert err in prompt

    def test_no_error_section_when_omitted(self):
        prompt = build_debug_prompt(self._make_request(error_message=None))
        assert "Error Message" not in prompt

    def test_required_sections(self):
        prompt = build_debug_prompt(self._make_request())
        assert "Problem Explanation" in prompt
        assert "Root Cause" in prompt
        assert "Corrected Code" in prompt
        assert "Prevention Advice" in prompt


class TestRefactorPrompt:
    def _make_request(self, **kwargs):
        defaults = {"language": "Python", "code": "def f(x):\n    return x+1"}
        defaults.update(kwargs)
        return RefactorRequest(**defaults)

    def test_contains_code(self):
        code = "def bad_func(x,y,z):\n    pass"
        prompt = build_refactor_prompt(self._make_request(code=code))
        assert code in prompt

    def test_contains_focus_when_provided(self):
        prompt = build_refactor_prompt(self._make_request(focus="performance"))
        assert "performance" in prompt

    def test_required_sections(self):
        prompt = build_refactor_prompt(self._make_request())
        assert "Issues Found" in prompt
        assert "Refactored Code" in prompt
        assert "Explanation of Changes" in prompt


class TestConvertPrompt:
    def _make_request(self, **kwargs):
        defaults = {
            "source_language": "Python",
            "target_language": "Java",
            "code": "print('hello')",
        }
        defaults.update(kwargs)
        return ConvertRequest(**defaults)

    def test_contains_source_language(self):
        prompt = build_convert_prompt(self._make_request(source_language="Python"))
        assert "Python" in prompt

    def test_contains_target_language(self):
        prompt = build_convert_prompt(self._make_request(target_language="Java"))
        assert "Java" in prompt

    def test_contains_code(self):
        code = "print('convert me')"
        prompt = build_convert_prompt(self._make_request(code=code))
        assert code in prompt

    def test_required_sections(self):
        prompt = build_convert_prompt(self._make_request())
        assert "Converted Code" in prompt
        assert "Important Differences" in prompt
        assert "Dependencies" in prompt
        assert "Behavior Notes" in prompt


class TestTestsPrompt:
    def _make_request(self, **kwargs):
        defaults = {
            "language": "Python",
            "code": "def add(a, b): return a + b",
            "test_framework": "pytest",
        }
        defaults.update(kwargs)
        return TestGenerationRequest(**defaults)

    def test_contains_framework(self):
        prompt = build_tests_prompt(self._make_request(test_framework="pytest"))
        assert "pytest" in prompt

    def test_contains_code(self):
        code = "def multiply(a, b): return a * b"
        prompt = build_tests_prompt(self._make_request(code=code))
        assert code in prompt

    def test_required_sections(self):
        prompt = build_tests_prompt(self._make_request())
        assert "Test Code" in prompt
        assert "Test Cases Covered" in prompt
        assert "Edge Cases" in prompt
        assert "Missing Cases" in prompt


class TestSecurityPrompt:
    def _make_request(self, **kwargs):
        defaults = {"language": "Python", "code": "password = 'admin123'"}
        defaults.update(kwargs)
        return SecurityRequest(**defaults)

    def test_contains_code(self):
        code = "exec(user_input)"
        prompt = build_security_prompt(self._make_request(code=code))
        assert code in prompt

    def test_contains_severity_levels(self):
        prompt = build_security_prompt(self._make_request())
        for level in ["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"]:
            assert level in prompt

    def test_required_sections(self):
        prompt = build_security_prompt(self._make_request())
        assert "Findings" in prompt
        assert "Overall Risk" in prompt
        assert "Summary" in prompt
