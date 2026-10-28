import numpy as np
import pandas as pd


def make_demo_transactions(seed: int = 41, count: int = 180) -> pd.DataFrame:
    """Create reproducible, clearly synthetic merchant payment activity."""
    rng = np.random.default_rng(seed)
    end = pd.Timestamp.now(tz="UTC").floor("h")
    times = end - pd.to_timedelta(rng.integers(1, 30 * 24, size=count), unit="h")
    statuses = rng.choice(["COMPLETED", "FAILED", "PENDING", "REFUNDED"], count, p=[.82, .11, .05, .02])
    amounts = np.round(np.clip(rng.lognormal(3.55, .75, count), 8, 1800), 2)
    frame = pd.DataFrame({
        "transaction_id": [f"DEMO-{i:05d}" for i in range(count)],
        "timestamp": times,
        "amount": amounts,
        "currency": "USD",
        "status": statuses,
        "event_code": "DEMO_PAYMENT",
        "customer_ref": [f"SYN-C{n:03d}" for n in rng.integers(1, 75, count)],
        "order_ref": [f"ORD-{n:05d}" for n in range(count)],
        "source": "Demo Data",
        "is_demo": True,
        "refund_amount": np.where(statuses == "REFUNDED", amounts, 0.0),
    })
    frame["transaction_key"] = frame["transaction_id"]
    # Controlled, explainable scenarios inserted at the end of the series.
    anchor = end - pd.Timedelta(hours=2)
    scenarios = [
        ("DEMO-REPEAT-1", anchor, 64.00, "FAILED", "SYN-C900", "ORD-RPT-1", 0),
        ("DEMO-REPEAT-2", anchor + pd.Timedelta(minutes=3), 64.00, "FAILED", "SYN-C900", "ORD-RPT-1", 0),
        ("DEMO-REPEAT-3", anchor + pd.Timedelta(minutes=7), 64.00, "COMPLETED", "SYN-C900", "ORD-RPT-1", 0),
        ("DEMO-LARGE-1", end - pd.Timedelta(hours=1), 2450.00, "COMPLETED", "SYN-C901", "ORD-LARGE", 0),
    ]
    extra = pd.DataFrame(scenarios, columns=["transaction_id", "timestamp", "amount", "status", "customer_ref", "order_ref", "refund_amount"])
    extra["currency"], extra["source"], extra["is_demo"] = "USD", "Demo Data", True
    extra["transaction_key"] = extra["transaction_id"]
    extra["event_code"] = "DEMO_PAYMENT"
    return pd.concat([frame, extra], ignore_index=True).sort_values("timestamp").reset_index(drop=True)

