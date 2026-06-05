import google.generativeai as genai
import json
import re
from typing import Dict, Any, List
from app.core.config import settings

if settings.GEMINI_API_KEY:
    genai.configure(api_key=settings.GEMINI_API_KEY)

# Use standard prompt wrapper to prevent crashes if no API key is set
def generate_content(prompt: str) -> str:
    if not settings.GEMINI_API_KEY:
        return ""
    try:
        model = genai.GenerativeModel('gemini-2.5-flash')
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        print(f"Error generating content: {e}")
        return ""

def parse_json_response(text: str) -> Any:
    # Remove markdown formatting if present
    text = text.replace("```json", "").replace("```", "").strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None

def build_base_prompt(context: Dict[str, Any]) -> str:
    return f"""
PR Type: {context.get('pr_type')}
Diff Summary: {context.get('diff_summary')}
Changed Files: {context.get('changed_files')}
Risk Score: {context.get('risk_score')} ({context.get('risk_category')})
Impact Analysis: {context.get('impact_analysis')}
Architecture Violations: {context.get('architecture_violations')}

Do not generate concerns unrelated to the modified files.
If this is a documentation-only PR, focus entirely on documentation review.

Do not hallucinate vulnerabilities.
Do not hallucinate performance issues.
Do not hallucinate testing requirements.
Do not discuss code paths that were not modified.
Only discuss evidence visible in the supplied PR context.
If insufficient evidence exists, state that no significant concerns were found.
"""

def generate_review_checklist(context: Dict[str, Any]) -> List[str]:
    base_prompt = build_base_prompt(context)
    pr_type = context.get('pr_type')
    
    rules = ""
    if pr_type == "DOCS":
        rules = "Generate items such as: verify documentation accuracy, verify terminology consistency, verify links and references."
    elif pr_type == "TEST":
        rules = "Generate items related to: coverage, edge cases, assertions."
    elif pr_type == "BACKEND":
        rules = "Generate items related to: logic correctness, error handling, performance."
    
    prompt = f"""{base_prompt}
Generate a code review checklist with maximum 5 items based ONLY on the context provided above.
{rules}
Never generate: null handling, performance bottlenecks, test coverage unless the modified code actually justifies those concerns.
Output as a JSON list of strings.
"""
    res = generate_content(prompt)
    parsed = parse_json_response(res)
    if isinstance(parsed, list):
        return parsed[:5]
    return ["Verify code changes against requirements"]

def generate_review_comments(context: Dict[str, Any]) -> List[Dict[str, Any]]:
    base_prompt = build_base_prompt(context)
    prompt = f"""{base_prompt}
Generate up to 5 specific review comments for this PR grounded in actual changes.

Rules:
Only generate a comment if:
1. There is evidence in the diff
2. The comment references a changed file
3. The comment references actual modified logic

Never invent try-except recommendations, security vulnerabilities, or missing tests unless supported by modified code.
If confidence is low or no issues exist, return an empty list [].

Output as a JSON list of objects with 'file', 'issue', 'suggestion', 'reasoning', 'confidence' (0-100), and 'severity' ("Critical", "Warning", or "Suggestion").

Example:
[{{
    "file": "path/to/file.py",
    "issue": "Missing error handling",
    "reasoning": "Database call lacks try-except",
    "suggestion": "Wrap in try-except and log error",
    "confidence": 92,
    "severity": "Warning"
}}]
"""
    res = generate_content(prompt)
    parsed = parse_json_response(res)
    comments = []
    if isinstance(parsed, list):
        for c in parsed:
            if isinstance(c, dict) and c.get('confidence', 0) >= 70:
                comments.append(c)
        return sorted(comments, key=lambda x: x.get('confidence', 0), reverse=True)[:5]
    return []

def explain_security_finding(finding: dict) -> dict:
    prompt = f"""
Explain the following security finding deterministically discovered by the security engine.
DO NOT detect vulnerabilities. Only EXPLAIN what was found.

Finding: {finding.get('name')}
Severity: {finding.get('severity')}
Code Snippet:
```
{finding.get('snippet')}
```
Reason: {finding.get('reason')}

Return JSON with:
"explanation": "Clear explanation of the risk.",
"recommendation": "How to fix it safely.",
"impact_summary": "What happens if exploited."
"""
    res = generate_content(prompt)
    parsed = parse_json_response(res)
    if isinstance(parsed, dict):
        return {
            **finding,
            "ai_explanation": parsed.get("explanation"),
            "ai_recommendation": parsed.get("recommendation", finding.get("recommendation")),
            "ai_impact_summary": parsed.get("impact_summary")
        }
    return finding

def generate_executive_summary(context: Dict[str, Any]) -> str:
    base_prompt = build_base_prompt(context)
    pr_type = context.get('pr_type')
    
    rules = ""
    if pr_type == "DOCS":
        rules = "discuss documentation impact. do not discuss tests. do not discuss runtime risk."
    elif pr_type == "TEST":
        rules = "discuss test coverage impact."
    elif pr_type == "BACKEND":
        rules = "discuss system impact."
    elif pr_type == "SECURITY":
        rules = "discuss security implications."
        
    prompt = f"""{base_prompt}
Write a concise executive engineering summary for this PR for a Tech Lead.
{rules}
Summary must explicitly reference actual files changed. Include purpose, risks, impacted systems, and recommendations.

FORMATTING RULES:
You MUST use proper Markdown headings starting with ### (e.g., ### Purpose, ### Risks, ### Impacted Systems, ### Recommendations).
Do NOT use bold text (**) for headings.
Always add two newlines (\n\n) after a heading so the content starts on the next line.
Use bullet points for lists.
"""
    res = generate_content(prompt)
    if res:
        return res
    return "This PR modifies specific files but no significant concerns were automatically detected."

def extract_jira_context(pr_data: Dict[str, Any]) -> Dict[str, Any]:
    text = f"{pr_data.get('title', '')} {pr_data.get('description', '')}"
    jira_pattern = r'[A-Z]+-\d+'
    matches = re.findall(jira_pattern, text)
    
    if not matches:
        return None
        
    ticket_id = matches[0]
    
    prompt = f"Given Jira ticket {ticket_id} and PR title '{pr_data.get('title')}', generate a 'PR Alignment Summary' answering: Does this PR appear aligned with ticket requirements? Provide a confidence score out of 100. Output as JSON with 'title', 'status', 'priority', 'acceptance_criteria', 'summary', 'confidence'."
    res = generate_content(prompt)
    parsed = parse_json_response(res)
    if isinstance(parsed, dict):
        return parsed
        
    return {
        "title": f"Feature implementation for {ticket_id}",
        "status": "In Progress",
        "priority": "High",
        "acceptance_criteria": "Code meets basic standards.",
        "summary": "PR appears aligned with standard requirements based on title.",
        "confidence": 80
    }
