"""
prompts/debug.py
Prompt template for the Debugging feature.
"""
from models.schemas import DebugRequest


def build_debug_prompt(request: DebugRequest) -> str:
    """
    Build a structured prompt for code debugging.

    Args:
        request: A DebugRequest with code, error, and context.

    Returns:
        A complete prompt string ready to send to the LLM.
    """
    error_clause = (
        f"\n## Error Message\n```\n{request.error_message}\n```"
        if request.error_message
        else ""
    )
    expected_clause = (
        f"\n## Expected Behavior\n{request.expected_behavior}"
        if request.expected_behavior
        else ""
    )

    return f"""You are a senior software engineer and debugging expert. Analyze the following {request.language} code and identify the issue.

## Code
```{request.language.lower()}
{request.code}
```{error_clause}{expected_clause}

## Instructions
- Only report issues that you can confirm from the code provided.
- Clearly distinguish between CONFIRMED issues and POSSIBLE issues.
- Do NOT fabricate error causes without evidence in the code.
- Provide the corrected code as a complete, working replacement.

## Response Format
Respond with EXACTLY these sections:

### Problem Explanation
[What is going wrong and why]

### Root Cause
[The specific root cause of the bug — be precise and factual]

### Corrected Code
```{request.language.lower()}
[Full corrected code here]
```

### Explanation of Changes
[Describe each change you made and why it fixes the problem]

### Prevention Advice
[How to avoid this type of bug in the future]
"""
