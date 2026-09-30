"""
services/file_service.py

Handles uploaded source-code file processing.
Validates size and file type, reads content safely.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from config.settings import settings
from utils.helpers import (
    detect_language_from_extension,
    format_file_size,
    is_supported_extension,
    safe_filename,
)
from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class FileReadResult:
    """Result of reading an uploaded file."""
    success: bool
    content: str = ""
    language: Optional[str] = None
    filename: str = ""
    file_size: int = 0
    error: Optional[str] = None


class FileService:
    """
    Safely processes uploaded source-code files.

    Security principles:
    - File type is validated by extension (whitelist).
    - File size is enforced.
    - Content is read as text only (no execution).
    - Filename is sanitised to prevent path traversal.
    - .env and secrets are never readable through this service.
    """

    def read_uploaded_file(self, uploaded_file) -> FileReadResult:
        """
        Process a Streamlit UploadedFile object.

        Args:
            uploaded_file: A streamlit.runtime.uploaded_file_manager.UploadedFile.

        Returns:
            A FileReadResult with either content or an error message.
        """
        if uploaded_file is None:
            return FileReadResult(success=False, error="No file provided.")

        # Sanitise filename
        raw_name = getattr(uploaded_file, "name", "unknown")
        filename = safe_filename(raw_name)

        # Validate extension
        if not is_supported_extension(filename):
            suffix = Path(filename).suffix or "(no extension)"
            return FileReadResult(
                success=False,
                filename=filename,
                error=(
                    f"Unsupported file type: {suffix}. "
                    "Supported types: .py, .js, .ts, .java, .cpp, .c, .html, .css, .json, .sql"
                ),
            )

        # Check file size
        file_bytes = uploaded_file.getvalue()
        size = len(file_bytes)
        if size > settings.max_file_size_bytes:
            return FileReadResult(
                success=False,
                filename=filename,
                file_size=size,
                error=(
                    f"File too large ({format_file_size(size)}). "
                    f"Maximum allowed size: {settings.max_file_size_mb} MB."
                ),
            )

        if size == 0:
            return FileReadResult(
                success=False,
                filename=filename,
                error="The uploaded file is empty.",
            )

        # Decode content safely
        try:
            content = file_bytes.decode("utf-8")
        except UnicodeDecodeError:
            try:
                content = file_bytes.decode("latin-1")
            except Exception:
                return FileReadResult(
                    success=False,
                    filename=filename,
                    error="Could not decode file. Please ensure it is a plain text source file.",
                )

        language = detect_language_from_extension(filename)
        logger.info(
            "File uploaded: %s (%s, %s)",
            filename,
            language or "unknown",
            format_file_size(size),
        )

        return FileReadResult(
            success=True,
            content=content,
            language=language,
            filename=filename,
            file_size=size,
        )
