"""
prompts/security.py
Prompt template for the Security Analysis feature.
"""
from models.schemas import SecurityRequest


def build_security_prompt(request: SecurityRequest) -> str:
    """
    Build a structured prompt for security analysis.

    Args:
        request: A SecurityRequest with code and language.

    Returns:
        A complete prompt string ready to send to the LLM.
    """
    return f"""You are a senior application security engineer. Perform a thorough security analysis of the following {request.language} code.

## Code to Analyze
```{request.language.lower()}
{request.code}
```

## What to Check
Look specifically for:
- Hardcoded secrets, passwords, API keys, or tokens
- SQL injection vulnerabilities
- Command injection / OS command injection
- Unsafe use of eval() or exec()
- Path traversal vulnerabilities
- Insecure deserialization
- Unsafe input handling / missing input validation
- Weak authentication or authorization patterns
- Insecure API key handling
- Dangerous subprocess usage
- Missing error handling that could leak sensitive information
- Insecure direct object references
- Broken access control patterns

## Severity Levels
Use these exact labels:
- CRITICAL: Immediate exploitation risk, data breach likely
- HIGH: Serious vulnerability, should be fixed before deployment
- MEDIUM: Moderate risk, fix in next sprint
- LOW: Minor issue, good practice to fix
- INFO: Observation or best practice recommendation

## Instructions
- Only report issues you can confirm from the code provided.
- Do NOT fabricate vulnerabilities.
- Provide actionable remediation for each finding.
- Be specific about location (function name, line context) when possible.

## Response Format
Respond with EXACTLY these sections:

### Findings
[For EACH finding, use this exact format:]
**[SEVERITY]** — [Title]
**Location**: [function/line context or "General"]
**Description**: [What the vulnerability is and why it is dangerous]
**Remediation**: [How to fix it]

---

[If no findings, write: "No security issues identified in the provided code."]

### Overall Risk
[One of: CRITICAL | HIGH | MEDIUM | LOW | INFO]

### Summary
[2–3 sentences summarizing the overall security posture of this code]
"""
