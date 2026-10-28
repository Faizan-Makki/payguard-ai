from decimal import Decimal

from payguard.presentation import format_currency_amount


def test_large_currency_value_keeps_full_precision_in_readable_one_line_format():
    assert format_currency_amount("USD", 10690.54) == "USD 10,690.54"


def test_currency_formatter_handles_decimal_and_rounds_only_for_display():
    amount = Decimal("9411.855")
    assert format_currency_amount("usd", amount) == "USD 9,411.86"
    assert amount == Decimal("9411.855")


def test_currency_formatter_handles_invalid_values_without_crashing():
    assert format_currency_amount("EUR", "not-a-number") == "EUR —"
