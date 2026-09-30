"""
models/schemas.py
Pydantic models for all request and response data structures,
including AI coding tasks, user authentication, coding history, and activity logs.
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, EmailStr, Field


# ── Enumerations ──────────────────────────────────────────────────────────────


class SeverityLevel(str, Enum):
    """Security finding severity levels."""
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFO = "INFO"


# ── Error Model ───────────────────────────────────────────────────────────────


class AIError(BaseModel):
    """Represents an error returned from the AI service layer."""
    code: str
    message: str
    details: Optional[str] = None


# ── Code Generation ───────────────────────────────────────────────────────────


class CodeGenerationRequest(BaseModel):
    """Input for the code generation feature."""
    language: str = Field(..., description="Target programming language")
    requirements: str = Field(..., description="Natural-language description of what to build")
    framework: Optional[str] = Field(None, description="Optional framework (e.g. FastAPI, React)")
    constraints: Optional[str] = Field(None, description="Optional constraints or style preferences")


class CodeGenerationResponse(BaseModel):
    """Structured output from the code generation feature."""
    generated_code: str
    explanation: str
    dependencies: List[str] = Field(default_factory=list)
    how_to_run: str = ""
    potential_improvements: List[str] = Field(default_factory=list)
    error: Optional[AIError] = None


# ── Debugging ────────────────────────────────────────────────────────────────


class DebugRequest(BaseModel):
    """Input for the debug feature."""
    language: str
    code: str
    error_message: Optional[str] = None
    expected_behavior: Optional[str] = None


class DebugResponse(BaseModel):
    """Structured output from the debug feature."""
    problem_explanation: str
    root_cause: str
    corrected_code: str
    explanation_of_changes: str
    prevention_advice: str
    error: Optional[AIError] = None


# ── Code Explanation ──────────────────────────────────────────────────────────


class ExplainRequest(BaseModel):
    """Input for the explain feature."""
    code: str
    language: Optional[str] = None


class ExplainResponse(BaseModel):
    """Structured output from the explain feature."""
    summary: str
    line_by_line: str
    important_concepts: List[str] = Field(default_factory=list)
    inputs: str = ""
    outputs: str = ""
    complexity: Optional[str] = None
    potential_problems: List[str] = Field(default_factory=list)
    beginner_explanation: str = ""
    error: Optional[AIError] = None


# ── Refactoring ──────────────────────────────────────────────────────────────


class RefactorIssue(BaseModel):
    """A single refactoring suggestion."""
    issue: str
    reason: str
    severity: str = "MEDIUM"  # LOW, MEDIUM, HIGH


# Keep backward-compatible alias
RefactorFinding = RefactorIssue


class RefactorRequest(BaseModel):
    """Input for the refactor feature."""
    language: str
    code: str
    focus: Optional[str] = None  # e.g. "performance", "readability"


class RefactorResponse(BaseModel):
    """Structured output from the refactor feature."""
    issues_found: List[RefactorIssue] = Field(default_factory=list)
    refactored_code: str
    explanation_of_changes: str
    error: Optional[AIError] = None


# ── Code Conversion ───────────────────────────────────────────────────────────


class ConvertRequest(BaseModel):
    """Input for the code conversion feature."""
    source_language: str
    target_language: str
    code: str


class ConvertResponse(BaseModel):
    """Structured output from the code conversion feature."""
    converted_code: str
    important_differences: List[str] = Field(default_factory=list)
    dependencies: List[str] = Field(default_factory=list)
    behavior_notes: str = ""
    error: Optional[AIError] = None


# ── Test Generation ───────────────────────────────────────────────────────────


class UnitTestGenerationRequest(BaseModel):
    """Input for the test generation feature."""
    language: str
    code: str
    test_framework: str = "pytest"  # pytest, unittest, jest


# Keep backward-compatible alias
TestGenerationRequest = UnitTestGenerationRequest


class TestGenerationResponse(BaseModel):
    """Structured output from the test generation feature."""
    test_code: str
    test_cases_covered: List[str] = Field(default_factory=list)
    edge_cases: List[str] = Field(default_factory=list)
    missing_cases: List[str] = Field(default_factory=list)
    error: Optional[AIError] = None


# ── Security Analysis ─────────────────────────────────────────────────────────


class SecurityFinding(BaseModel):
    """A single security issue found in code."""
    severity: SeverityLevel
    title: str
    description: str
    location: Optional[str] = None  # e.g., "line 42" or "function handle_upload"
    remediation: str


class SecurityRequest(BaseModel):
    """Input for the security analysis feature."""
    language: str
    code: str


class SecurityResponse(BaseModel):
    """Structured output from the security analysis feature."""
    findings: List[SecurityFinding] = Field(default_factory=list)
    overall_risk: SeverityLevel = SeverityLevel.INFO
    summary: str = ""
    disclaimer: str = (
        "This is an advisory analysis tool. It does not guarantee the absence of "
        "security vulnerabilities. Always conduct a thorough security review before "
        "deploying code to production."
    )
    error: Optional[AIError] = None


# ── Chat ──────────────────────────────────────────────────────────────────────


class ChatMessage(BaseModel):
    """A single message in the chat history."""
    role: str  # "user" or "assistant"
    content: str


class ChatRequest(BaseModel):
    """Input for the chat feature."""
    message: str
    history: List[ChatMessage] = Field(default_factory=list)
    context_code: Optional[str] = None
    context_language: Optional[str] = None


class ChatResponse(BaseModel):
    """Structured output from the chat feature."""
    reply: str
    error: Optional[AIError] = None


# ── Authentication & User Models ──────────────────────────────────────────────


class User(BaseModel):
    """Database representation of a user account."""
    id: str = Field(..., description="Unique user ID string representation of ObjectId")
    full_name: str
    username: str
    email: str
    created_at: str
    updated_at: str
    is_active: bool = True


class UserRegistration(BaseModel):
    """Payload for registering a new user."""
    full_name: str
    username: str
    email: str
    password: str
    confirm_password: str


class UserLogin(BaseModel):
    """Payload for user login."""
    email_or_username: str
    password: str


class UserProfileUpdate(BaseModel):
    """Payload for updating user profile info."""
    full_name: str
    username: str


class PasswordChange(BaseModel):
    """Payload for changing user password from profile."""
    current_password: str
    new_password: str
    confirm_new_password: str


class PasswordResetRequest(BaseModel):
    """Payload for requesting a password reset email."""
    email: str


class PasswordResetConfirm(BaseModel):
    """Payload for resetting password with a validated token."""
    token: str
    new_password: str
    confirm_new_password: str



# ── History & Activity Models ─────────────────────────────────────────────────


class HistoryRecord(BaseModel):
    """Database representation of a user's coding history item."""
    id: str
    user_id: str
    operation: str  # generate, debug, explain, refactor, convert, tests, security, chat, file_analyze
    language: str = "Unknown"
    input_summary: str = ""
    input_code: Optional[str] = None
    generated_code: Optional[str] = None
    explanation: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: str


class ActivityLog(BaseModel):
    """Database representation of an audit/activity log entry."""
    id: str
    user_id: str
    action: str
    timestamp: str
    details: Optional[Dict[str, Any]] = None
