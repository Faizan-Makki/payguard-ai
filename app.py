import pandas as pd
import plotly.express as px
import secrets
import streamlit as st
from payguard.ai_service import explain_finding
from payguard.analytics import summarize
from payguard.config import settings
from payguard.checkout_service import (
    CheckoutError, PayPalCheckoutStore, SANDBOX_TEST_AMOUNT,
    assess_sandbox_capture, create_sandbox_order, process_cancellation,
    verify_and_capture,
)
from payguard.demo_data import make_demo_transactions
from payguard.investigation_service import InvestigationStore
from payguard.paypal_client import PayPalClient
from payguard.risk_engine import assess_transactions

st.set_page_config(page_title="PayGuard AI", page_icon="◈", layout="wide", initial_sidebar_state="expanded")
st.markdown("""<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Manrope:wght@500;600;700;800&display=swap');
:root{--ink:#e9eff8;--muted:#94a3b8;--panel:#121d2b;--line:#253447;--blue:#5b9cff;--teal:#51d6bd}
html,body,[class*="css"]{font-family:'DM Sans',sans-serif} .stApp{background:#0b1320;color:var(--ink)}
.block-container{max-width:1420px;padding-top:1.5rem}.hero{padding:24px 0 12px}.eyebrow{color:#6fa9ff;text-transform:uppercase;letter-spacing:.15em;font-size:11px;font-weight:700}.hero h1{font-family:Manrope,sans-serif;font-size:34px;margin:3px 0;color:#f4f7fb}.hero p{color:#9baec4}.metric-card{background:#121d2b;border:1px solid #253447;border-radius:12px;padding:18px 20px;height:108px}.metric-label{color:#93a5bb;font-size:12px}.metric-value{font-family:Manrope,sans-serif;color:#f4f7fb;font-size:26px;font-weight:700;margin-top:7px}.metric-note{color:#51d6bd;font-size:11px;margin-top:2px}.section{font-family:Manrope,sans-serif;font-weight:700;color:#edf3fb;font-size:18px;margin:18px 0 8px}.tag{border-radius:20px;padding:4px 10px;background:#17283b;color:#a9cfff;font-size:12px}.stTabs [data-baseweb="tab-list"]{gap:8px}.stTabs [data-baseweb="tab"]{background:#121d2b;border-radius:8px 8px 0 0}
div[data-testid="stDataFrame"]{border:1px solid #253447;border-radius:10px} .stButton button[kind="primary"]{background:#316ee8;border:0}
</style>""", unsafe_allow_html=True)

@st.cache_data(ttl=90)
def demo_data(): return make_demo_transactions()

@st.cache_data(ttl=120)
def paypal_data(client_id, client_secret, base_url):
    result = PayPalClient(client_id, client_secret, base_url).fetch_transactions()
    return {"transactions": result.transactions, "pages_read": result.pages_read, "total_items_reported": result.total_items_reported, "malformed_rows_skipped": result.malformed_rows_skipped, "start": result.start, "end": result.end}

store = InvestigationStore(settings.db_path)
source = "Demo Data" if settings.data_source != "paypal" else "PayPal Sandbox"
source_status = "Synthetic sample dataset loaded" if settings.data_source != "paypal" else "Not connected"
if settings.data_source == "paypal" and settings.paypal_configured:
    try:
        paypal_result = paypal_data(settings.paypal_client_id, settings.paypal_client_secret, settings.paypal_base_url)
        transactions = pd.DataFrame(paypal_result["transactions"])
        source_status = f"Transaction Search succeeded · {len(transactions)} valid rows · {paypal_result['pages_read']} pages"
        if paypal_result["malformed_rows_skipped"]:
            source_status += f" · {paypal_result['malformed_rows_skipped']} malformed rows skipped"
    except Exception as exc:
        source_status = f"Transaction Search failed · {type(exc).__name__}"
        st.error(f"{source_status}. Check Sandbox credentials, reporting access, date range and API availability. Demo data was not substituted.")
        transactions = pd.DataFrame(columns=make_demo_transactions().columns)
elif settings.data_source == "paypal":
    source_status = "Credentials not configured · no data loaded"
    st.warning("PayPal Sandbox is selected, but credentials are not configured. No synthetic data is being shown as PayPal data.")
    transactions = pd.DataFrame(columns=make_demo_transactions().columns)
else:
    transactions = demo_data()

risk = assess_transactions(transactions)
metrics = summarize(transactions)
reviews = store.list_all()
open_count = sum(1 for transaction_key in risk.transaction_key if reviews.get(transaction_key, {}).get("status", "Open") != "Resolved") if not risk.empty else 0
high_count = int((risk.severity == "High").sum()) if not risk.empty else 0

with st.sidebar:
    st.markdown("### ◈ PayGuard AI")
    st.caption("Merchant risk investigation")
    st.markdown(f"**Data source**  \n`{source}`")
    st.caption(source_status)
    st.markdown("---")
    st.caption("Scores prioritize review. They are not fraud probabilities or automatic decisions.")

st.markdown(f'<div class="hero"><div class="eyebrow">PAYMENT INTELLIGENCE / {source.upper()}</div><h1>Merchant overview</h1><p>Make unusual payment activity easier to investigate, with evidence you can inspect.</p></div>', unsafe_allow_html=True)
def metric(label, value, note=""):
    st.markdown(f'<div class="metric-card"><div class="metric-label">{label}</div><div class="metric-value">{value}</div><div class="metric-note">{note}</div></div>', unsafe_allow_html=True)

def currency_breakdown(values):
    return " · ".join(f"{code} {amount:,.2f}" for code, amount in values.items()) or "No amounts"

if not metrics["volume_by_currency"]:
    volume_display, volume_note = "Unavailable", "No transaction amounts loaded"
elif metrics["volume"] is None:
    volume_display, volume_note = "Multi-currency", currency_breakdown(metrics["volume_by_currency"])
else:
    only_currency = next(iter(metrics["volume_by_currency"]))
    volume_display, volume_note = f"{only_currency} {metrics['volume']:,.2f}", "Loaded dataset total"

cols = st.columns(6)
with cols[0]: metric("TRANSACTIONS", f"{metrics['count']:,}", source)
with cols[1]: metric("PAYMENT VOLUME", volume_display, volume_note)
with cols[2]: metric("SUCCESSFUL", f"{metrics['success_count']:,}", currency_breakdown(metrics["success_amount_by_currency"]))
with cols[3]: metric("FAILED", f"{metrics['failed_count']:,}", "Payment status")
with cols[4]: metric("REFUNDED", f"{metrics['refund_count']:,}" if metrics["refund_available"] else "Unavailable", currency_breakdown(metrics["refund_amount_by_currency"]) if metrics["refund_available"] else "Not provided by source")
with cols[5]: metric("OPEN REVIEWS", f"{open_count:,}", f"{high_count} high-priority findings")

if transactions.empty:
    st.info("No transaction data is available for the selected source. Configure PayPal Sandbox or switch PAYGUARD_DATA_SOURCE to demo.")
else:
    left, right = st.columns([1.6, 1])
    with left:
        st.markdown('<div class="section">Payment activity</div>', unsafe_allow_html=True)
        chart_data = transactions.copy(); chart_data["timestamp"] = pd.to_datetime(chart_data.timestamp, utc=True, errors="coerce")
        chart_data["amount"] = pd.to_numeric(chart_data.amount, errors="coerce")
        chart_data = chart_data.dropna(subset=["timestamp", "amount"]).set_index("timestamp").groupby("currency").resample("D").amount.sum().reset_index()
        st.plotly_chart(px.area(chart_data, x="timestamp", y="amount", color="currency", template="plotly_dark", color_discrete_sequence=["#5b9cff", "#51d6bd", "#e8b768", "#ff7585"], labels={"timestamp":"Date", "amount":"Volume (native currency)"}).update_layout(paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,0)",margin=dict(l=0,r=0,t=8,b=0),height=290), width="stretch")
    with right:
        st.markdown('<div class="section">Payment status</div>', unsafe_allow_html=True)
        st.plotly_chart(px.pie(transactions, names="status", hole=.68, template="plotly_dark", color_discrete_sequence=["#51d6bd", "#ff7585", "#e8b768", "#6e8cae"]).update_layout(paper_bgcolor="rgba(0,0,0,0)",margin=dict(l=0,r=0,t=8,b=0),height=290,showlegend=True), width="stretch")

tab_overview, tab_transactions, tab_investigate, tab_analytics, tab_settings = st.tabs(["Overview", "Transactions", "Investigations", "Analytics", "Settings"])
with tab_overview:
    a, b = st.columns([1.5, 1])
    with a:
        st.markdown('<div class="section">Recent flagged activity</div>', unsafe_allow_html=True)
        if risk.empty: st.success("No records meet the current deterministic investigation rules.")
        else:
            view = risk.merge(transactions[["transaction_id", "transaction_key", "amount", "currency", "status", "timestamp", "event_code"]], on="transaction_key", how="left", suffixes=("_finding", "_transaction")).sort_values("score", ascending=False).head(8)
            st.dataframe(view[["transaction_id_transaction", "timestamp", "event_code", "score", "severity", "rules", "amount", "currency", "status"]], width="stretch", hide_index=True)
    with b:
        st.markdown('<div class="section">Risk priority</div>', unsafe_allow_html=True)
        if risk.empty: st.caption("Risk findings will appear when a rule has evidence to report.")
        else: st.plotly_chart(px.histogram(risk, x="severity", color="severity", category_orders={"severity":["High","Medium","Low"]}, template="plotly_dark", color_discrete_map={"High":"#ff7585","Medium":"#e8b768","Low":"#51d6bd"}).update_layout(paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,0)",showlegend=False,margin=dict(l=0,r=0,t=8,b=0)),width="stretch")

with tab_transactions:
    st.markdown('<div class="section">Transaction explorer</div>', unsafe_allow_html=True)
    query = st.text_input("Search transaction, customer reference, or order reference", key="search_tx")
    f1, f2, f3 = st.columns(3)
    statuses = sorted(transactions.status.dropna().astype(str).unique()) if not transactions.empty else []
    selected_status = f1.multiselect("Payment status", statuses, default=statuses)
    risk_levels = ["High", "Medium", "Low", "No finding"]
    selected_risk = f2.multiselect("Risk priority", risk_levels, default=risk_levels)
    listing = transactions.copy()
    if not listing.empty:
        listing["timestamp"] = pd.to_datetime(listing.timestamp, utc=True, errors="coerce")
        flags = risk.set_index("transaction_key").severity.to_dict() if not risk.empty else {}
        listing["risk_level"] = listing.transaction_key.map(flags).fillna("No finding")
        if not listing.timestamp.dropna().empty:
            first_day = listing.timestamp.min().date()
            last_day = listing.timestamp.max().date()
            selected_dates = f3.date_input("Date range", value=(first_day, last_day), min_value=first_day, max_value=last_day, key="tx_date_range")
            if isinstance(selected_dates, tuple) and len(selected_dates) == 2:
                listing = listing[listing.timestamp.dt.date.between(selected_dates[0], selected_dates[1])]
        if query:
            listing = listing[listing.astype(str).apply(lambda col: col.str.contains(query, case=False, na=False)).any(axis=1)]
        listing = listing[listing.status.astype(str).isin(selected_status) & listing.risk_level.isin(selected_risk)]
        if listing.empty:
            st.info("No transactions match the selected search, status, risk, and date filters.")
        else:
            st.dataframe(listing.sort_values("timestamp", ascending=False), width="stretch", hide_index=True)
            chosen = st.selectbox("Inspect transaction", listing.transaction_id.tolist())
            st.json(listing.loc[listing.transaction_id.eq(chosen)].iloc[0].to_dict(), expanded=False)
            selected_key = listing.loc[listing.transaction_id.eq(chosen), "transaction_key"].iloc[0]
            found = risk.loc[risk.transaction_key.eq(selected_key)]
            if not found.empty:
                st.caption("Rule-based risk finding")
                st.write(found.iloc[0].explanation)
    else: st.info("No transactions available.")

with tab_investigate:
    st.markdown('<div class="section">Investigation queue</div>', unsafe_allow_html=True)
    st.caption("Investigation notes and status are stored in local SQLite. On Render free instances, local files may be ephemeral.")
    st.session_state.setdefault("ai_explanations", {})
    if risk.empty: st.info("No findings to review.")
    else:
        for _, finding in risk.sort_values("score", ascending=False).iterrows():
            review_key = finding.transaction_key
            prior = reviews.get(review_key, {})
            with st.expander(f"{finding.severity} · {finding.transaction_id} · priority {finding.score}/100", expanded=False):
                st.write(finding.explanation)
                st.write("Evidence", finding.evidence)
                st.write("Triggered rules", ", ".join(finding.rules))
                explanation_key = str(review_key)
                result = st.session_state.ai_explanations.get(explanation_key)
                if result is None:
                    result = explain_finding(finding.to_dict())
                if settings.GEMINI_API_KEY and st.button("Ask AI to explain this finding", key=f"ai-{explanation_key}"):
                    result = explain_finding(finding.to_dict(), settings.GEMINI_API_KEY, settings.GEMINI_MODEL)
                    st.session_state.ai_explanations[explanation_key] = result
                elif not settings.GEMINI_API_KEY:
                    st.caption("AI provider not configured. Showing the deterministic rules-based explanation.")
                st.caption(f"Explanation source: {result['provider']}")
                st.write(result["why_flagged"])
                if "evidence_summary" in result: st.write("AI evidence summary:", result["evidence_summary"])
                st.write("Uncertainty:", result["uncertainty"])
                st.write("Suggested review steps:", result.get("next_steps", []))
                status = st.selectbox("Review status", ["Open", "Reviewing", "Resolved"], index=["Open", "Reviewing", "Resolved"].index(prior.get("status", "Open")), key=f"status-{review_key}")
                note = st.text_area("Investigation note", value=prior.get("note", ""), key=f"note-{review_key}")
                if st.button("Save review", key=f"save-{review_key}"):
                    store.save(review_key, status, note); st.success("Review saved locally.")
                st.caption("No payment action is taken by PayGuard AI.")

with tab_analytics:
    st.markdown('<div class="section">Activity analysis</div>', unsafe_allow_html=True)
    if not transactions.empty:
        analytic = transactions.copy(); analytic["timestamp"] = pd.to_datetime(analytic.timestamp, utc=True, errors="coerce")
        period = st.selectbox("Period", ["All available data", "Last 7 days", "Last 30 days"])
        if period != "All available data": analytic = analytic[analytic.timestamp >= pd.Timestamp.now(tz="UTC") - pd.Timedelta(days=7 if period == "Last 7 days" else 30)]
        c1, c2 = st.columns(2)
        with c1: st.plotly_chart(px.histogram(analytic, x="amount", color="currency", facet_col="currency", nbins=24, template="plotly_dark", title="Transaction amount distribution by currency").update_layout(paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,0)"), width="stretch")
        with c2:
            rule_rows = [{"rule": rule, "findings": int(risk.rules.map(lambda rules: rule in rules).sum())} for rule in sorted({r for rules in risk.rules for r in rules})] if not risk.empty else []
            if rule_rows: st.plotly_chart(px.bar(pd.DataFrame(rule_rows), x="rule", y="findings", template="plotly_dark", title="Findings by rule", color_discrete_sequence=["#51d6bd"]).update_layout(paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,0)"), width="stretch")
            else: st.info("No rule findings in this dataset.")
        status = analytic.status.astype(str).str.upper()
        st.metric("Payment success rate", f"{(status.isin(['COMPLETED','SUCCESS','S']).mean()*100):.1f}%" if len(analytic) else "Unavailable")
        if "refund_amount" in analytic and pd.to_numeric(analytic.refund_amount, errors="coerce").notna().any():
            refund_data = analytic.copy()
            refund_data["refund_amount"] = pd.to_numeric(refund_data.refund_amount, errors="coerce").fillna(0)
            refund_totals = refund_data.groupby("currency").refund_amount.sum().to_dict()
            st.metric("Recorded refunds", currency_breakdown(refund_totals))
        else: st.caption("Refund analysis unavailable: source did not provide refund amounts.")
    else: st.info("No data to analyze.")

with tab_settings:
    st.markdown('<div class="section">Connections & configuration</div>', unsafe_allow_html=True)
    st.write(f"**Data source:** {source}")
    st.write(f"**Local .env:** {'Loaded' if settings.dotenv_loaded else 'Not found'} — environment variable values are never displayed.")
    st.write(f"**PayPal Sandbox credentials:** {'Configured' if settings.paypal_configured else 'Not configured'} — this indicates presence only, not a successful API connection.")
    if settings.data_source == "paypal" and settings.paypal_configured:
        if st.button("Test PayPal reporting connection"):
            try:
                st.session_state.paypal_probe = PayPalClient(settings.paypal_client_id, settings.paypal_client_secret, settings.paypal_base_url).test_connection()
            except Exception as exc:
                st.session_state.paypal_probe = {"connected": False, "error": type(exc).__name__}
        probe = st.session_state.get("paypal_probe")
        if probe and probe.get("connected"):
            st.success(f"OAuth and Transaction Search API call succeeded. Probe reported {probe['total_items_reported']} matching transactions in a one-hour window.")
            st.caption("A connection test can succeed with zero transactions; this is separate from the dashboard retrieval result above.")
        elif probe:
            st.error(f"Connection test failed ({probe.get('error', 'unknown error')}). No transaction rows were invented.")
    elif settings.data_source == "paypal":
        st.info("Select PayPal Sandbox and set server-side credentials before testing the reporting API.")
    st.write(f"**Gemini API key:** {'Configured; a request is made only when you click the explanation button' if settings.GEMINI_API_KEY else 'Not configured; deterministic fallback is active'} — key remains server-side.")
    st.write("**Storage:** Local SQLite file; suitable for a demo, not shared multi-user production storage.")
    st.markdown("Set environment variables before starting Streamlit or in Render settings. The project loads its own `.env` file at startup. Never paste credentials into this page.")
    st.code("PAYGUARD_DATA_SOURCE=demo\nPAYPAL_CLIENT_ID=...\nPAYPAL_CLIENT_SECRET=...\nPAYPAL_BASE_URL=https://api-m.sandbox.paypal.com\nPAYPAL_RETURN_URL=http://localhost:8501/\nPAYPAL_CANCEL_URL=http://localhost:8501/\nGEMINI_API_KEY=...\nGEMINI_MODEL=gemini-3.8-flash", language="bash")

    st.markdown('<div class="section">PayPal Sandbox checkout test</div>', unsafe_allow_html=True)
    st.caption("Creates a fixed USD test order through the Sandbox API. Use a Sandbox Personal buyer. Approval alone does not mark the payment complete; PayGuard verifies and captures server-side after you request verification.")
    if not settings.paypal_configured:
        st.info("Configure Sandbox REST credentials in the server environment to use checkout. Demo mode remains available without them.")
    else:
        checkout_store = PayPalCheckoutStore(settings.db_path)
        checkout_client = PayPalClient(settings.paypal_client_id, settings.paypal_client_secret, settings.paypal_base_url)
        st.info(f"Fixed test amount: USD {SANDBOX_TEST_AMOUNT} · Source: PayPal Sandbox · Stored locally in SQLite")
        if "pg_checkout_state" not in st.session_state:
            st.session_state.pg_checkout_state = None
        query = st.query_params
        callback_event = query.get("pg_checkout")
        callback_state = query.get("pg_state")
        callback_order = query.get("token")
        if callback_event in {"return", "cancel"} and callback_state and callback_order:
            try:
                if callback_event == "cancel":
                    cancelled = process_cancellation(checkout_client, checkout_store, callback_order, callback_state)
                    st.session_state.pg_checkout_state = callback_state
                    if cancelled["status"] == "PAID":
                        st.success("PayPal confirms this Sandbox order was already completed. The verified capture is recorded below.")
                    else:
                        st.info("PayPal returned you from the approval flow. This order has not been captured.")
                else:
                    returned_attempt = checkout_store.get_attempt(callback_state)
                    if not returned_attempt or returned_attempt.get("order_id") != callback_order:
                        raise CheckoutError("PayPal return did not match the order stored for this checkout")
                    st.session_state.pg_checkout_state = callback_state
                    st.info("Return received. PayGuard will verify this order with PayPal before offering server-side capture.")
            except Exception as exc:
                st.error(f"Could not validate the PayPal return ({type(exc).__name__}). Start a new Sandbox checkout if needed.")
            finally:
                # Remove callback parameters so refreshes do not repeat callback handling.
                st.query_params.clear()
        if st.button("Create USD 1.00 Sandbox checkout", type="primary", key="pg-create-checkout"):
            state = secrets.token_urlsafe(32)
            try:
                checkout_store.create_attempt(state)
                attempt = create_sandbox_order(checkout_client, checkout_store, state, settings.paypal_return_url, settings.paypal_cancel_url)
                st.session_state.pg_checkout_state = state
                st.success("Sandbox order created. Open the approval link and complete the buyer step using your Sandbox Personal account.")
            except Exception as exc:
                st.error(f"Sandbox order creation failed ({type(exc).__name__}). No synthetic data was substituted.")
        checkout_state = st.session_state.get("pg_checkout_state")
        attempt = checkout_store.get_attempt(checkout_state) if checkout_state else None
        if attempt:
            st.caption(f"Checkout state: {attempt['status']} · Order ID: {attempt['order_id'] or 'not created'}")
            if attempt.get("approval_url") and attempt["status"] == "AWAITING_APPROVAL":
                st.link_button("Open PayPal Sandbox approval", attempt["approval_url"])
                st.caption("Sign in with your Sandbox Personal buyer, approve the USD 1.00 payment, then return to this app.")
                if st.button("Verify with PayPal and capture", key="pg-verify-capture"):
                    try:
                        attempt = verify_and_capture(checkout_client, checkout_store, attempt["order_id"], checkout_state)
                        if attempt["status"] == "PAID":
                            st.success("PayPal confirmed a completed Sandbox capture.")
                        else:
                            st.warning("PayPal has not confirmed buyer approval yet. Complete approval, then verify again.")
                    except Exception as exc:
                        st.error(f"Verification/capture did not complete ({type(exc).__name__}). The app has not marked this payment paid.")
            if attempt["status"] == "PAID" and attempt.get("transaction"):
                txn = attempt["transaction"]
                st.write({"Source": txn["source"], "Capture ID": txn["transaction_id"], "Amount": f"{txn['currency']} {txn['amount']:.2f}", "PayPal status": txn["status"], "Timestamp": txn["timestamp"] or "Not supplied"})
                st.caption("This verified Sandbox capture is assessed on its own and is not added to synthetic demo metrics or transactions.")
                sandbox_risk = assess_sandbox_capture(txn)
                if sandbox_risk.empty:
                    st.info("No risk rule was triggered by this single capture. A single payment is not evidence of fraud.")
                else:
                    finding = sandbox_risk.iloc[0]
                    st.write(f"Investigation priority: {finding.severity} · {finding.score}/100")
                    st.write("Evidence:", finding.evidence)
                    st.write(finding.explanation)
