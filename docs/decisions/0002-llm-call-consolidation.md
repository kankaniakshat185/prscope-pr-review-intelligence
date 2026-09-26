# 0002 — Consolidating LLM calls under real rate-limit pressure

## Problem
The shared free-tier Gemini pool started getting rate-limited in production.
A single analysis fired up to ~14 separate LLM calls: per-finding security
explanations (one call per finding), plus separate calls for the review
checklist, suggested comments, executive summary, and Jira alignment.

## Approach
- Merged the four review-generation calls into one `generate_review_bundle`
  call returning a single JSON object with all four sections.
- Merged all per-finding security explanations into one
  `explain_security_findings_batch` call.
- Added Groq as a third BYOK/shared-pool provider (alongside Gemini and
  OpenAI) so a rate-limited provider isn't a hard stop.
- Forced each provider's native structured-output mode (`json_mode` →
  `response_format: json_object` for OpenAI/Groq, `response_mime_type:
  application/json` for Gemini) instead of relying on prompt instructions
  alone — Groq's model was observed returning malformed, non-JSON responses
  under prose-only "return JSON" instructions in production.

## Result
At most 2 LLM calls per analysis instead of up to ~14 — the dominant fix for
the quota pressure users were hitting. The deterministic engines
(risk/reviewability/security/architecture/dependency graph) were already a
separate, fast, non-LLM code path (`/analyze`) — this consolidation only
touches the slower AI-enrichment path (`/analyze/enrich`).

## Tradeoff
One failed LLM call now fails a larger unit of output (the whole bundle, or
the whole batch of finding explanations) instead of just one section.

**Code:** `backend/app/services/llm.py`
(`generate_review_bundle`, `explain_security_findings_batch`)
