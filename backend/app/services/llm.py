import requests
import json
import re
import time
from typing import Dict, Any, List, Optional
from app.core.config import settings

# Retries per LLM call (both providers). Backoff is 5s, 10s, 20s between the
# 4 attempts (35s max per call) - generous on purpose, since a fresh
# free-tier key can otherwise get rate-limited on a single burst of traffic.
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
    elif provider == "groq":
        # Groq's API is OpenAI-compatible (same request/response shape),
        # just a different host, key, and model - included as a genuinely
        # free, generously-rate-limited option for the shared pool and for
        # BYOK, unlike Gemini's free tier under real traffic or HuggingFace's
        # increasingly paid-by-default Inference Providers.
        key_to_use = api_key or settings.GROQ_API_KEY
        if not key_to_use:
            return ""
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {key_to_use}'
        }
        data = {
            "model": "llama-3.3-70b-versatile",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.1
        }
        response = _post_with_retry(url, headers, data, "Groq")
        if response is _RATE_LIMITED:
            return '{"error": "RATE_LIMIT_EXCEEDED"}'
        if response is None:
            return ""
        try:
            return response.json()['choices'][0]['message']['content']
        except Exception as e:
            print(f"Error parsing Groq response: {e}")
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


_PROVIDER_LABELS = {"openai": "OpenAI", "groq": "Groq", "gemini": "Gemini"}


def _rate_limit_fallback_summary(provider: str, api_key: Optional[str]) -> str:
    """The executive-summary-shaped message shown when the LLM call behind
    the review bundle fails outright (empty response or exhausted retries) -
    same messaging generate_executive_summary used to build inline, now
    shared since generate_review_bundle needs the identical fallback."""
    provider_label = _PROVIDER_LABELS.get(provider, "Gemini")

    if api_key:
        # This PR's analysis used a BYOK key, and THAT key got rate-limited -
        # not the shared pool. A single analysis makes several back-to-back
        # LLM calls, which can burn through a fresh free-tier key's
        # per-minute quota within one run.
        return f"""### Your {provider_label} API Key Was Rate-Limited
Your personal {provider_label} API key (not the shared PRScope pool) hit its own rate limit. Wait a minute and retry, or check your usage/quota in your {provider_label} account dashboard.

> *Note: Deterministic security scanning, dependency intelligence, and architecture rule validations are unaffected by this limit and have executed successfully below.*"""

    return f"""### Global Rate Limit Exceeded
The global free-tier {provider_label} API pool is currently experiencing exceptionally high demand and has temporarily rate-limited inference requests.

### Instant Bypass (BYOK)
You can instantly bypass this global queue by providing your own free {provider_label} API key (Groq's free tier is a good option if you don't already have one). Click the **Settings (⚙️)** gear icon in the top right corner of the extension to securely add your key to local storage for unlimited inference.

### Automatic Refresh
Alternatively, you can wait a short moment for the global API quota pool to refresh and retry the analysis.

> *Note: Deterministic security scanning, dependency intelligence, and architecture rule validations are unaffected by this limit and have executed successfully below.*"""


def _parse_error_fallback_summary() -> str:
    """Distinct from the rate-limit message: the LLM answered (not rate
    limited), but its response wasn't valid JSON, so none of the bundle's
    fields could be trusted - an honest, different failure mode from a 429,
    and worth saying so rather than reusing the rate-limit wording."""
    return """### AI Response Could Not Be Parsed
The AI provider returned a response, but it wasn't in the expected format, so a summary couldn't be generated this time. Retrying the analysis usually resolves this.

> *Note: Deterministic security scanning, dependency intelligence, and architecture rule validations are unaffected by this and have executed successfully below.*"""


def generate_executive_summary(context: Dict[str, Any], api_key: str = None, provider: str = "gemini") -> str:
    """Standalone single-purpose summary generation - kept separate from
    generate_review_bundle (which also produces a summary, folded into its
    combined call) because this makes its own independent LLM call and is
    useful on its own, e.g. for testing the rate-limit fallback messaging
    in isolation."""
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
    return _rate_limit_fallback_summary(provider, api_key)


def _checklist_rules_for(pr_type: Optional[str]) -> str:
    if pr_type == "DOCS":
        return "Generate items such as: verify documentation accuracy, verify terminology consistency, verify links and references."
    if pr_type == "TEST":
        return "Generate items related to: coverage, edge cases, assertions."
    if pr_type == "BACKEND":
        return "Generate items related to: logic correctness, error handling, performance."
    return ""


def generate_review_bundle(context: Dict[str, Any], pr_data: Dict[str, Any], api_key: str = None, provider: str = "gemini") -> Dict[str, Any]:
    """
    Review checklist, suggested comments, executive summary, and Jira
    context, all from a SINGLE LLM call instead of four separate ones. This
    is the main quota-reduction lever: a PR with several security findings
    used to make up to ~14 back-to-back LLM calls per analysis (this bundle
    plus one per finding - see explain_security_findings_batch for that
    side), which is exactly what exhausts a shared free-tier key's
    per-minute or per-day quota under any real traffic. Down to at most 2
    calls total now.

    Returns a dict with keys: review_checklist, suggested_comments,
    executive_summary, jira_context - the same shapes the four separate
    functions used to return, so callers don't need to change.
    """
    base_prompt = build_base_prompt(context)
    pr_type = context.get('pr_type')
    checklist_rules = _checklist_rules_for(pr_type)

    jira_pattern = r'[A-Z]+-\d+'
    text = f"{pr_data.get('title', '')} {pr_data.get('description', '')}"
    jira_matches = re.findall(jira_pattern, text)
    ticket_id = jira_matches[0] if jira_matches else None

    if ticket_id:
        jira_task = (
            f'Given Jira ticket {ticket_id} and PR title \'{pr_data.get("title")}\', generate Jira Alignment '
            'intelligence as a JSON object with keys: "Confidence" (number 0-100), "Coverage" (e.g. "3 / 4"), '
            '"Missing Requirements" (string describing potential gaps).'
        )
    else:
        jira_task = 'No Jira ticket ID (pattern like "ABC-123") was found in the PR title or description. Set "jira_context" to null.'

    prompt = f"""{base_prompt}
You are performing four separate analysis tasks on this same pull request. Return a SINGLE JSON object with exactly these four top-level keys: "review_checklist", "suggested_comments", "executive_summary", "jira_context".

=== TASK 1: review_checklist ===
A JSON list of strings: a code review checklist with maximum 5 items based ONLY on the context above.
{checklist_rules}
Never generate: null handling, performance bottlenecks, test coverage unless the modified code actually justifies those concerns.

=== TASK 2: suggested_comments ===
A JSON list of up to 3 high-impact specific review comments for this PR grounded in actual changes.
VALUE FILTER (CRITICAL):
REJECT style-only comments, formatting comments, minor naming comments, cosmetic suggestions, redundant annotation suggestions, and trivial refactors.
ALLOW potential bugs, edge cases, validation issues, concurrency concerns, testing gaps, error handling issues, performance risks, security concerns, architecture concerns, dependency concerns.
Only include a comment if: it passes the VALUE FILTER, there is evidence in the diff, and it references actual modified logic.
Never invent try-except recommendations, security vulnerabilities, or missing tests unless explicitly supported by modified code.
If confidence is low (< 80) or no issues exist, use an empty list [].
Each object needs: "file", "issue", "suggestion", "reasoning", "confidence" (0-100), "severity" ("Critical", "Warning", or "Suggestion").

=== TASK 3: executive_summary ===
A single markdown string: a concise executive engineering summary for this PR, for a Tech Lead or Senior Engineer.
Maximum 120 words. Do NOT include file lists, function lists, long explanations, code snippets, or directory names.
Must use EXACTLY these four headings using standard markdown ###: Purpose, Risk, Impact, Recommendation. Format EXACTLY like this:
### Purpose
[1-2 sentences]

### Risk
[Medium/High/Low]. [1 sentence reason]

### Impact
[1 sentence]

### Recommendation
[1 sentence]

=== TASK 4: jira_context ===
{jira_task}

Return ONLY the JSON object, no other text, no markdown code fences.
"""

    res = generate_content(prompt, api_key, provider)

    default_jira = {"Ticket": ticket_id, "Confidence": 80, "Coverage": "N/A", "Missing_Requirements": "None detected"} if ticket_id else None

    if not res or "RATE_LIMIT_EXCEEDED" in res:
        return {
            "review_checklist": ["Verify code changes against requirements"],
            "suggested_comments": [],
            "executive_summary": _rate_limit_fallback_summary(provider, api_key),
            "jira_context": default_jira,
        }

    parsed = parse_json_response(res)
    if not isinstance(parsed, dict):
        return {
            "review_checklist": ["Verify code changes against requirements"],
            "suggested_comments": [],
            "executive_summary": _parse_error_fallback_summary(),
            "jira_context": default_jira,
        }

    checklist = parsed.get("review_checklist")
    if not isinstance(checklist, list) or not checklist:
        checklist = ["Verify code changes against requirements"]
    else:
        checklist = checklist[:5]

    comments = parsed.get("suggested_comments")
    if isinstance(comments, list):
        comments = [c for c in comments if isinstance(c, dict) and c.get('confidence', 0) >= 80]

        def severity_score(sev):
            if sev == "Critical":
                return 3
            if sev == "Warning":
                return 2
            return 1

        comments = sorted(comments, key=lambda x: (severity_score(x.get('severity')), x.get('confidence', 0)), reverse=True)[:3]
    else:
        comments = []

    summary = parsed.get("executive_summary")
    if not isinstance(summary, str) or not summary.strip():
        summary = _parse_error_fallback_summary()

    jira_context = default_jira
    if ticket_id:
        parsed_jira = parsed.get("jira_context")
        if isinstance(parsed_jira, dict):
            jira_context = {
                "Ticket": ticket_id,
                "Confidence": parsed_jira.get("Confidence", 80),
                "Coverage": parsed_jira.get("Coverage", "N/A"),
                "Missing_Requirements": parsed_jira.get("Missing Requirements", "None detected"),
            }

    return {
        "review_checklist": checklist,
        "suggested_comments": comments,
        "executive_summary": summary,
        "jira_context": jira_context,
    }


def explain_security_findings_batch(findings: List[dict], api_key: str = None, provider: str = "gemini") -> List[dict]:
    """
    AI explanations for a whole batch of security findings in ONE LLM call
    instead of one call per finding - the single biggest source of call
    volume in an analysis (previously up to MAX_AI_EXPLAINED_FINDINGS
    separate calls). Findings that don't come back explained (empty list,
    no response, wrong-length/malformed result) are returned unchanged,
    same graceful-degradation behavior the old per-finding version had.
    """
    if not findings:
        return []

    finding_blocks = []
    for i, finding in enumerate(findings):
        finding_blocks.append(f"""Finding {i + 1}:
Name: {finding.get('name')}
Severity: {finding.get('severity')}
Code Snippet:
```
{finding.get('snippet')}
```
Reason: {finding.get('reason')}
""")

    prompt = f"""Explain the following {len(findings)} security findings, each deterministically discovered by the security engine.
DO NOT detect vulnerabilities. Only EXPLAIN what was already found for each one.

{chr(10).join(finding_blocks)}

Return a JSON array with exactly {len(findings)} objects, in the SAME ORDER as the findings above (the first object explains Finding 1, the second explains Finding 2, and so on). Each object must have:
"explanation": "Clear explanation of the risk.",
"recommendation": "How to fix it safely.",
"impact_summary": "What happens if exploited."

Return ONLY the JSON array, no other text, no markdown code fences.
"""
    res = generate_content(prompt, api_key, provider)
    parsed = parse_json_response(res)

    if not isinstance(parsed, list) or len(parsed) != len(findings):
        return findings

    explained = []
    for finding, explanation in zip(findings, parsed):
        if isinstance(explanation, dict):
            explained.append({
                **finding,
                "ai_explanation": explanation.get("explanation"),
                "ai_recommendation": explanation.get("recommendation", finding.get("recommendation")),
                "ai_impact_summary": explanation.get("impact_summary"),
            })
        else:
            explained.append(finding)
    return explained
