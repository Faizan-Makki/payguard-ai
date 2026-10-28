"""Pure display-formatting helpers used by the Streamlit presentation layer."""
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP


def format_currency_amount(currency: str, amount: object) -> str:
    """Format an exact amount with a visible currency code and two decimals."""
    code = str(currency).strip().upper() or "UNKNOWN"
    try:
        value = Decimal(str(amount))
        if not value.is_finite():
            raise InvalidOperation
        value = value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError, TypeError):
        return f"{code} —"
    return f"{code} {value:,.2f}"
