"""
utils/helpers.py
General utility functions used across the application.
"""
import re
from pathlib import Path
from typing import Optional


# ── Supported file extensions for upload ─────────────────────────────────────

SUPPORTED_EXTENSIONS: dict[str, str] = {
    ".py": "Python",
    ".js": "JavaScript",
    ".ts": "TypeScript",
    ".java": "Java",
    ".cpp": "C++",
    ".c": "C",
    ".html": "HTML",
    ".css": "CSS",
    ".json": "JSON",
    ".sql": "SQL",
}


def detect_language_from_extension(filename: str) -> Optional[str]:
    """
    Return the programming language name for a given filename.
    Returns None if the extension is not supported.

    Examples:
        >>> detect_language_from_extension("main.py")
        'Python'
        >>> detect_language_from_extension("style.css")
        'CSS'
        >>> detect_language_from_extension("readme.md")
        None
    """
    suffix = Path(filename).suffix.lower()
    return SUPPORTED_EXTENSIONS.get(suffix)


def is_supported_extension(filename: str) -> bool:
    """Return True if the file extension is in the supported list."""
    suffix = Path(filename).suffix.lower()
    return suffix in SUPPORTED_EXTENSIONS


def truncate_text(text: str, max_chars: int = 12_000) -> str:
    """
    Truncate text to max_chars characters, appending a notice if truncated.
    Used to keep prompts within model context limits.

    Args:
        text: The text to possibly truncate.
        max_chars: Maximum character count allowed.

    Returns:
        Original text if within limit, or truncated version with notice.
    """
    if len(text) <= max_chars:
        return text
    notice = f"\n\n[... truncated — showing first {max_chars} characters ...]"
    return text[:max_chars] + notice


def clean_code_fence(text: str) -> str:
    """
    Remove markdown code fences from a string.
    Useful for extracting code returned inside ```...``` blocks.

    Examples:
        >>> clean_code_fence("```python\\nprint('hi')\\n```")
        "print('hi')"
        >>> clean_code_fence("print('hi')")
        "print('hi')"
    """
    # Remove opening fence (with optional language identifier)
    text = re.sub(r"^```[a-zA-Z0-9_+-]*\n?", "", text.strip())
    # Remove closing fence
    text = re.sub(r"\n?```$", "", text.strip())
    return text.strip()


def safe_filename(filename: str) -> str:
    """
    Sanitise a filename by removing path traversal characters.
    Only the base name is returned.

    Examples:
        >>> safe_filename("../../etc/passwd")
        'passwd'
        >>> safe_filename("my_script.py")
        'my_script.py'
    """
    return Path(filename).name


def format_file_size(size_bytes: int) -> str:
    """
    Format a byte count as a human-readable string.

    Examples:
        >>> format_file_size(1024)
        '1.0 KB'
        >>> format_file_size(2097152)
        '2.0 MB'
    """
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 ** 2:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes / 1024 ** 2:.1f} MB"


def extract_section(text: str, heading: str) -> str:
    """
    Extract text under a specific markdown heading from an AI response.
    Returns empty string if not found.

    Args:
        text: Full AI response text.
        heading: Heading to look for (case-insensitive, without ##).
    """
    pattern = re.compile(
        rf"#+\s*{re.escape(heading)}\s*\n(.*?)(?=\n#+\s|\Z)",
        re.DOTALL | re.IGNORECASE,
    )
    match = pattern.search(text)
    return match.group(1).strip() if match else ""


def build_language_list() -> list[str]:
    """Return a sorted list of programming languages for UI dropdowns."""
    return [
        "Python",
        "JavaScript",
        "TypeScript",
        "Java",
        "C++",
        "C",
        "C#",
        "Go",
        "Rust",
        "Ruby",
        "PHP",
        "Swift",
        "Kotlin",
        "R",
        "SQL",
        "Bash/Shell",
        "HTML/CSS",
    ]
