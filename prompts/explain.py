"""
prompts/explain.py
Prompt template for the Code Explanation feature.
"""
from models.schemas import ExplainRequest


def build_explain_prompt(request: ExplainRequest) -> str:
    """
    Build a structured prompt for code explanation.

    Args:
        request: An ExplainRequest containing the code and optional language.

    Returns:
        A complete prompt string ready to send to the LLM.
    """
    language_clause = (
        f"Language: {request.language}\n" if request.language else ""
    )

    return f"""You are an expert programming tutor. Explain the following code clearly and accurately.

{language_clause}## Code to Explain
```
{request.code}
```

## Instructions
- Base your explanation ONLY on what is actually present in the code.
- Do NOT assume or fabricate functionality that is not shown.
- Be factual and precise.

## Response Format
Respond with EXACTLY these sections:

### Summary
[One or two sentences describing what this code does overall]

### Line-by-Line Explanation
[Walk through the code block by block, explaining each significant part]

### Important Concepts
[List 2–5 key programming concepts demonstrated, prefixed with "- "]

### Inputs
[Describe the inputs or parameters. If none, write "None"]

### Outputs
[Describe what the code returns or produces. If none, write "None"]

### Complexity
[Time and space complexity if relevant. Otherwise write "N/A"]

### Potential Problems
[List any bugs, edge cases, or issues you can identify. Prefix with "- ". If none, write "- None identified"]

### Beginner Explanation
[Explain the code as if talking to a beginner who just learned to program]
"""
