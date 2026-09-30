"""
utils/__init__.py
Utilities package for AI Coding Assistant.
"""
from utils.logger import get_logger
from utils.helpers import (
    truncate_text,
    clean_code_fence,
    detect_language_from_extension,
    safe_filename,
    format_file_size,
)

__all__ = [
    "get_logger",
    "truncate_text",
    "clean_code_fence",
    "detect_language_from_extension",
    "safe_filename",
    "format_file_size",
]
