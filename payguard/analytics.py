import pandas as pd


def summarize(data: pd.DataFrame) -> dict:
    if data is None or data.empty:
        return {"count": 0, "volume": 0.0, "volume_by_currency": {}, "success_count": 0, "success_amount": 0.0, "success_amount_by_currency": {}, "failed_count": 0, "refund_count": 0, "refund_amount": 0.0, "refund_amount_by_currency": {}, "refund_available": False}
    amount = pd.to_numeric(data.get("amount", pd.Series(index=data.index, dtype=float)), errors="coerce").fillna(0)
    status = data.get("status", pd.Series("", index=data.index)).astype(str).str.upper()
    currency = data.get("currency", pd.Series("Unknown", index=data.index)).fillna("Unknown").astype(str).str.upper()
    refund = pd.to_numeric(data.get("refund_amount", pd.Series(0, index=data.index)), errors="coerce")
    refund_values = refund.fillna(0)
    refund_available = "refund_amount" in data.columns and bool(pd.to_numeric(data["refund_amount"], errors="coerce").notna().any())
    successful = status.isin(["COMPLETED", "SUCCESS", "S"])
    volume_by_currency = {key: float(amount[currency.eq(key)].sum()) for key in sorted(currency.unique())}
    success_by_currency = {key: float(amount[currency.eq(key) & successful].sum()) for key in sorted(currency.unique())}
    refund_by_currency = {key: float(refund_values[currency.eq(key)].sum()) for key in sorted(currency.unique())}
    single_currency = len(volume_by_currency) == 1
    return {"count": len(data), "volume": float(amount.sum()) if single_currency else None, "volume_by_currency": volume_by_currency, "success_count": int(successful.sum()), "success_amount": float(amount[successful].sum()) if single_currency else None, "success_amount_by_currency": success_by_currency, "failed_count": int(status.isin(["FAILED", "DENIED", "D"]).sum()), "refund_count": int((refund_values > 0).sum()), "refund_amount": float(refund_values.sum()), "refund_amount_by_currency": refund_by_currency, "refund_available": refund_available}

