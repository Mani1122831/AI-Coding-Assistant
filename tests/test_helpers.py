"""
tests/test_helpers.py
Unit tests for utility helper functions.
No API key required.
"""
import pytest
from utils.helpers import (
    build_language_list,
    clean_code_fence,
    detect_language_from_extension,
    extract_section,
    format_file_size,
    is_supported_extension,
    safe_filename,
    truncate_text,
)


# ── detect_language_from_extension ────────────────────────────────────────────

class TestDetectLanguage:
    def test_python(self):
        assert detect_language_from_extension("main.py") == "Python"

    def test_javascript(self):
        assert detect_language_from_extension("app.js") == "JavaScript"

    def test_typescript(self):
        assert detect_language_from_extension("index.ts") == "TypeScript"

    def test_java(self):
        assert detect_language_from_extension("Main.java") == "Java"

    def test_cpp(self):
        assert detect_language_from_extension("main.cpp") == "C++"

    def test_c(self):
        assert detect_language_from_extension("main.c") == "C"

    def test_html(self):
        assert detect_language_from_extension("index.html") == "HTML"

    def test_css(self):
        assert detect_language_from_extension("style.css") == "CSS"

    def test_json(self):
        assert detect_language_from_extension("config.json") == "JSON"

    def test_sql(self):
        assert detect_language_from_extension("query.sql") == "SQL"

    def test_unsupported(self):
        assert detect_language_from_extension("readme.md") is None

    def test_no_extension(self):
        assert detect_language_from_extension("Makefile") is None

    def test_uppercase_extension(self):
        # Extensions should be case-insensitive
        assert detect_language_from_extension("Main.PY") == "Python"


# ── is_supported_extension ────────────────────────────────────────────────────

class TestIsSupportedExtension:
    def test_supported(self):
        assert is_supported_extension("script.py") is True

    def test_unsupported(self):
        assert is_supported_extension("README.md") is False

    def test_env_file_not_supported(self):
        assert is_supported_extension(".env") is False


# ── truncate_text ─────────────────────────────────────────────────────────────

class TestTruncateText:
    def test_no_truncation_needed(self):
        text = "hello world"
        assert truncate_text(text, max_chars=100) == text

    def test_truncation_applied(self):
        text = "a" * 200
        result = truncate_text(text, max_chars=100)
        assert len(result) > 100  # includes the notice
        assert "truncated" in result
        assert result.startswith("a" * 100)

    def test_exact_limit(self):
        text = "a" * 100
        assert truncate_text(text, max_chars=100) == text

    def test_empty_string(self):
        assert truncate_text("", max_chars=100) == ""


# ── clean_code_fence ──────────────────────────────────────────────────────────

class TestCleanCodeFence:
    def test_removes_python_fence(self):
        code = "```python\nprint('hello')\n```"
        assert clean_code_fence(code) == "print('hello')"

    def test_removes_generic_fence(self):
        code = "```\nhello\n```"
        assert clean_code_fence(code) == "hello"

    def test_no_fence_unchanged(self):
        code = "print('hello')"
        assert clean_code_fence(code) == code

    def test_removes_javascript_fence(self):
        code = "```javascript\nconsole.log('hi');\n```"
        assert clean_code_fence(code) == "console.log('hi');"


# ── safe_filename ─────────────────────────────────────────────────────────────

class TestSafeFilename:
    def test_normal_filename(self):
        assert safe_filename("main.py") == "main.py"

    def test_path_traversal(self):
        assert safe_filename("../../etc/passwd") == "passwd"

    def test_absolute_path(self):
        assert safe_filename("/home/user/script.py") == "script.py"

    def test_windows_path(self):
        assert safe_filename("C:\\Users\\test\\app.py") == "app.py"


# ── format_file_size ──────────────────────────────────────────────────────────

class TestFormatFileSize:
    def test_bytes(self):
        assert format_file_size(512) == "512 B"

    def test_kilobytes(self):
        assert format_file_size(1024) == "1.0 KB"

    def test_megabytes(self):
        assert format_file_size(2 * 1024 * 1024) == "2.0 MB"

    def test_zero(self):
        assert format_file_size(0) == "0 B"


# ── extract_section ───────────────────────────────────────────────────────────

class TestExtractSection:
    SAMPLE = """
## Summary
This is the summary.

## Details
These are the details.
They span multiple lines.

## Conclusion
Final thoughts.
"""

    def test_extract_summary(self):
        result = extract_section(self.SAMPLE, "Summary")
        assert "This is the summary." in result

    def test_extract_details(self):
        result = extract_section(self.SAMPLE, "Details")
        assert "These are the details." in result
        assert "span multiple lines" in result

    def test_missing_section(self):
        result = extract_section(self.SAMPLE, "Missing Section")
        assert result == ""

    def test_case_insensitive(self):
        result = extract_section(self.SAMPLE, "summary")
        assert "This is the summary." in result


# ── build_language_list ───────────────────────────────────────────────────────

class TestBuildLanguageList:
    def test_returns_list(self):
        langs = build_language_list()
        assert isinstance(langs, list)
        assert len(langs) > 0

    def test_contains_python(self):
        assert "Python" in build_language_list()

    def test_contains_javascript(self):
        assert "JavaScript" in build_language_list()
