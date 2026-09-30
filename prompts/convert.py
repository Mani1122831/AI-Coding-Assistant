"""
prompts/convert.py
Prompt template for the Code Conversion feature.
"""
from models.schemas import ConvertRequest


def build_convert_prompt(request: ConvertRequest) -> str:
    """
    Build a structured prompt for code conversion between languages.

    Args:
        request: A ConvertRequest with source/target languages and code.

    Returns:
        A complete prompt string ready to send to the LLM.
    """
    return f"""You are an expert polyglot programmer. Convert the following {request.source_language} code to idiomatic {request.target_language}.

## Source Code ({request.source_language})
```{request.source_language.lower()}
{request.code}
```

## Instructions
- Produce idiomatic {request.target_language} — use the natural patterns and conventions of that language.
- Preserve the original functionality exactly.
- Use only real, well-known libraries for {request.target_language}.
- If a direct equivalent does not exist, explain the difference clearly in the notes.
- Do NOT fabricate libraries or APIs.

## Response Format
Respond with EXACTLY these sections:

### Converted Code ({request.target_language})
```{request.target_language.lower()}
[Complete converted code]
```

### Important Differences
[List key language/paradigm differences, prefixed with "- "]

### Dependencies
[List libraries/packages needed in {request.target_language}, prefixed with "- ". If none, write "- None"]

### Behavior Notes
[Any behavioral differences or caveats the developer should be aware of]
"""
