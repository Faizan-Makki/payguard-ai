from dataclasses import dataclass, asdict
import pandas as pd


@dataclass
class Finding:
    transaction_id: str
    transaction_key: str
    score: int
    severity: str
    rules: list[str]
    evidence: list[dict]
    explanation: str
    next_steps: list[str]
    assessed_at: str

    def to_dict(self):
        return asdict(self)


def assess_transactions(data: pd.DataFrame, repeat_window_minutes: int = 15) -> pd.DataFrame:
    """Deterministic prioritization rules; scores are not fraud probabilities."""
    if data is None or data.empty:
        return pd.DataFrame(columns=["transaction_id", "score", "severity", "rules", "evidence", "explanation", "next_steps", "assessed_at"])
    df = data.copy()
    for column in ("timestamp", "amount", "status", "customer_ref", "order_ref", "currency", "transaction_id"):
        if column not in df.columns:
            df[column] = None
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")
    df["amount"] = pd.to_numeric(df["amount"], errors="coerce")
    df["currency"] = df["currency"].fillna("Unknown").astype(str).str.upper()
    valid = df.loc[df.amount.notna() & (df.amount > 0)]
    baselines = {cur: float(rows.amount.quantile(.95)) if len(rows) >= 20 else 250.0 for cur, rows in valid.groupby("currency")}
    results = []
    for idx, row in df.iterrows():
        score, rules, evidence, explanations = 0, [], [], []
        customer = row.get("customer_ref")
        order = row.get("order_ref")
        time = row.get("timestamp")
        if pd.notna(time) and ((isinstance(customer, str) and customer.strip()) or (isinstance(order, str) and order.strip())):
            keys = pd.Series(False, index=df.index)
            if isinstance(customer, str) and customer.strip(): keys |= df.customer_ref.eq(customer)
            if isinstance(order, str) and order.strip(): keys |= df.order_ref.eq(order)
            nearby = df.loc[keys & df.timestamp.notna() & ((df.timestamp - time).abs() <= pd.Timedelta(minutes=repeat_window_minutes))]
            if len(nearby) >= 3:
                score += 35; rules.append("REPEATED_ATTEMPTS")
                evidence.append({"attempts": int(len(nearby)), "window_minutes": repeat_window_minutes, "customer_ref": customer if isinstance(customer, str) else None})
                explanations.append(f"{len(nearby)} attempts share a customer or order reference within {repeat_window_minutes} minutes.")
        baseline = baselines.get(row.currency, 250.0)
        threshold = max(baseline * 2.0, 500.0)
        if pd.notna(row.amount) and row.amount > threshold:
            score += 40; rules.append("UNUSUALLY_LARGE")
            evidence.append({"amount": float(row.amount), "currency": row.currency, "threshold": round(threshold, 2), "baseline_p95": round(baseline, 2)})
            explanations.append(f"Amount {row.amount:.2f} {row.currency} exceeds the configured investigation threshold of {threshold:.2f} {row.currency} (historical 95th percentile × 2, with a 500 minimum).")
        failed = str(row.get("status", "")).upper() in {"FAILED", "DENIED", "D"}
        # A local cluster of at least 5 failed records in one hour is a rule event.
        if failed and pd.notna(time):
            hourly = df.loc[df.timestamp.notna() & df.status.astype(str).str.upper().isin({"FAILED", "DENIED", "D"}) & ((df.timestamp - time).abs() <= pd.Timedelta(hours=1))]
            if len(hourly) >= 5:
                score += 25; rules.append("FAILED_PAYMENT_CLUSTER")
                evidence.append({"failed_attempts": int(len(hourly)), "window_hours": 1})
                explanations.append(f"{len(hourly)} failed attempts occurred in a rolling one-hour window.")
        score = min(score, 100)
        severity = "High" if score >= 60 else "Medium" if score >= 30 else "Low"
        if score:
            transaction_id = str(row.get("transaction_id", idx))
            transaction_key = row.get("transaction_key")
            if not isinstance(transaction_key, str) or not transaction_key:
                transaction_key = transaction_id
            results.append(Finding(transaction_id, transaction_key, score, severity, rules, evidence, " ".join(explanations), ["Review payment timeline and order context.", "Confirm the event with your payment records before taking action."], pd.Timestamp.now(tz="UTC").isoformat()).to_dict())
    return pd.DataFrame(results)

