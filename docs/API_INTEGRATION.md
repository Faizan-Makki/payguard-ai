# PayPal API integration notes

Verified against PayPal developer documentation on 2026-10-27. The Transaction Search API documents `GET /v1/reporting/transactions` with OAuth 2.0 client-credentials and the Sandbox URL `https://api-m.sandbox.paypal.com`. The client requests `fields=transaction_info` and `balance_affecting_records_only=N`, maps only ID, initiation time, amount/currency, status and reference, validates page metadata, and retrieves all reported pages. Page size defaults to 100 (the API allows 1–500); a defensive 20-page ceiling (2,000 default-sized rows) raises an error instead of returning an apparently complete partial dataset.

PayPal documents that the API lists transactions from the previous three years, but any individual date range can span at most 31 days. Executed transactions may take up to three hours to appear. This app queries the previous seven days. A populated result therefore depends on real test transactions in the configured Sandbox account and its reporting access; no account history can be inferred from credentials alone.

The Settings connection probe independently verifies OAuth plus a one-hour reporting API query with page size one. A successful probe is distinct from loading dashboard data, and can return zero matching transactions. Dashboard status reports rows loaded and malformed rows skipped. This workspace has no Sandbox credentials, so a live response remains unverified. The UI surfaces sanitized errors and never swaps in demo data under a Sandbox label.

Hackathon rule check: the official rules require meaningful PayPal Sandbox integration and AI use, a functional demo, public source repository with an open-source license, and a public YouTube video under three minutes. The local deterministic fallback is not represented as provider-backed AI. Credentials and real responses remain to be supplied and tested. See [`SUBMISSION_CHECKLIST.md`](SUBMISSION_CHECKLIST.md).

