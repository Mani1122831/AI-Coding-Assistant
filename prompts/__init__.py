"""
prompts/__init__.py
Prompts package for AI Coding Assistant.
"""
from prompts.generate import build_generate_prompt
from prompts.explain import build_explain_prompt
from prompts.debug import build_debug_prompt
from prompts.refactor import build_refactor_prompt
from prompts.convert import build_convert_prompt
from prompts.tests import build_tests_prompt
from prompts.security import build_security_prompt

__all__ = [
    "build_generate_prompt",
    "build_explain_prompt",
    "build_debug_prompt",
    "build_refactor_prompt",
    "build_convert_prompt",
    "build_tests_prompt",
    "build_security_prompt",
]
