# Architecture

Streamlit presents the merchant views; `payguard/` contains independent data generation, PayPal read access, deterministic assessment, analytics, AI explanation and SQLite investigation storage.

`transactions → rules and evidence → optional AI explanation → merchant review and saved decision`.

Risk scores are capped sums of rule contributions: repeated reference attempts in 15 minutes +35, amount above twice the observed 95th percentile (minimum threshold USD 500) +40, and five or more failures in a rolling one-hour window +25. Severity is Low (0–29), Medium (30–59), High (60–100). These are prioritization values, not calibrated fraud probabilities.

Demo records are reproducible and labelled Demo Data. PayPal is opt-in and uses Transaction Search, read-only, for a bounded recent period; its account history and data availability depend on merchant account/reporting access. The code does not infer cardholder or customer details that the endpoint omits. Refund event interpretation is deliberately not used as a rule.

AI sends only the selected structured finding to the configured OpenAI-compatible Chat Completions API. Without a key, with provider errors, or invalid output, the app uses a deterministic explanation. No payment action is taken.

SQLite is local-file storage. The Render free service filesystem is ephemeral and is not appropriate for durable shared investigation records.

