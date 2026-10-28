import pandas as pd
from payguard.demo_data import make_demo_transactions
from payguard.risk_engine import assess_transactions


def test_demo_contains_explainable_high_priorities():
    risk = assess_transactions(make_demo_transactions())
    assert "DEMO-REPEAT-2" in risk.transaction_id.values
    assert "REPEATED_ATTEMPTS" in risk.loc[risk.transaction_id.eq("DEMO-REPEAT-2"), "rules"].iloc[0]
    assert "UNUSUALLY_LARGE" in risk.loc[risk.transaction_id.eq("DEMO-LARGE-1"), "rules"].iloc[0]


def test_ordinary_transactions_are_not_high_priority():
    data = pd.DataFrame([{"transaction_id":"ordinary", "timestamp":"2026-10-01T00:00:00Z", "amount":24, "status":"COMPLETED", "customer_ref":"C1", "order_ref":"O1"}])
    risk = assess_transactions(data)
    assert risk.empty or int(risk.score.max()) < 60


def test_missing_and_malformed_inputs_are_safe():
    data = pd.DataFrame([{"transaction_id":"bad", "timestamp":"not-a-date", "amount":"oops", "status":"FAILED", "customer_ref":None, "order_ref":None}])
    assert assess_transactions(data).empty


def test_failed_payment_cluster_detected():
    data = pd.DataFrame([{"transaction_id":str(i), "timestamp":f"2026-10-01T00:{i:02d}:00Z", "amount":12, "status":"FAILED", "customer_ref":f"C{i}", "order_ref":f"O{i}"} for i in range(5)])
    risk = assess_transactions(data)
    assert all("FAILED_PAYMENT_CLUSTER" in rules for rules in risk.rules)


def test_paypal_denied_status_codes_count_as_failed_attempts():
    data = pd.DataFrame([{"transaction_id":str(i), "timestamp":f"2026-10-01T00:{i:02d}:00Z", "amount":12, "status":"D", "customer_ref":f"C{i}", "order_ref":f"O{i}"} for i in range(5)])
    risk = assess_transactions(data)
    assert all("FAILED_PAYMENT_CLUSTER" in rules for rules in risk.rules)


def test_score_bounded_and_repeated_rule_not_duplicated():
    data = make_demo_transactions()
    risk = assess_transactions(data)
    assert risk.score.between(0, 100).all()
    rules = risk.loc[risk.transaction_id.eq("DEMO-REPEAT-2"), "rules"].iloc[0]
    assert rules.count("REPEATED_ATTEMPTS") == 1


def test_empty_dataset():
    assert assess_transactions(pd.DataFrame()).empty


def test_missing_schema_columns_do_not_crash():
    result = assess_transactions(pd.DataFrame([{"transaction_id":"partial"}]))
    assert result.empty


def test_large_transaction_evidence_includes_currency():
    data = pd.DataFrame([{"transaction_id":"large","timestamp":"2026-10-01T00:00:00Z","amount":800,"currency":"EUR","status":"COMPLETED"}])
    result = assess_transactions(data)
    assert result.iloc[0].evidence[0]["currency"] == "EUR"

