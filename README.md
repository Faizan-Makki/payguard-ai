# PayGuard AI

PayGuard AI is a small-merchant payment investigation assistant. It groups deterministic payment risk signals with visible evidence, optionally explains that evidence with AI, and lets a merchant record a review. It supports synthetic demo data without credentials and an opt-in read-only PayPal Sandbox Transaction Search connection.

This is a decision-support prototype, not production-grade fraud prevention. A risk score is an investigation priority, not a probability. The app never cancels, blocks or refunds payments.

## Features

- Responsive Streamlit dashboard with data-derived payment KPIs, activity, status and risk views.
- Searchable transaction explorer with payment status and risk priority shown separately.
- Explainable repeated-attempt, unusual-amount and failed-payment-cluster rules.
- Optional OpenAI Chat Completions service with strict JSON Schema output and deterministic fallback.
- Local SQLite review status and notes.
- Read-only PayPal Sandbox Transaction Search client; no silently substituted demo records.

## Stack and layout

Python, Streamlit, Pandas, Plotly, Requests and SQLite. `app.py` is the UI. `payguard/` contains configuration, demo generation, analytics, rules, provider clients and investigation storage. `tests/` covers core behavior.

## Run locally

Requires Python 3.11+.

```bash
cd payguard-ai
python -m venv .venv
# Windows: .venv\Scripts\Activate.ps1
# macOS/Linux: source .venv/bin/activate
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

The default source is deterministic synthetic data. Run checks with `python -m pytest -q`.

## Configuration

The app loads `.env` from the `payguard-ai` project directory at startup. Copy `.env.example` to `.env`, then set your own credentials there or in the shell. The template contains blank credential placeholders. In PowerShell, run `Copy-Item .env.example .env`; on macOS or Linux, run `cp .env.example .env`.

Keep `PAYGUARD_DATA_SOURCE=demo` in `.env` for the synthetic demo. To verify PayPal without changing the app's source mode, run `python -m payguard.paypal_check`; it performs OAuth and a read-only transaction search, and prints aggregate counts only. To start the app locally, run `python -m streamlit run app.py`.

Keep secrets out of source control, screenshots, and logs. On Render, define them in service environment settings.

| Variable | Purpose |
| --- | --- |
| `PAYGUARD_DATA_SOURCE` | `demo` (default) or `paypal` |
| `PAYPAL_CLIENT_ID`, `PAYPAL_CLIENT_SECRET` | Sandbox REST app credentials |
| `PAYPAL_BASE_URL` | Defaults to PayPal Sandbox API URL above |
| `OPENAI_API_KEY` | Optional provider key for AI explanations |
| `OPENAI_MODEL` | Optional model name, default `gpt-4o-mini` |
| `OPENAI_BASE_URL` | API base URL, default `https://api.openai.com/v1` |
| `PAYGUARD_DB_PATH` | Local SQLite path, default `payguard.db` |

## PayPal Sandbox

Create a Sandbox REST app in the PayPal Developer Dashboard and place its client ID and secret in environment variables. Set `PAYGUARD_DATA_SOURCE=paypal`. The app uses OAuth 2.0 client credentials and the read-only Transaction Search endpoint for the recent seven-day period. Settings offers a separate reporting API connection probe; a successful probe means OAuth and an API call succeeded, even if zero transactions matched. The dashboard separately reports transaction retrieval and row count. It does not initiate or capture payments. A failed request produces an explicit error and no synthetic fallback.

PayPal documents history over the previous three years, a maximum requested period of 31 days, and up to a three-hour delay before executed transactions appear. The app reads all pages reported by the API (with a defensive 20-page limit, 2,000 rows at the default page size; exceeding it errors rather than silently truncating), requests only `transaction_info`, and asks for all record types. The default seven-day query still depends on transactions existing in the configured Sandbox account.

Official references: [PayPal REST requests and OAuth](https://developer.paypal.com/api/rest/requests/) and [Transaction Search endpoint and schema](https://developer.paypal.com/api/transaction-search/v1/search-get).

## AI explanations

Without `OPENAI_API_KEY`, the app provides a clearly labelled deterministic explanation. With a key, the merchant clicks **Ask AI to explain this finding**; only that structured finding is sent to the configured OpenAI Chat Completions endpoint. The response is validated; engine evidence and recommendations remain authoritative. PayPal credentials are never sent. Provider failure falls back to deterministic output. No live AI call has been verified in this workspace.

## Render deployment

1. Push this `payguard-ai` directory to a public Git repository (the hackathon requires a public repository and open-source license).
2. In Render, create a Web Service from the repository root `payguard-ai`.
3. Render reads `render.yaml`; build command installs `requirements.txt`, start command binds Streamlit to `$PORT`.
4. Set optional secrets in Render environment settings. Start with `PAYGUARD_DATA_SOURCE=demo`; switch to `paypal` only after Sandbox credentials are set.
5. Deploy and verify the service URL and source badge.

Render's ephemeral filesystem can lose SQLite investigations on restart or redeploy. Use a persistent disk or external storage before relying on history; neither is configured here.

## Limitations

- PayPal client behavior has mock coverage, but credentials and an actual Sandbox API response have not been exercised in this workspace. Availability depends on the Sandbox account's transaction history and reporting access. This is delayed historical reporting, not a streaming fraud feed.
- Refund semantics are not treated as a risk rule. Missing refund data is displayed as unavailable.
- The failure rule is a simple rolling count and does not claim calibrated rate anomaly detection.
- Demo customer/order identifiers are synthetic; no real personal information is used.
- SQLite does not provide multi-user authorization or durable storage on the Render free filesystem.
- No hackathon submission, public repo, hosted deployment or video is created by this code.

## Hackathon submission checklist

See [`docs/SUBMISSION_CHECKLIST.md`](docs/SUBMISSION_CHECKLIST.md). The repository includes an MIT License. Official deadline: Nov 12, 2026 at 12:00 PM Pacific.

## Demo walkthrough

See [`docs/DEMO_SCRIPT.md`](docs/DEMO_SCRIPT.md) for the three-minute flow and [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for scoring details.

