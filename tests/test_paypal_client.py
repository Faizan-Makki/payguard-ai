from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch

import pytest
import requests

from payguard.paypal_client import PayPalAPIError, PayPalClient


def response(body):
    result = Mock()
    result.raise_for_status.return_value = None
    result.json.return_value = body
    return result


def transaction(identifier):
    return {"transaction_info": {
        "transaction_id": identifier,
        "transaction_initiation_date": "2026-10-20T12:00:00Z",
        "transaction_amount": {"value": "21.25", "currency_code": "USD"},
        "transaction_status": "S",
        "paypal_reference_id": "order-ref",
    }}


def test_auth_and_reporting_parameters_and_response_mapping():
    client = PayPalClient("id", "secret")
    start, end = datetime(2026,10,20,tzinfo=timezone.utc), datetime(2026,10,21,tzinfo=timezone.utc)
    with patch("payguard.paypal_client.requests.post", return_value=response({"access_token":"token"})) as post, \
         patch("payguard.paypal_client.requests.get", return_value=response({"transaction_details":[transaction("tx-1")],"total_pages":1,"total_items":1})) as get:
        result = client.fetch_transactions(start, end)
    assert post.call_args.kwargs["auth"] == ("id", "secret")
    assert post.call_args.kwargs["data"] == {"grant_type":"client_credentials"}
    assert get.call_args.args[0].endswith("/v1/reporting/transactions")
    assert get.call_args.kwargs["params"]["start_date"] == "2026-10-20T00:00:00Z"
    assert get.call_args.kwargs["params"]["fields"] == "transaction_info"
    assert get.call_args.kwargs["params"]["balance_affecting_records_only"] == "N"
    assert result.transactions[0]["amount"] == 21.25
    assert result.transactions[0]["is_demo"] is False


def test_all_pages_are_retrieved_past_old_five_page_limit():
    client = PayPalClient("id", "secret")
    page_responses = [response({"transaction_details":[transaction(f"tx-{i}")],"total_pages":6,"total_items":6}) for i in range(1,7)]
    with patch("payguard.paypal_client.requests.post", return_value=response({"access_token":"token"})), \
         patch("payguard.paypal_client.requests.get", side_effect=page_responses) as get:
        result = client.fetch_transactions()
    assert len(result.transactions) == 6
    assert result.pages_read == 6
    assert get.call_count == 6


def test_connection_probe_can_succeed_with_zero_matching_transactions():
    client = PayPalClient("id", "secret")
    with patch("payguard.paypal_client.requests.post", return_value=response({"access_token":"token"})), \
         patch("payguard.paypal_client.requests.get", return_value=response({"transaction_details":[],"total_pages":0,"total_items":0})):
        result = client.test_connection()
    assert result["connected"] is True
    assert result["total_items_reported"] == 0


def test_query_rejects_over_31_day_range_and_naive_datetime():
    client = PayPalClient("id", "secret")
    now = datetime.now(timezone.utc)
    with pytest.raises(ValueError, match="31-day"):
        client.fetch_transactions(now - timedelta(days=32), now)
    with pytest.raises(ValueError, match="timezone"):
        client.fetch_transactions(datetime(2026,1,1), now)


def test_client_rejects_live_or_non_paypal_hosts():
    with pytest.raises(ValueError, match="official PayPal Sandbox"):
        PayPalClient("id", "secret", "https://api-m.paypal.com")


def test_oauth_scope_is_checked_without_printing_scope_list():
    client = PayPalClient("id", "secret")
    body = {"access_token":"test-token", "scope":"openid https://uri.paypal.com/services/reporting/search/read"}
    with patch("payguard.paypal_client.requests.post", return_value=response(body)):
        client._token()
    assert client.transaction_search_scope_present is True


def test_oauth_scope_missing_is_reported_as_boolean():
    client = PayPalClient("id", "secret")
    with patch("payguard.paypal_client.requests.post", return_value=response({"access_token":"test-token", "scope":"openid"})):
        client._token()
    assert client.transaction_search_scope_present is False


def test_malformed_response_fails_explicitly():
    client = PayPalClient("id", "secret")
    with patch("payguard.paypal_client.requests.post", return_value=response({"access_token":"token"})), \
         patch("payguard.paypal_client.requests.get", return_value=response({"unexpected":[]})):
        with pytest.raises(PayPalAPIError, match="invalid transaction_details"):
            client.fetch_transactions()


def test_malformed_rows_are_counted_and_not_fabricated():
    client = PayPalClient("id", "secret")
    body = {"transaction_details":[transaction("ok"), {"transaction_info":{"transaction_id":"bad"}}, {"transaction_info":{**transaction("bad-time")["transaction_info"], "transaction_initiation_date":"nonsense"}}], "total_pages":1,"total_items":3}
    with patch("payguard.paypal_client.requests.post", return_value=response({"access_token":"token"})), \
         patch("payguard.paypal_client.requests.get", return_value=response(body)):
        result = client.fetch_transactions()
    assert [row["transaction_id"] for row in result.transactions] == ["ok"]
    assert result.malformed_rows_skipped == 2


def test_page_safety_limit_fails_instead_of_returning_partial_data():
    client = PayPalClient("id", "secret")
    with patch("payguard.paypal_client.requests.post", return_value=response({"access_token":"token"})), \
         patch("payguard.paypal_client.requests.get", return_value=response({"transaction_details":[],"total_pages":21,"total_items":2100})) as get:
        with pytest.raises(PayPalAPIError, match="safety limit"):
            client.fetch_transactions()
    assert get.call_count == 1


def test_request_error_is_sanitized():
    client = PayPalClient("id", "super-secret")
    with patch("payguard.paypal_client.requests.post", side_effect=requests.Timeout):
        with pytest.raises(PayPalAPIError, match="timed out") as error:
            client.fetch_transactions()
    assert "super-secret" not in str(error.value)
