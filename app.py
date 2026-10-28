import pandas as pd
import plotly.express as px
import streamlit as st
from payguard.ai_service import explain_finding
from payguard.analytics import summarize
from payguard.config import settings
from payguard.demo_data import make_demo_transactions
from payguard.investigation_service import InvestigationStore
from payguard.paypal_client import PayPalClient
from payguard.risk_engine import assess_transactions

st.set_page_config(page_title="PayGuard AI", page_icon="◈", layout="wide", initial_sidebar_state="expanded")
NAV_SECTIONS = ["Overview", "Transactions", "Investigations", "Analytics", "Settings"]
FLAGGED_TABLE_COLUMNS = [
    "transaction_id_transaction", "timestamp", "event_code", "score", "severity", "rules", "amount", "currency", "status",
]
st.session_state.setdefault("flagged_table_revision", 0)
st.session_state.setdefault("active_section_main", "Overview")

def _flagged_columns_changed():
    st.session_state.flagged_table_revision += 1

def _restore_flagged_columns():
    for column in FLAGGED_TABLE_COLUMNS:
        st.session_state[f"flagged_column_{column}"] = True
    st.session_state.flagged_table_revision += 1

st.markdown("""<style>
@import url(https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Manrope:wght@500;600;700;800&display=swap);
html,body,[class*="css"]{font-family:DM Sans,sans-serif}
[data-testid="stAppViewContainer"],.stApp{background:radial-gradient(ellipse at 10% 0%,color-mix(in srgb,var(--pg-accent, #38aaff) 7%,var(--background-color)),transparent 36rem),var(--background-color)}
[data-testid="stHeader"]{background:transparent}
.block-container{max-width:1440px;padding:2rem 2.5rem 3rem}
section[data-testid="stSidebar"]{background:var(--secondary-background-color);border-right:1px solid color-mix(in srgb,var(--text-color) 20%,var(--background-color))}
[data-testid="stSidebar"] [data-testid="stCaptionContainer"]{opacity:.78}
[data-testid="stSidebar"] [data-testid="stRadio"] [role="radiogroup"]{gap:.35rem}
[data-testid="stSidebar"] [data-testid="stRadio"] [role="radio"]{padding:.45rem .65rem;border:1px solid color-mix(in srgb,var(--text-color) 20%,var(--background-color));border-radius:9px;background:var(--secondary-background-color);transition:all .15s ease}
[data-testid="stSidebar"] [data-testid="stRadio"] [role="radio"][aria-checked="true"]{border-color:var(--primary-color);background:color-mix(in srgb,var(--secondary-background-color) 88%,var(--primary-color) 12%)}
.hero{padding:22px 0 20px}.eyebrow{color:var(--primary-color);text-transform:uppercase;letter-spacing:.16em;font-size:11px;font-weight:700}
.hero h1{font-family:Manrope,sans-serif;font-size:clamp(30px,3vw,38px);letter-spacing:-.035em;margin:5px 0}.hero p{opacity:.78;font-size:15px;margin:0}
.metric-card{position:relative;box-sizing:border-box;width:100%;min-width:0;min-height:122px;height:auto;display:flex;flex-direction:column;background:linear-gradient(145deg,color-mix(in srgb,var(--secondary-background-color) 88%,var(--primary-color) 12%),var(--secondary-background-color));border:1px solid rgba(148,163,184,.4);border-color:color-mix(in srgb,var(--primary-color) 42%,var(--secondary-background-color));border-radius:15px;padding:18px 20px;box-shadow:0 0 0 1px color-mix(in srgb,var(--primary-color) 10%,transparent),0 12px 30px rgba(0,0,0,.16);transition:transform .18s ease,border-color .18s ease,box-shadow .18s ease;overflow:visible}
.metric-card::after{content:"";position:absolute;top:0;left:22px;right:22px;height:1px;background:linear-gradient(90deg,transparent,color-mix(in srgb,var(--primary-color) 68%,transparent),transparent);pointer-events:none}
.metric-card:hover{transform:translateY(-3px);border-color:var(--primary-color);box-shadow:0 0 0 1px color-mix(in srgb,var(--primary-color) 22%,transparent),0 18px 36px rgba(0,0,0,.2)}
div[data-testid="stHorizontalBlock"]:has(.metric-card){align-items:stretch}div[data-testid="stHorizontalBlock"]:has(.metric-card)>div[data-testid="stColumn"]{display:flex;flex-direction:column}div[data-testid="stHorizontalBlock"]:has(.metric-card)>div[data-testid="stColumn"]>div{display:flex;flex:1}.metric-card{min-height:138px}.metric-label{opacity:.72;font-size:11px;letter-spacing:.075em;font-weight:700}.metric-value{font-family:Manrope,sans-serif;font-size:clamp(16px,1.25vw,22px);line-height:1.2;font-weight:700;margin-top:10px;overflow-wrap:anywhere;word-break:normal}.metric-note{font-size:11px;line-height:1.4;margin-top:6px;overflow-wrap:anywhere;word-break:normal;opacity:.88}
.section{font-family:Manrope,sans-serif;font-weight:700;font-size:18px;margin:22px 0 10px;letter-spacing:-.02em}.tag{border-radius:20px;padding:4px 10px;background:var(--secondary-background-color);font-size:12px}.section-center{text-align:center}
.priority-count{box-sizing:border-box;width:100%;display:flex;flex-direction:column;align-items:center;text-align:center;padding:8px 0 16px}.priority-count-label{font-size:14px;font-weight:600;opacity:.82}.priority-count-value{font-family:Manrope,sans-serif;font-size:32px;line-height:1.1;font-weight:700;margin-top:8px}
:root{--pg-accent:color-mix(in srgb,var(--primary-color) 42%,#38aaff);--pg-accent-soft:color-mix(in srgb,var(--pg-accent) 13%,var(--secondary-background-color))}
.metric-card{border-color:color-mix(in srgb,var(--pg-accent) 46%,var(--secondary-background-color));box-shadow:0 0 0 1px color-mix(in srgb,var(--pg-accent) 11%,transparent),0 12px 30px rgba(0,0,0,.12)}.metric-card::after{background:linear-gradient(90deg,transparent,color-mix(in srgb,var(--pg-accent) 72%,transparent),transparent)}.metric-card:hover{border-color:var(--pg-accent);box-shadow:0 0 0 1px color-mix(in srgb,var(--pg-accent) 22%,transparent),0 18px 36px rgba(0,0,0,.16)}
.eyebrow{color:var(--pg-accent)}[data-testid="stSegmentedControl"]{margin:0 0 1rem}[data-testid="stSegmentedControl"] button{border-color:color-mix(in srgb,var(--text-color) 20%,var(--background-color));transition:background-color .16s ease,border-color .16s ease}[data-testid="stSegmentedControl"] button[aria-pressed="true"]{background:var(--pg-accent-soft);border-color:color-mix(in srgb,var(--pg-accent) 68%,var(--secondary-background-color));color:var(--text-color)}
.stButton button:hover{border-color:var(--pg-accent);box-shadow:0 0 0 1px color-mix(in srgb,var(--pg-accent) 16%,transparent)}
[data-testid="stSidebar"]{box-shadow:inset -1px 0 0 color-mix(in srgb,var(--pg-accent) 8%,transparent)}
.metric-card{background:linear-gradient(145deg,color-mix(in srgb,var(--secondary-background-color) 82%,var(--pg-accent) 18%),var(--secondary-background-color) 68%);box-shadow:inset 0 1px 0 color-mix(in srgb,var(--text-color) 7%,transparent),0 14px 30px rgba(0,0,0,.12)}
.st-key-flagged-table-shell{box-sizing:border-box;padding:6px 8px 8px;border:1px solid color-mix(in srgb,var(--pg-accent) 26%,var(--text-color) 12%);border-radius:14px;background:linear-gradient(145deg,color-mix(in srgb,var(--secondary-background-color) 94%,var(--pg-accent) 6%),var(--secondary-background-color));box-shadow:inset 0 1px 0 color-mix(in srgb,var(--text-color) 8%,transparent),0 12px 28px rgba(0,0,0,.10)}
.st-key-flagged-table-shell [data-testid="stPopover"] button{min-height:34px;border:1px solid color-mix(in srgb,var(--pg-accent) 30%,var(--text-color) 14%);background:var(--secondary-background-color);box-shadow:0 3px 8px rgba(0,0,0,.10)}
.st-key-flagged-table-shell [data-testid="stDataFrame"]{border:1px solid color-mix(in srgb,var(--text-color) 13%,var(--background-color));border-radius:10px;overflow:hidden;box-shadow:0 5px 15px rgba(0,0,0,.08)}
div[data-testid="stDataFrame"]{border:1px solid color-mix(in srgb,var(--text-color) 20%,var(--background-color));border-radius:12px;overflow:hidden}
[data-testid="stExpander"]{background:var(--secondary-background-color);border:1px solid color-mix(in srgb,var(--text-color) 20%,var(--background-color));border-radius:12px}
[data-testid="stAlert"]{background:var(--secondary-background-color);border-color:color-mix(in srgb,var(--text-color) 20%,var(--background-color))}
[data-baseweb="input"]>div,[data-baseweb="select"]>div,textarea,[data-testid="stDateInput"] input{background:var(--secondary-background-color);border-color:color-mix(in srgb,var(--text-color) 20%,var(--background-color))}
[data-baseweb="popover"] ul,[data-baseweb="menu"]{background:var(--secondary-background-color)}
button,textarea,input,[data-baseweb="select"]{border-radius:9px!important}
.stButton button{border:1px solid color-mix(in srgb,var(--text-color) 20%,var(--background-color));background:var(--secondary-background-color);border-radius:9px;transition:all .15s ease}.stButton button:hover{border-color:var(--primary-color)}
.stButton button[kind="primary"]{background:var(--primary-color);border-color:var(--primary-color);color:#fff}.stButton button[kind="primary"]:hover{filter:brightness(1.08)}
/* Theme-aware finish: visual treatment only; Streamlit retains all widget behavior and placement. */
[data-testid="stAppViewContainer"],.stApp{background-image:radial-gradient(ellipse at 12% 0%,color-mix(in srgb,var(--pg-accent) 7%,transparent),transparent 38rem),linear-gradient(180deg,color-mix(in srgb,var(--secondary-background-color) 20%,transparent),transparent 26rem)}
section[data-testid="stSidebar"]{background:linear-gradient(165deg,color-mix(in srgb,var(--secondary-background-color) 88%,var(--pg-accent) 12%),var(--secondary-background-color) 58%);box-shadow:inset -1px 0 0 color-mix(in srgb,var(--pg-accent) 12%,transparent)}
.hero h1{ text-shadow:0 2px 18px color-mix(in srgb,var(--pg-accent) 13%,transparent)}
.section{ text-shadow:0 1px 12px color-mix(in srgb,var(--pg-accent) 9%,transparent)}
.metric-card{backdrop-filter:blur(12px);-webkit-backdrop-filter:blur(12px);box-shadow:inset 0 1px 0 color-mix(in srgb,var(--text-color) 9%,transparent),inset 0 -1px 0 color-mix(in srgb,var(--pg-accent) 10%,transparent),0 16px 34px rgba(0,0,0,.14)}
.priority-count-label{color:var(--text-color)}.priority-count-value{text-shadow:0 2px 16px color-mix(in srgb,var(--pg-accent) 18%,transparent)}
div[data-testid="stPlotlyChart"]{box-sizing:border-box;border:1px solid color-mix(in srgb,var(--pg-accent) 20%,var(--text-color) 10%);border-radius:15px;background:linear-gradient(145deg,color-mix(in srgb,var(--secondary-background-color) 94%,var(--pg-accent) 6%),color-mix(in srgb,var(--background-color) 92%,transparent));box-shadow:inset 0 1px 0 color-mix(in srgb,var(--text-color) 7%,transparent),0 10px 25px rgba(0,0,0,.09)}
div[data-testid="stDataFrame"]{box-shadow:inset 0 1px 0 color-mix(in srgb,var(--text-color) 6%,transparent),0 10px 24px rgba(0,0,0,.10)}
[data-baseweb="input"]>div,[data-baseweb="select"]>div,textarea,[data-testid="stDateInput"] input{transition:border-color .16s ease,box-shadow .16s ease}
[data-baseweb="input"]>div:focus-within,[data-baseweb="select"]>div:focus-within,textarea:focus,[data-testid="stDateInput"] input:focus{border-color:var(--pg-accent)!important;box-shadow:0 0 0 3px color-mix(in srgb,var(--pg-accent) 17%,transparent)!important}
[data-testid="stSegmentedControl"] button{box-shadow:inset 0 1px 0 color-mix(in srgb,var(--text-color) 6%,transparent)}[data-testid="stSegmentedControl"] button[aria-pressed="true"]{box-shadow:inset 0 1px 0 color-mix(in srgb,var(--text-color) 10%,transparent),0 4px 12px color-mix(in srgb,var(--pg-accent) 12%,transparent)}
.stButton button{box-shadow:inset 0 1px 0 color-mix(in srgb,var(--text-color) 6%,transparent);transition:transform .16s ease,border-color .16s ease,box-shadow .16s ease}.stButton button:hover{transform:translateY(-1px)}.stButton button[kind="primary"]{background:linear-gradient(135deg,var(--primary-color),color-mix(in srgb,var(--primary-color) 76%,#2478ff));box-shadow:inset 0 1px 0 rgba(255,255,255,.2),0 6px 15px color-mix(in srgb,var(--primary-color) 20%,transparent)}
[data-testid="stExpander"]{box-shadow:inset 0 1px 0 color-mix(in srgb,var(--text-color) 6%,transparent),0 8px 20px rgba(0,0,0,.07)}[data-testid="stExpander"]:hover{border-color:color-mix(in srgb,var(--pg-accent) 40%,var(--text-color) 12%)}
[data-baseweb="popover"]>div{border:1px solid color-mix(in srgb,var(--pg-accent) 24%,var(--text-color) 12%);box-shadow:0 16px 38px rgba(0,0,0,.2)}
@media(max-width:760px){.block-container{padding:1rem 1rem 2rem}.hero{padding-top:12px}.metric-card{padding:16px;min-height:112px}}
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
    st.caption("Merchant payment review")
    st.markdown("#### Data source")
    st.markdown(f"**{source}**")
    st.caption(source_status)
    st.markdown("#### About PayGuard")
    st.caption("PayGuard organizes payment activity, highlights rule-based patterns, and helps merchants investigate them with visible evidence.")
    st.caption("Risk scores are review priorities, not fraud probabilities. PayGuard does not block, cancel, or change payments.")

active_section = st.session_state.active_section_main
page_titles = {
    "Overview": ("Merchant overview", "Make unusual payment activity easier to investigate, with evidence you can inspect."),
    "Transactions": ("Transactions", "Search and inspect payment records using the available filters."),
    "Investigations": ("Investigations", "Review flagged activity, evidence, explanations, and saved notes."),
    "Analytics": ("Analytics", "Explore transaction patterns, payment outcomes, and recorded refunds."),
    "Settings": ("Settings", "Check data sources, credentials status, and local storage details."),
}
page_title, page_description = page_titles[active_section]
st.markdown(f'<div class="hero"><div class="eyebrow">PAYMENT INTELLIGENCE / {source.upper()}</div><h1>{page_title}</h1><p>{page_description}</p></div>', unsafe_allow_html=True)
active_section = st.segmented_control(
    "Sections",
    NAV_SECTIONS,
    default="Overview",
    key="active_section_main",
    label_visibility="collapsed",
    width="stretch",
)

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

if active_section == "Overview":
    first_row = st.columns(3)
    with first_row[0]: metric("TRANSACTIONS", f"{metrics['count']:,}", source)
    with first_row[1]: metric("PAYMENT VOLUME", volume_display, volume_note)
    with first_row[2]: metric("SUCCESSFUL", f"{metrics['success_count']:,}", currency_breakdown(metrics["success_amount_by_currency"]))
    second_row = st.columns(3)
    with second_row[0]: metric("FAILED", f"{metrics['failed_count']:,}", "Payment status")
    with second_row[1]: metric("REFUNDED", f"{metrics['refund_count']:,}" if metrics["refund_available"] else "Unavailable", currency_breakdown(metrics["refund_amount_by_currency"]) if metrics["refund_available"] else "Not provided by source")
    with second_row[2]: metric("OPEN REVIEWS", f"{open_count:,}", f"{high_count} high-priority findings")

    if transactions.empty:
        st.info("No transaction data is available for the selected source. Configure PayPal Sandbox or switch PAYGUARD_DATA_SOURCE to demo.")
    else:
        left, right = st.columns([1.6, 1])
        with left:
            st.markdown('<div class="section">Payment activity</div>', unsafe_allow_html=True)
            chart_data = transactions.copy(); chart_data["timestamp"] = pd.to_datetime(chart_data.timestamp, utc=True, errors="coerce")
            chart_data["amount"] = pd.to_numeric(chart_data.amount, errors="coerce")
            chart_data = chart_data.dropna(subset=["timestamp", "amount"]).set_index("timestamp").groupby("currency").resample("D").amount.sum().reset_index()
            st.plotly_chart(px.area(chart_data, x="timestamp", y="amount", color="currency", color_discrete_sequence=["#5b9cff", "#51d6bd", "#e8b768", "#ff7585"], labels={"timestamp":"Date", "amount":"Volume (native currency)"}).update_layout(paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,0)",margin=dict(l=0,r=0,t=8,b=0),height=290), width="stretch")
        with right:
            st.markdown('<div class="section">Payment status</div>', unsafe_allow_html=True)
            st.plotly_chart(px.pie(transactions, names="status", hole=.68, color_discrete_sequence=["#51d6bd", "#ff7585", "#e8b768", "#6e8cae"]).update_layout(paper_bgcolor="rgba(0,0,0,0)",margin=dict(l=0,r=0,t=8,b=0),height=290,showlegend=True), width="stretch")

    st.markdown('<div class="section section-center">Recent flagged activity</div>', unsafe_allow_html=True)
    if risk.empty:
        st.success("No records meet the current deterministic investigation rules.")
    else:
        view = risk.merge(transactions[["transaction_id", "transaction_key", "amount", "currency", "status", "timestamp", "event_code"]], on="transaction_key", how="left", suffixes=("_finding", "_transaction")).sort_values("score", ascending=False).head(8)
        with st.container(key="flagged-table-shell"):
            _, menu_column = st.columns([.94, .06], vertical_alignment="center")
            with menu_column:
                with st.popover("⋮", help="Show, hide, or restore table columns"):
                    st.markdown("**Visible columns**")
                    for column in FLAGGED_TABLE_COLUMNS:
                        st.checkbox(column.replace("_", " ").title(), value=True, key=f"flagged_column_{column}", on_change=_flagged_columns_changed)
                    st.button("Restore all columns", key="restore_flagged_columns", on_click=_restore_flagged_columns, use_container_width=True)
            visible_columns = [column for column in FLAGGED_TABLE_COLUMNS if st.session_state.get(f"flagged_column_{column}", True)]
            if visible_columns:
                st.dataframe(view[visible_columns], width="stretch", hide_index=True, key=f"flagged-activity-{st.session_state.flagged_table_revision}")
            else:
                st.info("All columns are hidden. Use the column menu to show them again.")
    st.markdown('<div class="section section-center">Risk priority</div>', unsafe_allow_html=True)
    if risk.empty:
        st.caption("Risk findings will appear when a rule has evidence to report.")
    else:
        priority_order = ["High", "Medium", "Low"]
        priority_counts = risk["severity"].value_counts().reindex(priority_order, fill_value=0).rename_axis("severity").reset_index(name="count")
        count_cols = st.columns([1, 1, 1])
        for col, level in zip(count_cols, priority_order):
            count = int(priority_counts.loc[priority_counts.severity.eq(level), "count"].iloc[0])
            with col:
                st.markdown(
                    f'<div class="priority-count"><div class="priority-count-label">{level} priority</div><div class="priority-count-value">{count}</div></div>',
                    unsafe_allow_html=True,
                )
        priority_chart = px.bar(
            priority_counts,
            x="severity",
            y="count",
            color="severity",
            text="count",
            category_orders={"severity": priority_order},
            color_discrete_map={"High": "#ff7585", "Medium": "#e8b768", "Low": "#51d6bd"},
        ).update_traces(textposition="outside", cliponaxis=False).update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            showlegend=False,
            margin=dict(l=12, r=12, t=20, b=8),
            height=320,
        )
        st.plotly_chart(priority_chart, width="stretch")
if active_section == "Transactions":
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

if active_section == "Investigations":
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
                if settings.openai_api_key and st.button("Ask AI to explain this finding", key=f"ai-{explanation_key}"):
                    result = explain_finding(finding.to_dict(), settings.openai_api_key, settings.openai_model, base_url=settings.openai_base_url)
                    st.session_state.ai_explanations[explanation_key] = result
                elif not settings.openai_api_key:
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

if active_section == "Analytics":
    st.markdown('<div class="section">Activity analysis</div>', unsafe_allow_html=True)
    if not transactions.empty:
        analytic = transactions.copy(); analytic["timestamp"] = pd.to_datetime(analytic.timestamp, utc=True, errors="coerce")
        period = st.selectbox("Period", ["All available data", "Last 7 days", "Last 30 days"])
        if period != "All available data": analytic = analytic[analytic.timestamp >= pd.Timestamp.now(tz="UTC") - pd.Timedelta(days=7 if period == "Last 7 days" else 30)]
        c1, c2 = st.columns(2)
        with c1: st.plotly_chart(px.histogram(analytic, x="amount", color="currency", facet_col="currency", nbins=24, title="Transaction amount distribution by currency").update_layout(paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,0)"), width="stretch")
        with c2:
            rule_rows = [{"rule": rule, "findings": int(risk.rules.map(lambda rules: rule in rules).sum())} for rule in sorted({r for rules in risk.rules for r in rules})] if not risk.empty else []
            if rule_rows: st.plotly_chart(px.bar(pd.DataFrame(rule_rows), x="rule", y="findings", title="Findings by rule", color_discrete_sequence=["#51d6bd"]).update_layout(paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,0)"), width="stretch")
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

if active_section == "Settings":
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
    st.write(f"**AI provider key:** {'Configured; a request is made only when you click the explanation button' if settings.openai_api_key else 'Not configured; deterministic fallback is active'} — key remains server-side.")
    st.write("**Storage:** Local SQLite file; suitable for a demo, not shared multi-user production storage.")
    st.markdown("Set environment variables before starting Streamlit or in Render settings. Streamlit does not load `.env` automatically. Never paste credentials into this page.")
    st.code("PAYGUARD_DATA_SOURCE=demo  # or paypal\nPAYPAL_CLIENT_ID=...\nPAYPAL_CLIENT_SECRET=...\nPAYPAL_BASE_URL=https://api-m.sandbox.paypal.com\nOPENAI_API_KEY=...\nOPENAI_MODEL=gpt-4o-mini\nOPENAI_BASE_URL=https://api.openai.com/v1", language="bash")
    