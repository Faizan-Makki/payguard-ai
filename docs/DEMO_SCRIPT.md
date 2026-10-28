# Three-minute demo narration

## 0:00–0:25 — Problem and source

“Small merchants need a clear way to prioritize unusual payment activity without treating a rules alert as proof of fraud. This demo uses labeled, reproducible synthetic records. Every KPI is derived from the current dataset.” Point out the Demo Data source label and payment totals.

## 0:25–1:05 — Evidence

In Overview, locate `DEMO-REPEAT-2`. Open Investigations and show the repeated-attempt rule, the three shared synthetic attempts, the score contribution, and the uncertainty statement. Explain that repeated attempts can have legitimate causes.

## 1:05–1:40 — AI explanation and merchant decision

If a provider key is configured, click **Ask AI to explain this finding** and identify it as an AI-generated explanation of the listed evidence. Otherwise show the deterministic fallback and state that no live AI provider is configured. Add a short investigation note, set the status to Reviewing, and save. No payment is cancelled or refunded.

## 1:40–2:15 — Search and analytics

Search `DEMO-REPEAT` in Transactions. Show payment status separately from risk priority. Open the transaction details, then show Analytics and the rule counts. If demonstrating multiple currencies, point out that totals remain separated by currency.

## 2:15–2:50 — PayPal and close

In Settings, explain that PayPal Sandbox credentials are optional for this local demo. Only show a successful Sandbox probe or transaction table if you have personally verified it against your account; a connection probe can succeed with zero rows and is distinct from loading historical transaction data. Close: “PayGuard helps a merchant investigate activity; it does not decide that a payment is fraud.”

Keep the recording below three minutes. Avoid presenting scores as fraud probabilities or claiming production prevention. Use only verified provider responses and do not show secrets, third-party marks, or copyrighted music without permission.

