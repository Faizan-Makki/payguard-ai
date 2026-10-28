from types import SimpleNamespace
from unittest.mock import Mock

from payguard import paypal_check


def test_cli_reports_missing_credentials_without_network(monkeypatch, capsys):
    monkeypatch.setattr(paypal_check, "settings", SimpleNamespace(dotenv_loaded=True, paypal_configured=False, data_source="demo"))
    assert paypal_check.main([]) == 2
    output = capsys.readouterr().out
    assert "oauth_authentication=not_attempted" in output
    assert "application_data_source=demo" in output


def test_cli_never_prints_credentials_or_token(monkeypatch, capsys):
    client_id, secret, token = "test-client-id", "test-client-secret", "test-access-token"
    monkeypatch.setattr(paypal_check, "settings", SimpleNamespace(
        dotenv_loaded=True,
        paypal_configured=True,
        paypal_client_id=client_id,
        paypal_client_secret=secret,
        paypal_base_url="https://api-m.sandbox.paypal.com",
        data_source="demo",
    ))
    client = Mock()
    client._token.return_value = token
    client.fetch_transactions.return_value = SimpleNamespace(transactions=[{}], total_items_reported=1, pages_read=1, malformed_rows_skipped=0)
    monkeypatch.setattr(paypal_check, "PayPalClient", Mock(return_value=client))

    assert paypal_check.main([]) == 0
    output = capsys.readouterr().out
    assert "oauth_authentication=success" in output
    assert "transaction_retrieval=success" in output
    assert all(value not in output for value in (client_id, secret, token))
