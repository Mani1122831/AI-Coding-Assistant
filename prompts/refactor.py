"""
prompts/refactor.py
Prompt template for the Code Refactoring feature.
"""
from models.schemas import RefactorRequest


def build_refactor_prompt(request: RefactorRequest) -> str:
    """
    Build a structured prompt for code refactoring.

    Args:
        request: A RefactorRequest with code and optional focus.

    Returns:
        A complete prompt string ready to send to the LLM.
    """
    focus_clause = (
        f"\nFocus area: {request.focus}"
        if request.focus
        else ""
    )

    return f"""You are a senior software engineer specializing in code quality. Analyze and refactor the following {request.language} code.

## Code to Refactor
```{request.language.lower()}
{request.code}
```{focus_clause}

## Instructions
- Preserve the existing behavior — only improve the code quality.
- Look for: code duplication, poor naming, unnecessary complexity, maintainability issues, performance opportunities, and code smells.
- Classify each issue as LOW, MEDIUM, or HIGH severity.
- Do NOT introduce new dependencies unless absolutely necessary.
- Do NOT change the public API or function signatures unless there is a strong reason.

## Response Format
Respond with EXACTLY these sections:

### Issues Found
[List each issue in this exact format — repeat the block for each issue:]
**Issue**: [short title]
**Severity**: [LOW | MEDIUM | HIGH]
**Reason**: [why this is a problem]

### Refactored Code
```{request.language.lower()}
[Complete refactored code]
```

### Explanation of Changes
[Summarize what you changed and why, in plain language]
"""
