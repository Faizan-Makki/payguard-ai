import pandas as pd

from payguard.risk_engine import assess_transactions
from payguard.analytics import summarize


def test_amount_exactly_at_threshold_is_not_flagged():
    data = pd.DataFrame([
        {
            "transaction_id": "exact-limit",
            "timestamp": "2026-10-01T00:00:00Z",
            "amount": 500,
            "currency": "USD",
            "status": "COMPLETED",
        }
    ])

    result = assess_transactions(data)

    assert result.empty


def test_amount_just_above_threshold_is_flagged():
    data = pd.DataFrame([
        {
            "transaction_id": "above-limit",
            "timestamp": "2026-10-01T00:00:00Z",
            "amount": 500.01,
            "currency": "USD",
            "status": "COMPLETED",
        }
    ])

    result = assess_transactions(data)

    assert "UNUSUALLY_LARGE" in result.iloc[0]["rules"]


def test_repeat_attempt_at_exact_time_window_boundary():
    data = pd.DataFrame([
        {
            "transaction_id": "attempt-1",
            "timestamp": "2026-10-01T00:00:00Z",
            "amount": 12,
            "status": "FAILED",
            "customer_ref": "CUSTOMER-1",
            "order_ref": "ORDER-1",
        },
        {
            "transaction_id": "attempt-2",
            "timestamp": "2026-10-01T00:07:00Z",
            "amount": 12,
            "status": "FAILED",
            "customer_ref": "CUSTOMER-1",
            "order_ref": "ORDER-1",
        },
        {
            "transaction_id": "attempt-3",
            "timestamp": "2026-10-01T00:15:00Z",
            "amount": 12,
            "status": "FAILED",
            "customer_ref": "CUSTOMER-1",
            "order_ref": "ORDER-1",
        },
    ])

    result = assess_transactions(data)

    first_attempt = result.loc[
        result["transaction_id"].eq("attempt-1")
    ]

    assert not first_attempt.empty
    assert "REPEATED_ATTEMPTS" in first_attempt.iloc[0]["rules"]

def test_negative_transaction_amount_does_not_crash():
    data = pd.DataFrame([
        {
            "amount": -50,
            "currency": "USD",
            "status": "COMPLETED",
        }
    ])

    result = summarize(data)

    assert result["count"] == 1
    assert result["volume"] == -50.0


def test_negative_refund_amount_does_not_crash():
    data = pd.DataFrame([
        {
            "amount": 100,
            "currency": "USD",
            "status": "COMPLETED",
            "refund_amount": -10,
        }
    ])

    result = summarize(data)

    assert result["refund_count"] == 0
    assert result["refund_amount"] == -10.0