# Architecture

Streamlit presents the merchant views; `payguard/` contains independent data generation, PayPal read access, deterministic assessment, analytics, AI explanation and SQLite investigation storage.

`transactions → rules and evidence → optional AI explanation → merchant review and saved decision`.

Risk scores are capped sums of rule contributions: repeated reference attempts in 15 minutes +35, amount above twice the observed 95th percentile (minimum threshold USD 500) +40, and five or more failures in a rolling one-hour window +25. Severity is Low (0–29), Medium (30–59), High (60–100). These are prioritization values, not calibrated fraud probabilities.

Demo records are reproducible and labelled Demo Data. PayPal is opt-in and uses Transaction Search, read-only, for a bounded recent period; its account history and data availability depend on merchant account/reporting access. The code does not infer cardholder or customer details that the endpoint omits. Refund event interpretation is deliberately not used as a rule.

AI sends only the selected structured finding to Google's Gemini `generateContent` API. The request asks for schema-constrained JSON, and the app validates the response. Engine evidence and investigation steps remain authoritative. Without a key, with provider errors, or invalid output, the app uses a deterministic explanation. No payment action is taken.

SQLite is local-file storage. The Render free service filesystem is ephemeral and is not appropriate for durable shared investigation records.

# Sandbox checkout workflow

The optional Settings workflow is separate from dashboard data loading. `PayPalClient` owns OAuth and Orders API HTTP calls. `checkout_service` binds a random browser state nonce to one SQLite order, verifies callbacks against the stored order, claims capture atomically, and maps only verified capture fields into the existing transaction schema. A capture is marked paid only after PayPal confirms a completed order and matching completed capture. The risk engine receives a single isolated PayPal Sandbox row; its payer reference is intentionally `None`. The UI never merges that row into demo KPIs.

The SQLite callback state assumes one app instance and durable local storage for the lifetime of the 30-minute order. Streamlit callbacks cannot safely depend on browser session state alone because PayPal can open a separate browser context. Render's free ephemeral disk and multi-instance deployments can lose or split checkout state, so this implementation is for local/demo use only.

