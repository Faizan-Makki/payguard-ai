from unittest.mock import Mock

import pytest

from payguard.checkout_service import (
    CheckoutError,
    PayPalCheckoutStore,
    assess_sandbox_capture,
    create_sandbox_order,
    process_cancellation,
    verify_and_capture,
)


ORDER_ID = "ORDER123"
STATE = "a" * 48


def completed_order(order_id=ORDER_ID, status="COMPLETED", capture_status="COMPLETED"):
    return {
        "id": order_id,
        "status": status,
        "purchase_units": [{"payments": {"captures": [{
            "id": "CAPTURE123",
            "status": capture_status,
            "create_time": "2026-10-29T10:11:12Z",
            "amount": {"currency_code": "USD", "value": "1.00"},
            "payee": {"email_address": "must-not-be-stored@example.invalid"},
        }]}}],
    }


def setup_checkout(tmp_path):
    store = PayPalCheckoutStore(tmp_path / "checkout.sqlite")
    store.create_attempt(STATE)
    client = Mock()
    client.create_order.return_value = {"id": ORDER_ID, "approval_url": "https://www.sandbox.paypal.com/checkoutnow?token=ORDER123"}
    created = create_sandbox_order(client, store, STATE, "http://localhost:8501/", "http://localhost:8501/")
    return store, client, created


def test_verified_approval_captures_and_maps_only_safe_transaction_fields(tmp_path):
    store, client, created = setup_checkout(tmp_path)
    client.get_order.return_value = {"id": ORDER_ID, "status": "APPROVED"}
    client.capture_order.return_value = completed_order()

    result = verify_and_capture(client, store, ORDER_ID, STATE)

    assert created["status"] == "AWAITING_APPROVAL"
    assert result["status"] == "PAID"
    tx = result["transaction"]
    assert (tx["transaction_id"], tx["amount"], tx["currency"], tx["status"]) == ("CAPTURE123", 1.0, "USD", "COMPLETED")
    assert tx["timestamp"] == "2026-10-29T10:11:12Z"
    assert tx["source"] == "PayPal Sandbox" and tx["is_demo"] is False
    assert tx["customer_ref"] is None
    assert "email" not in str(tx)
    client.capture_order.assert_called_once_with(ORDER_ID, result["capture_request_id"])


def test_cancellation_verifies_order_but_never_captures(tmp_path):
    store, client, _ = setup_checkout(tmp_path)
    client.get_order.return_value = {"id": ORDER_ID, "status": "CREATED"}

    result = process_cancellation(client, store, ORDER_ID, STATE)

    assert result["status"] == "CANCELLED"
    client.get_order.assert_called_once_with(ORDER_ID)
    client.capture_order.assert_not_called()


def test_invalid_or_mismatched_order_id_never_calls_paypal(tmp_path):
    store, client, _ = setup_checkout(tmp_path)
    with pytest.raises(CheckoutError, match="does not match"):
        verify_and_capture(client, store, "ANOTHERORDER", STATE)
    with pytest.raises(CheckoutError):
        verify_and_capture(client, store, "bad/id", STATE)
    client.get_order.assert_not_called()
    client.capture_order.assert_not_called()


def test_failed_or_noncompleted_capture_is_not_marked_paid_and_can_retry(tmp_path):
    store, client, _ = setup_checkout(tmp_path)
    client.get_order.return_value = {"id": ORDER_ID, "status": "APPROVED"}
    client.capture_order.return_value = completed_order(capture_status="PENDING")

    with pytest.raises(CheckoutError, match="completed Sandbox capture"):
        verify_and_capture(client, store, ORDER_ID, STATE)

    assert store.get_attempt(STATE)["status"] == "AWAITING_APPROVAL"
    client.capture_order.side_effect = RuntimeError("sanitized mocked failure")
    with pytest.raises(RuntimeError):
        verify_and_capture(client, store, ORDER_ID, STATE)
    assert store.get_attempt(STATE)["status"] == "AWAITING_APPROVAL"
    assert client.capture_order.call_args_list[0].args == client.capture_order.call_args_list[1].args


def test_duplicate_processing_returns_saved_capture_without_second_capture(tmp_path):
    store, client, _ = setup_checkout(tmp_path)
    client.get_order.return_value = {"id": ORDER_ID, "status": "APPROVED"}
    client.capture_order.return_value = completed_order()

    first = verify_and_capture(client, store, ORDER_ID, STATE)
    second = verify_and_capture(client, store, ORDER_ID, STATE)

    assert second["transaction"] == first["transaction"]
    client.capture_order.assert_called_once()
    client.get_order.assert_called_once()


def test_single_sandbox_capture_is_assessed_by_existing_risk_engine_without_identity_signal(tmp_path):
    store, client, _ = setup_checkout(tmp_path)
    client.get_order.return_value = {"id": ORDER_ID, "status": "APPROVED"}
    client.capture_order.return_value = completed_order()
    paid = verify_and_capture(client, store, ORDER_ID, STATE)

    findings = assess_sandbox_capture(paid["transaction"])

    assert findings.empty  # USD 1 alone is not evidence of suspicious activity.


def test_cancelled_checkout_cannot_later_be_captured(tmp_path):
    store, client, _ = setup_checkout(tmp_path)
    client.get_order.return_value = {"id": ORDER_ID, "status": "CREATED"}
    process_cancellation(client, store, ORDER_ID, STATE)
    with pytest.raises(CheckoutError, match="cancelled"):
        verify_and_capture(client, store, ORDER_ID, STATE)
    client.capture_order.assert_not_called()
