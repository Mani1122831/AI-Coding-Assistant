"""
prompts/generate.py
Prompt template for the Code Generation feature.
"""
from models.schemas import CodeGenerationRequest


def build_generate_prompt(request: CodeGenerationRequest) -> str:
    """
    Build a structured prompt for code generation.

    Args:
        request: A CodeGenerationRequest with all user inputs.

    Returns:
        A complete prompt string ready to send to the LLM.
    """
    framework_clause = (
        f"\nFramework/library to use: {request.framework}" if request.framework else ""
    )
    constraints_clause = (
        f"\nConstraints / style preferences: {request.constraints}"
        if request.constraints
        else ""
    )

    return f"""You are a senior software engineer. Generate production-quality {request.language} code based on the requirements below.

## Requirements
{request.requirements}{framework_clause}{constraints_clause}

## Instructions
- Write clean, readable, idiomatic {request.language} code.
- Include docstrings / comments where appropriate.
- Do NOT fabricate libraries or APIs that do not exist.
- Do NOT include executable instructions or system commands outside of code blocks.

## Response Format
Respond with EXACTLY these sections and no others:

### Generated Code
```{request.language.lower()}
[Your complete code here]
```

### Explanation
[Brief explanation of what the code does and key design decisions]

### Dependencies
[List each dependency on a separate line, prefixed with "- ". If none, write "None"]

### How to Run
[Step-by-step instructions to run the code]

### Potential Improvements
[List 2–5 concrete improvements that could be made in future iterations, prefixed with "- "]
"""
