"""
prompts/tests.py
Prompt template for the Test Generation feature.
"""
from models.schemas import TestGenerationRequest


def build_tests_prompt(request: TestGenerationRequest) -> str:
    """
    Build a structured prompt for unit test generation.

    Args:
        request: A TestGenerationRequest with code and target framework.

    Returns:
        A complete prompt string ready to send to the LLM.
    """
    return f"""You are a senior QA engineer. Generate comprehensive unit tests for the following {request.language} code using {request.test_framework}.

## Code to Test
```{request.language.lower()}
{request.code}
```

## Instructions
- Write tests that cover the normal happy path, edge cases, and error conditions.
- Use only real {request.test_framework} APIs and conventions.
- Each test should be independent and have a clear, descriptive name.
- Do NOT test implementation details — test behavior and outputs.
- Do NOT use real external services; mock them where needed.

## Response Format
Respond with EXACTLY these sections:

### Test Code
```{request.language.lower()}
[Complete test code using {request.test_framework}]
```

### Test Cases Covered
[List each test case, prefixed with "- "]

### Edge Cases
[List edge cases covered by the tests, prefixed with "- "]

### Missing Cases
[List important cases that are NOT covered due to missing context or complexity, prefixed with "- ". If none, write "- None"]
"""
