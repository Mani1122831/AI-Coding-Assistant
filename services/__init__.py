"""
services/__init__.py
Services package for AI Coding Assistant.
"""
from services.activity_service import ActivityService, activity_service
from services.auth_service import AuthService, auth_service
from services.code_service import CodeService
from services.email_service import EmailService, email_service
from services.file_service import FileService
from services.history_service import HistoryService, history_service
from services.llm_service import LLMService, RECOMMENDED_MODELS
from services.mongo_service import DatabaseUnavailableError, MongoService, mongo_service
from services.security_service import SecurityService

__all__ = [
    "LLMService",
    "RECOMMENDED_MODELS",
    "CodeService",
    "FileService",
    "SecurityService",
    "MongoService",
    "mongo_service",
    "DatabaseUnavailableError",
    "AuthService",
    "auth_service",
    "EmailService",
    "email_service",
    "HistoryService",
    "history_service",
    "ActivityService",
    "activity_service",
]
