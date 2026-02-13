from __future__ import annotations

from app.gateway.telegram import (
    _classify_provider_error,
    _format_provider_error_message,
    _should_try_fallback,
)


def test_classify_provider_error_auth_401():
    info = _classify_provider_error(Exception("OpenAI API 401: invalid_api_key"))
    assert info.code == "auth_error"
    assert info.http_status == 401


def test_classify_provider_error_rate_limit_429():
    info = _classify_provider_error(Exception("DeepSeek API 429: rate limit reached"))
    assert info.code == "rate_limit"
    assert info.http_status == 429


def test_format_provider_error_message_masks_token_like_strings():
    raw = "OpenAI API 401: invalid_api_key sk-secret-1234567890 and 123456789:AAAAABBBBBCCCCCDDDDD"
    text = _format_provider_error_message(
        provider_name="openai_default",
        exc=Exception(raw),
        debug=True,
        error_id="abc12345",
    )
    assert "openai_default" in text
    assert "abc12345" in text
    assert "sk-secret-1234567890" not in text
    assert "123456789:AAAAABBBBBCCCCCDDDDD" not in text


def test_should_try_fallback_for_retryable_provider_errors_only():
    assert _should_try_fallback(Exception("Provider temporarily unavailable (503)")) is True
    assert _should_try_fallback(Exception("local parsing bug without status code")) is False
