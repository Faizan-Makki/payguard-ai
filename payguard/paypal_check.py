"""Safe, read-only command-line verification for PayPal Sandbox credentials."""
import argparse
import sys
from payguard.config import settings
from payguard.paypal_client import PayPalAPIError, PayPalClient


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--oauth-only", action="store_true", help="test OAuth and report the required scope without querying transaction data")
    args = parser.parse_args(argv if argv is not None else sys.argv[1:])
    print(f"dotenv_loaded={settings.dotenv_loaded}")
    print(f"paypal_credentials_present={settings.paypal_configured}")
    print(f"application_data_source={settings.data_source}")
    if not settings.paypal_configured:
        print("oauth_authentication=not_attempted; configure credentials in project .env")
        return 2

    client = PayPalClient(
        settings.paypal_client_id,
        settings.paypal_client_secret,
        settings.paypal_base_url,
        timeout=12,
    )
    try:
        token = client._token()
    except PayPalAPIError as exc:
        print("oauth_authentication=failed")
        print(f"error={exc}")
        return 3
    else:
        del token
        print("oauth_authentication=success")
        print(f"transaction_search_scope_present={client.transaction_search_scope_present}")

    if args.oauth_only:
        return 0

    try:
        fetched = client.fetch_transactions()
    except PayPalAPIError as exc:
        print("transaction_retrieval=failed")
        print(f"error={exc}")
        return 4

    print("transaction_retrieval=success")
    print(f"valid_rows={len(fetched.transactions)}")
    print(f"reported_total_items={fetched.total_items_reported}")
    print(f"pages_read={fetched.pages_read}")
    print(f"malformed_rows_skipped={fetched.malformed_rows_skipped}")
    print("No transaction IDs, credentials, access tokens, or response bodies are displayed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
