from unittest.mock import patch, MagicMock

from app.services.llm import generate_content, generate_executive_summary

# Regression coverage for a real user-reported bug: the rate-limit fallback
# message always blamed "the global free-tier pool" even when a BYOK key was
# the one that got rate-limited, making it look like BYOK wasn't being used
# at all when it actually was.


class _RateLimitedResponse:
    status_code = 429


def test_byok_rate_limit_blames_the_users_own_key_not_the_shared_pool():
    with patch("requests.post", return_value=_RateLimitedResponse()), \
         patch("app.services.llm.time.sleep"):
        msg = generate_executive_summary({"pr_type": "BACKEND"}, api_key="user-own-key", provider="gemini")
    assert "Your Gemini API Key Was Rate-Limited" in msg
    assert "global" not in msg.lower()


def test_shared_pool_rate_limit_still_blames_the_shared_pool():
    with patch("requests.post", return_value=_RateLimitedResponse()), \
         patch("app.services.llm.time.sleep"), \
         patch("app.services.llm.settings.GEMINI_API_KEY", "shared-fallback-key"):
        msg = generate_executive_summary({"pr_type": "BACKEND"}, api_key=None, provider="gemini")
    assert "Global Rate Limit Exceeded" in msg


def test_byok_rate_limit_message_is_provider_aware():
    with patch("requests.post", return_value=_RateLimitedResponse()), \
         patch("app.services.llm.time.sleep"):
        msg = generate_executive_summary({"pr_type": "BACKEND"}, api_key="user-openai-key", provider="openai")
    assert "Your OpenAI API Key Was Rate-Limited" in msg


def _success_response(json_body):
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = json_body
    return resp


def test_gemini_uses_a_current_non_retired_model():
    # Regression coverage: gemini-2.0-flash was retired by Google (started
    # returning 404 "no longer available" on every request, not just
    # rate-limited ones - a real production incident, not a hypothetical).
    # Pinning the expected model name here means a future copy-paste of an
    # old snippet, or reverting this line by accident, fails a test instead
    # of silently breaking every shared-pool Gemini request again.
    with patch("requests.post", return_value=_success_response(
        {"candidates": [{"content": {"parts": [{"text": "ok"}]}}]}
    )) as mock_post:
        generate_content("prompt", api_key="k", provider="gemini")
    called_url = mock_post.call_args[0][0]
    assert "gemini-2.0-flash" not in called_url
    assert "models/gemini-3.6-flash:generateContent" in called_url


def test_gemini_retries_and_succeeds_after_transient_rate_limits():
    responses = [_RateLimitedResponse(), _RateLimitedResponse(), _success_response(
        {"candidates": [{"content": {"parts": [{"text": "ok"}]}}]}
    )]
    with patch("requests.post", side_effect=responses) as mock_post, \
         patch("app.services.llm.time.sleep") as mock_sleep:
        result = generate_content("prompt", api_key="k", provider="gemini")
    assert result == "ok"
    assert mock_post.call_count == 3
    assert mock_sleep.call_count == 2  # backed off before attempt 2 and attempt 3


def test_groq_uses_the_openai_compatible_chat_completions_shape():
    with patch("requests.post", return_value=_success_response(
        {"choices": [{"message": {"content": "hello from groq"}}]}
    )) as mock_post:
        result = generate_content("prompt", api_key="gsk_test", provider="groq")
    assert result == "hello from groq"
    assert mock_post.call_args[0][0] == "https://api.groq.com/openai/v1/chat/completions"
    assert mock_post.call_args[1]["json"]["model"] == "llama-3.3-70b-versatile"


def test_groq_rate_limit_message_is_provider_aware():
    with patch("requests.post", return_value=_RateLimitedResponse()), \
         patch("app.services.llm.time.sleep"):
        msg = generate_executive_summary({"pr_type": "BACKEND"}, api_key="user-groq-key", provider="groq")
    assert "Your Groq API Key Was Rate-Limited" in msg


def test_json_mode_sets_response_format_for_groq_and_openai():
    # Real bug: Groq's Llama model, asked only in prose to "return JSON",
    # sometimes doesn't - json_mode forces each provider's own structured-
    # output mode instead of relying on instruction-following alone.
    for provider in ("groq", "openai"):
        with patch("requests.post", return_value=_success_response(
            {"choices": [{"message": {"content": "{}"}}]}
        )) as mock_post:
            generate_content("prompt", api_key="k", provider=provider, json_mode=True)
        assert mock_post.call_args[1]["json"]["response_format"] == {"type": "json_object"}


def test_json_mode_sets_response_mime_type_for_gemini():
    with patch("requests.post", return_value=_success_response(
        {"candidates": [{"content": {"parts": [{"text": "{}"}]}}]}
    )) as mock_post:
        generate_content("prompt", api_key="k", provider="gemini", json_mode=True)
    assert mock_post.call_args[1]["json"]["generationConfig"]["response_mime_type"] == "application/json"


def test_json_mode_defaults_to_off():
    with patch("requests.post", return_value=_success_response(
        {"choices": [{"message": {"content": "plain text"}}]}
    )) as mock_post:
        generate_content("prompt", api_key="k", provider="openai")
    assert "response_format" not in mock_post.call_args[1]["json"]


def test_openai_now_retries_instead_of_giving_up_immediately():
    # Before this fix, OpenAI had zero retry logic at all and returned the
    # rate-limit error on the very first 429. This is the regression test.
    responses = [_RateLimitedResponse(), _success_response(
        {"choices": [{"message": {"content": "ok"}}]}
    )]
    with patch("requests.post", side_effect=responses) as mock_post, \
         patch("app.services.llm.time.sleep") as mock_sleep:
        result = generate_content("prompt", api_key="k", provider="openai")
    assert result == "ok"
    assert mock_post.call_count == 2
    assert mock_sleep.call_count == 1
