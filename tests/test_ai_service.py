import json
from unittest.mock import Mock, patch

import requests

from payguard.ai_service import explain_finding


FINDING = {
    "explanation": "Amount 700 exceeds the threshold of 500",
    "evidence": [{"amount": 700, "threshold": 500}],
    "next_steps": ["Review order context"],
}
MODEL_OUTPUT = {
    "why_flagged": "The amount is above the rule threshold.",
    "evidence_summary": "The engine records 700 against a threshold of 500.",
    "uncertainty": "This does not establish intent.",
    "next_steps": ["Invented step"],
}


def gemini_response(payload=MODEL_OUTPUT):
    response = Mock()
    response.json.return_value = {
        "candidates": [{"content": {"parts": [{"text": json.dumps(payload)}]}}]
    }
    return response


def test_missing_key_uses_transparent_fallback():
    result = explain_finding(FINDING)
    assert result["provider"] == "Deterministic fallback"
    assert "not a determination" in result["uncertainty"]
    assert result["evidence"] == FINDING["evidence"]
    assert result["fallback_reason"] == "missing_api_key"


def test_whitespace_key_is_treated_as_missing():
    assert explain_finding(FINDING, "   ")["fallback_reason"] == "missing_api_key"


def test_gemini_success_uses_native_endpoint_and_keeps_engine_evidence():
    response = gemini_response()
    with patch("payguard.ai_service.requests.post", return_value=response) as post:
        result = explain_finding(FINDING, "test-gemini-key", "gemini-2.5-flash")

    request = post.call_args.kwargs
    assert post.call_args.args[0] == "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"
    assert request["headers"]["x-goog-api-key"] == "test-gemini-key"
    assert "Authorization" not in request["headers"]
    assert request["timeout"] == 30
    assert request["json"]["generationConfig"]["responseMimeType"] == "application/json"
    assert request["json"]["generationConfig"]["thinkingConfig"] == {"thinkingLevel": "low"}
    assert request["json"]["generationConfig"]["responseSchema"]["required"] == [
        "why_flagged", "evidence_summary", "uncertainty", "next_steps"
    ]
    assert result["provider"] == "Gemini response"
    assert result["evidence"] == FINDING["evidence"]
    assert result["next_steps"] == FINDING["next_steps"]
    assert "test-gemini-key" not in str(result)


def test_malformed_provider_response_uses_fallback():
    response = Mock()
    response.json.return_value = {"candidates": []}
    with patch("payguard.ai_service.requests.post", return_value=response):
        result = explain_finding(FINDING, "key")
    assert result["provider"] == "Deterministic fallback"
    assert result["fallback_reason"] == "invalid_provider_response"


def test_invalid_schema_uses_fallback():
    response = gemini_response({"why_flagged": "incomplete"})
    with patch("payguard.ai_service.requests.post", return_value=response):
        result = explain_finding(FINDING, "key")
    assert result["fallback_reason"] == "invalid_provider_response"


def test_provider_timeout_uses_fallback():
    with patch("payguard.ai_service.requests.post", side_effect=requests.Timeout):
        result = explain_finding(FINDING, "key")
    assert result["fallback_reason"] == "timeout"


def test_provider_http_error_uses_fallback():
    with patch("payguard.ai_service.requests.post", side_effect=requests.ConnectionError):
        result = explain_finding(FINDING, "key")
    assert result["fallback_reason"] == "provider_error"


def test_provider_http_status_is_reported_without_response_body():
    response = Mock()
    response.status_code = 429
    response.raise_for_status.side_effect = requests.HTTPError(response=response)
    with patch("payguard.ai_service.requests.post", return_value=response):
        result = explain_finding(FINDING, "key")
    assert result["fallback_reason"] == "provider_http_429"


def test_invalid_model_is_rejected_without_request():
    with patch("payguard.ai_service.requests.post") as post:
        result = explain_finding(FINDING, "key", "../unexpected")
    post.assert_not_called()
    assert result["fallback_reason"] == "invalid_model"


def test_non_json_serializable_finding_uses_fallback():
    finding = {**FINDING, "extra": object()}
    with patch("payguard.ai_service.requests.post") as post:
        result = explain_finding(finding, "key")
    post.assert_not_called()
    assert result["fallback_reason"] == "invalid_finding"
