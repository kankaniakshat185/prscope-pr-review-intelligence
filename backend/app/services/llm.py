import requests
import json
import re
import time
from typing import Dict, Any, List, Optional
from app.core.config import settings

# Retries per LLM call (both providers). Backoff is 5s, 10s, 20s between the
# 4 attempts (35s max per call) - generous on purpose, since a single
# analysis makes several calls back-to-back and a fresh free-tier key can
# otherwise get rate-limited well before the analysis actually finishes.
MAX_ATTEMPTS = 4
BACKOFF_BASE_SECONDS = 5

_RATE_LIMITED = object()  # sentinel: distinct from None (hard failure) and a real response


def _post_with_retry(url: str, headers: dict, data: dict, provider_label: str):
    """POST with retry-on-429 and retry-on-timeout. Returns the successful
    requests.Response, the _RATE_LIMITED sentinel if every attempt was
    rate-limited, or None on any other failure."""
    last_response: Optional[requests.Response] = None
    for attempt in range(MAX_ATTEMPTS):
        is_last_attempt = attempt == MAX_ATTEMPTS - 1
        try:
            response = requests.post(url, headers=headers, json=data, timeout=30)
        except requests.exceptions.Timeout:
            print(f"Timed out waiting for {provider_label} API (attempt {attempt + 1}/{MAX_ATTEMPTS})")
            if is_last_attempt:
                return None
            continue
        except requests.exceptions.RequestException as e:
            print(f"Error generating content ({provider_label}): {e}")
            return None

        if response.status_code == 200:
            return response

        if response.status_code == 429:
            last_response = response
            if is_last_attempt:
                print(f"Rate limit exceeded for {provider_label} API after {MAX_ATTEMPTS} attempts")
                return _RATE_LIMITED
            wait = BACKOFF_BASE_SECONDS * (2 ** attempt)
            print(f"Rate limit hit for {provider_label} (attempt {attempt + 1}/{MAX_ATTEMPTS}), backing off {wait}s...")
            time.sleep(wait)
            continue

        print(f"Error generating content ({provider_label}): {response.text}")
        return None

    return _RATE_LIMITED if last_response is not None else None


def generate_content(prompt: str, api_key: str = None, provider: str = "gemini") -> str:
    if provider == "openai":
        key_to_use = api_key or settings.OPENAI_API_KEY
        if not key_to_use:
            return ""
        url = "https://api.openai.com/v1/chat/completions"
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {key_to_use}'
        }
        data = {
            "model": "gpt-4o",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.1
        }
        response = _post_with_retry(url, headers, data, "OpenAI")
        if response is _RATE_LIMITED:
            return '{"error": "RATE_LIMIT_EXCEEDED"}'
        if response is None:
            return ""
        try:
            return response.json()['choices'][0]['message']['content']
        except Exception as e:
            print(f"Error parsing OpenAI response: {e}")
            return ""
    else:
        key_to_use = api_key or settings.GEMINI_API_KEY
        if not key_to_use:
            return ""
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={key_to_use}"
        headers = {'Content-Type': 'application/json'}
        data = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.1}
        }
        response = _post_with_retry(url, headers, data, "Gemini")
        if response is _RATE_LIMITED:
            return '{"error": "RATE_LIMIT_EXCEEDED"}'
        if response is None:
            return ""
        try:
            return response.json()['candidates'][0]['content']['parts'][0]['text']
        except Exception as e:
            print(f"Error parsing Gemini response: {e}")
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
"""

def generate_review_checklist(context: Dict[str, Any], api_key: str = None, provider: str = "gemini") -> List[str]:
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
    res = generate_content(prompt, api_key, provider)
    parsed = parse_json_response(res)
    if isinstance(parsed, list):
        return parsed[:5]
    return ["Verify code changes against requirements"]

def generate_review_comments(context: Dict[str, Any], api_key: str = None, provider: str = "gemini") -> List[Dict[str, Any]]:
    base_prompt = build_base_prompt(context)
    prompt = f"""{base_prompt}
Generate up to 3 high-impact specific review comments for this PR grounded in actual changes.

VALUE FILTER (CRITICAL):
REJECT style-only comments, formatting comments, minor naming comments, cosmetic suggestions, redundant annotation suggestions, and trivial refactors.
ALLOW potential bugs, edge cases, validation issues, concurrency concerns, testing gaps, error handling issues, performance risks, security concerns, architecture concerns, dependency concerns.

Rules:
Only generate a comment if:
1. It passes the VALUE FILTER.
2. There is evidence in the diff.
3. The comment references actual modified logic.

Never invent try-except recommendations, security vulnerabilities, or missing tests unless explicitly supported by modified code.
If confidence is low (< 80) or no issues exist, return an empty list [].

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
    res = generate_content(prompt, api_key, provider)
    parsed = parse_json_response(res)
    comments = []
    if isinstance(parsed, list):
        for c in parsed:
            if isinstance(c, dict) and c.get('confidence', 0) >= 80:
                comments.append(c)
                
        def severity_score(sev):
            if sev == "Critical": return 3
            if sev == "Warning": return 2
            return 1
            
        return sorted(comments, key=lambda x: (severity_score(x.get('severity')), x.get('confidence', 0)), reverse=True)[:3]
    return []

def explain_security_finding(finding: dict, api_key: str = None, provider: str = "gemini") -> dict:
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
    res = generate_content(prompt, api_key, provider)
    parsed = parse_json_response(res)
    if isinstance(parsed, dict):
        return {
            **finding,
            "ai_explanation": parsed.get("explanation"),
            "ai_recommendation": parsed.get("recommendation", finding.get("recommendation")),
            "ai_impact_summary": parsed.get("impact_summary")
        }
    return finding

def generate_executive_summary(context: Dict[str, Any], api_key: str = None, provider: str = "gemini") -> str:
    base_prompt = build_base_prompt(context)
    
    prompt = f"""{base_prompt}
Write a concise executive engineering summary for this PR for a Tech Lead or Senior Engineer.

REQUIREMENTS:
1. Maximum 120 words.
2. DO NOT INCLUDE: file lists, function lists, long explanations, code snippets, directory names.
3. Must use EXACTLY these four headings using standard markdown `###`: Purpose, Risk, Impact, Recommendation.

Format EXACTLY like this:
### Purpose
[1-2 sentences]

### Risk
[Medium/High/Low]. [1 sentence reason]

### Impact
[1 sentence]

### Recommendation
[1 sentence]
"""
    res = generate_content(prompt, api_key, provider)
    if res and "RATE_LIMIT_EXCEEDED" not in res:
        return res

    provider_label = "OpenAI" if provider == "openai" else "Gemini"

    if api_key:
        # This PR's analysis used a BYOK key, and THAT key got rate-limited -
        # not the shared pool. A single analysis makes several back-to-back
        # LLM calls (checklist, comments, summary, jira context, plus one
        # per security finding), which can burn through a fresh free-tier
        # key's per-minute quota within one run.
        return f"""### Your {provider_label} API Key Was Rate-Limited
Your personal {provider_label} API key (not the shared PRScope pool) hit its own rate limit. A single analysis makes several AI calls in quick succession, which can exceed a free-tier key's per-minute quota - especially on PRs with multiple security findings, each of which triggers its own explanation call.

### What to do
Wait a minute and retry, or check your usage/quota in your {provider_label} account dashboard.

> *Note: Deterministic security scanning, dependency intelligence, and architecture rule validations are unaffected by this limit and have executed successfully below.*"""

    return """### Global Rate Limit Exceeded
The global free-tier Gemini API pool is currently experiencing exceptionally high demand and has temporarily rate-limited inference requests.

### Instant Bypass (BYOK)
You can instantly bypass this global queue by providing your own free Google Gemini API Key. Click the **Settings (⚙️)** gear icon in the top right corner of the extension to securely add your key to local storage for unlimited inference.

### Automatic Refresh
Alternatively, you can wait a short moment for the global API quota pool to refresh and retry the analysis.

> *Note: Deterministic security scanning, dependency intelligence, and architecture rule validations are unaffected by this limit and have executed successfully below.*"""

def extract_jira_context(pr_data: Dict[str, Any], api_key: str = None, provider: str = "gemini") -> Dict[str, Any]:
    text = f"{pr_data.get('title', '')} {pr_data.get('description', '')}"
    jira_pattern = r'[A-Z]+-\d+'
    matches = re.findall(jira_pattern, text)
    
    if not matches:
        return None
        
    ticket_id = matches[0]
    
    prompt = f"Given Jira ticket {ticket_id} and PR title '{pr_data.get('title')}', generate Jira Alignment intelligence. Output JSON exactly with keys: 'Ticket', 'Confidence' (number 0-100), 'Coverage' (e.g. '3 / 4'), 'Missing Requirements' (string describing potential gaps)."
    res = generate_content(prompt, api_key, provider)
    parsed = parse_json_response(res)
    if isinstance(parsed, dict):
        return {
            "Ticket": ticket_id,
            "Confidence": parsed.get("Confidence", 80),
            "Coverage": parsed.get("Coverage", "N/A"),
            "Missing_Requirements": parsed.get("Missing Requirements", "None detected")
        }
        
    return {
        "Ticket": ticket_id,
        "Confidence": 80,
        "Coverage": "N/A",
        "Missing_Requirements": "None detected"
    }
