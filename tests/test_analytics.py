import pandas as pd
from payguard.analytics import summarize


def test_empty_summary():
    assert summarize(pd.DataFrame())["count"] == 0


def test_metrics_derived_from_rows_and_refunds():
    data = pd.DataFrame([{"amount":10,"status":"COMPLETED","refund_amount":0},{"amount":5,"status":"FAILED","refund_amount":2}])
    result = summarize(data)
    assert result["count"] == 2 and result["volume"] == 15
    assert result["success_count"] == 1 and result["failed_count"] == 1
    assert result["refund_amount"] == 2


def test_refund_absence_is_reported_unavailable():
    result = summarize(pd.DataFrame([{"amount":10,"status":"COMPLETED"}]))
    assert result["refund_count"] == 0 and result["refund_available"] is False


def test_mixed_currencies_are_never_added_as_one_volume():
    result = summarize(pd.DataFrame([
        {"amount":10,"currency":"USD","status":"COMPLETED"},
        {"amount":1000,"currency":"JPY","status":"FAILED"},
    ]))
    assert result["volume"] is None
    assert result["volume_by_currency"] == {"JPY": 1000.0, "USD": 10.0}


def test_missing_amount_and_currency_columns_are_handled():
    result = summarize(pd.DataFrame([{"status":"FAILED"}]))
    assert result["count"] == 1
    assert result["volume_by_currency"] == {"UNKNOWN": 0.0}

