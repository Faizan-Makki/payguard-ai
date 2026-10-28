from unittest.mock import Mock, patch

import requests

from payguard.ai_service import explain_finding

FINDING = {"explanation":"Amount 700 exceeds the threshold of 500", "evidence":[{"amount":700,"threshold":500}], "next_steps":["Review order context"]}


def test_missing_key_uses_transparent_fallback():
    result = explain_finding(FINDING)
    assert result["provider"] == "Deterministic fallback"
    assert "not a determination" in result["uncertainty"]
    assert result["evidence"] == FINDING["evidence"]
    assert result["fallback_reason"] == "missing_api_key"


def test_whitespace_key_is_treated_as_missing():
    assert explain_finding(FINDING, "   ")["fallback_reason"] == "missing_api_key"


def test_provider_success_keeps_engine_evidence_and_next_steps():
    payload = {"why_flagged":"The amount is above the rule threshold.", "evidence_summary":"The engine records 700 against a threshold of 500.", "uncertainty":"This does not establish intent.", "next_steps":["Invented step"]}
    response = Mock()
    response.json.return_value = {"choices":[{"message":{"content":__import__("json").dumps(payload)}}]}
    with patch("payguard.ai_service.requests.post", return_value=response) as post:
        result = explain_finding(FINDING, "test-secret", "test-model")
    assert result["provider"] == "OpenAI response"
    assert result["evidence"] == FINDING["evidence"]
    assert result["next_steps"] == FINDING["next_steps"]
    assert post.call_args.kwargs["timeout"] == 15
    assert "test-secret" not in str(result)


def test_invalid_provider_json_uses_fallback():
    response = Mock()
    response.json.return_value = {"choices":[{"message":{"content":"{}"}}]}
    with patch("payguard.ai_service.requests.post", return_value=response):
        result = explain_finding(FINDING, "key")
    assert result["provider"] == "Deterministic fallback"
    assert result["fallback_reason"] == "invalid_provider_response"


def test_provider_timeout_uses_fallback():
    with patch("payguard.ai_service.requests.post", side_effect=requests.Timeout):
        result = explain_finding(FINDING, "key")
    assert result["fallback_reason"] == "timeout"


def test_provider_http_error_uses_fallback():
    with patch("payguard.ai_service.requests.post", side_effect=requests.ConnectionError):
        result = explain_finding(FINDING, "key")
    assert result["fallback_reason"] == "provider_error"

