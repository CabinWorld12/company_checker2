import os
import re
import requests
import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(page_title="Company Checker", page_icon="📊", layout="wide")

API_BASE = "https://data.businessquant.com"
st.title("📊 Company Checker")
st.caption("A simple company research dashboard powered by Business Quant.")

def get_secret(name, default=""):
    try:
        return st.secrets.get(name, os.getenv(name, default))
    except Exception:
        return os.getenv(name, default)

def password_gate():
    password = get_secret("APP_PASSWORD")
    if not password:
        return True
    if st.session_state.get("app_unlocked"):
        return True
    st.subheader("Private access")
    entered = st.text_input("App password", type="password")
    if st.button("Unlock"):
        if entered == password:
            st.session_state.app_unlocked = True
            st.rerun()
        st.error("That password did not match.")
    return False

if not password_gate():
    st.stop()

api_key = get_secret("BUSINESSQUANT_API_KEY")
if not api_key:
    st.warning("Business Quant API key not configured yet.")
    st.markdown("""
    Add this to **Streamlit → App settings → Secrets**:
    ```toml
    BUSINESSQUANT_API_KEY = "paste-your-Business-Quant-key-here"
    APP_PASSWORD = "choose-a-private-password"
    ```
    Save the secrets and reload the app.
    """)
    st.stop()

@st.cache_data(ttl=86400, show_spinner=False)
def get_metric_catalog(_api_key):
    response = requests.get(
        f"{API_BASE}/metadata",
        params={"table": "historic", "api_key": _api_key},
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    if isinstance(payload, list):
        return payload
    for key in ("data", "metrics", "results"):
        if isinstance(payload, dict) and isinstance(payload.get(key), list):
            return payload[key]
    raise ValueError("The metric catalogue response had an unexpected format.")

def pick_slug(catalog, wanted, keywords):
    # Prefer exact display-name matches, then a slug containing all required terms.
    for item in catalog:
        full = str(item.get("metric_full", "")).strip().lower()
        short = str(item.get("metric_short", "")).strip().lower()
        slug = str(item.get("slug", "")).strip()
        if slug and any(full == x.lower() or short == x.lower() for x in wanted):
            return slug
    candidates = []
    for item in catalog:
        slug = str(item.get("slug", "")).lower()
        full = str(item.get("metric_full", "")).lower()
        dim = str(item.get("dimension", "")).lower()
        text = f"{slug} {full} {dim}"
        if all(k in text for k in keywords):
            candidates.append(item)
    # Prefer annual metrics for financial statements and daily for P/E.
    if "annual" in keywords:
        candidates.sort(key=lambda x: ("annual" not in str(x.get("slug", "")).lower(), len(str(x.get("slug", "")))))
    elif "daily" in keywords:
        candidates.sort(key=lambda x: ("price-to-earnings" not in str(x.get("slug", "")).lower(), len(str(x.get("slug", "")))))
    return str(candidates[0].get("slug")) if candidates else None

@st.cache_data(ttl=1800, show_spinner=False)
def fetch_historic(tickers_tuple, slugs_tuple, period, _api_key):
    response = requests.get(
        f"{API_BASE}/historic",
        params={
            "ticker": ",".join(tickers_tuple),
            "slug": ",".join(slugs_tuple),
            "period": period,
            "api_key": _api_key,
        },
        timeout=45,
    )
    if response.status_code == 401 or response.status_code == 403:
        raise ValueError("Business Quant did not accept the API key or your plan does not permit this request.")
    if response.status_code == 404:
        raise ValueError("Business Quant returned no data for one or more requested metrics/tickers. Check the ticker and metric availability.")
    response.raise_for_status()
    payload = response.json()
    rows = payload.get("data", []) if isinstance(payload, dict) else payload
    if not isinstance(rows, list):
        raise ValueError("The historical data response had an unexpected format.")
    return rows

def compact_number(value):
    if pd.isna(value):
        return "—"
    value = float(value)
    absolute = abs(value)
    if absolute >= 1_000_000_000_000:
        return f"{value/1_000_000_000_000:,.2f}T"
    if absolute >= 1_000_000_000:
        return f"{value/1_000_000_000:,.2f}B"
    if absolute >= 1_000_000:
        return f"{value/1_000_000:,.2f}M"
    return f"{value:,.2f}"

def show_value(value, metric):
    if pd.isna(value):
        return "—"
    if metric == "pe":
        return f"{float(value):,.1f}×"
    return compact_number(value)

st.sidebar.header("Find companies")
raw = st.sidebar.text_input("Ticker symbols", value="AAPL, MSFT")
tickers = list(dict.fromkeys(re.findall(r"[A-Za-z0-9.\-]+", raw.upper())))
if len(tickers) > 5:
    st.sidebar.warning("The Business Quant historical endpoint allows up to 5 tickers per request. Only the first five will be used.")
    tickers = tickers[:5]
period_label = st.sidebar.selectbox("History window", ["2 years (free API limit)", "1 year"])
period = "2y" if period_label.startswith("2") else "1y"
st.sidebar.caption("The free API tier currently lists 30 calls/day and up to 2 years of metric history. This app combines the three metrics into one historical-data request.")
if st.sidebar.button("Refresh data"):
    st.cache_data.clear()

if not tickers:
    st.info("Enter at least one ticker symbol in the sidebar.")
    st.stop()

try:
    with st.spinner("Checking Business Quant's metric catalogue…"):
        catalog = get_metric_catalog(api_key)
    revenue_slug = pick_slug(catalog, ["Revenue (Annual)"], ["revenue", "annual"])
    operating_slug = pick_slug(catalog, ["Operating Income (Annual)", "Operating Income (Yr)"], ["operating", "income", "annual"])
    pe_slug = pick_slug(catalog, ["Price to Earnings"], ["price-to-earnings", "daily"])
    missing = [name for name, slug in [
        ("annual revenue", revenue_slug),
        ("annual operating income", operating_slug),
        ("daily P/E ratio", pe_slug),
    ] if not slug]
    if missing:
        st.error("Couldn't identify these metrics in the Business Quant catalogue: " + ", ".join(missing))
        st.stop()
    metric_slugs = (revenue_slug, operating_slug, pe_slug)
    with st.spinner("Loading company financial history…"):
        rows = fetch_historic(tuple(tickers), metric_slugs, period, api_key)
except requests.RequestException as exc:
    st.error(f"Could not connect to Business Quant: {exc}")
    st.stop()
except Exception as exc:
    st.error(str(exc))
    st.stop()

if not rows:
    st.warning("No data was returned. Check the ticker symbols and whether Business Quant covers those companies on your plan.")
    st.stop()

df = pd.DataFrame(rows)
required = {"ticker", "date", "value", "metric"}
if not required.issubset(df.columns):
    st.error("Business Quant returned data in an unexpected format. Please check the API documentation.")
    st.stop()

df["date"] = pd.to_datetime(df["date"], errors="coerce")
df["value"] = pd.to_numeric(df["value"], errors="coerce")
df = df.dropna(subset=["date", "value"])
df["ticker"] = df["ticker"].astype(str).str.upper()

def metric_kind(row):
    slug_text = str(row.get("metric", "")).lower()
    if "price to earnings" in slug_text or "p/e" in slug_text or "earnings ratio" in slug_text:
        return "pe"
    if "operating income" in slug_text or "operating profit" in slug_text:
        return "operating"
    if "revenue" in slug_text:
        return "revenue"
    return "other"

df["kind"] = df.apply(metric_kind, axis=1)
# Fallback: map by the returned metric label or requested slug when label wording varies.
for kind, slug in [("revenue", revenue_slug), ("operating", operating_slug), ("pe", pe_slug)]:
    if kind not in set(df["kind"]):
        metric_name = next((str(x.get("metric_full", "")) for x in catalog if x.get("slug") == slug), "")
        if metric_name:
            mask = df["metric"].astype(str).str.lower().eq(metric_name.lower())
            df.loc[mask, "kind"] = kind

company_names = {}
for _, row in df.iterrows():
    company_names[row["ticker"]] = row.get("companyname_short") or row.get("companyname") or row["ticker"]

st.caption("Data source: Business Quant. This free-tier app is limited to the data and history your plan exposes; coverage can vary by ticker.")

tabs = st.tabs(["Company overview", "Compare companies", "About the numbers"])

with tabs[0]:
    available = sorted(df["ticker"].unique().tolist())
    chosen = st.selectbox("Choose a company", available)
    st.subheader(f"{company_names.get(chosen, chosen)} ({chosen})")
    company_df = df[df["ticker"] == chosen]
    metric_defs = [
        ("revenue", "Latest annual revenue"),
        ("operating", "Latest annual operating income"),
        ("pe", "Latest P/E ratio"),
    ]
    cols = st.columns(3)
    for col, (kind, label) in zip(cols, metric_defs):
        subset = company_df[company_df["kind"] == kind].sort_values("date")
        if subset.empty:
            col.metric(label, "Not available")
        else:
            latest = subset.iloc[-1]
            col.metric(label, show_value(latest["value"], kind), help=f"Observation date: {latest['date'].date()}")
    for kind, title in [
        ("revenue", "Annual revenue history"),
        ("operating", "Annual operating income history"),
        ("pe", "Daily P/E ratio history"),
    ]:
        subset = company_df[company_df["kind"] == kind].sort_values("date")
        st.markdown(f"**{title}**")
        if subset.empty:
            st.info("No observations returned for this metric.")
            continue
        table = subset[["date", "value"]].copy()
        table["Date"] = table["date"].dt.strftime("%Y-%m-%d")
        table["Value"] = table["value"].map(lambda x: show_value(x, kind))
        st.dataframe(table[["Date", "Value"]], hide_index=True, use_container_width=True)
        fig = px.line(subset, x="date", y="value", markers=True, title=title)
        fig.update_layout(xaxis_title="Reporting date" if kind != "pe" else "Date", yaxis_title="P/E (×)" if kind == "pe" else "Reported value")
        if kind == "pe":
            fig.update_yaxes(ticksuffix="×")
        else:
            fig.update_yaxes(tickformat="~s")
        st.plotly_chart(fig, use_container_width=True)

with tabs[1]:
    st.subheader("Side-by-side comparison")
    st.caption("Revenue and operating income are shown in the provider's reported units. Check company filings before comparing raw amounts across issuers with different reporting currencies.")
    summary = []
    for ticker in sorted(df["ticker"].unique()):
        row = {"Company": f"{company_names.get(ticker, ticker)} ({ticker})"}
        for kind, label in [("revenue", "Latest annual revenue"), ("operating", "Latest operating income"), ("pe", "Latest P/E")]:
            part = df[(df["ticker"] == ticker) & (df["kind"] == kind)].sort_values("date")
            row[label] = show_value(part.iloc[-1]["value"], kind) if not part.empty else "—"
        summary.append(row)
    st.dataframe(pd.DataFrame(summary), hide_index=True, use_container_width=True)
    graph_metric = st.radio("Graph metric", ["Revenue", "Operating income", "P/E ratio"], horizontal=True)
    kind = {"Revenue": "revenue", "Operating income": "operating", "P/E ratio": "pe"}[graph_metric]
    plot = df[df["kind"] == kind].copy()
    if plot.empty:
        st.info("No data available for this graph.")
    else:
        plot["Company"] = plot["ticker"].map(lambda x: company_names.get(x, x))
        fig = px.line(plot, x="date", y="value", color="Company", markers=True, title=f"{graph_metric} comparison")
        fig.update_layout(xaxis_title="Date", yaxis_title="P/E (×)" if kind == "pe" else "Reported value")
        if kind == "pe":
            fig.update_yaxes(ticksuffix="×")
        else:
            fig.update_yaxes(tickformat="~s")
        st.plotly_chart(fig, use_container_width=True)

with tabs[2]:
    st.subheader("How to interpret the figures")
    st.markdown("""
- **Revenue** is the money a company earns from its ordinary business before expenses.
- **Operating income** is profit from the company's core operations before interest and tax.
- **P/E** compares a share price with earnings per share. It is a market valuation ratio, not a measure of profit by itself.
- Annual revenue and operating income are fiscal-year figures; companies can have different financial year-end dates.
- P/E is daily and can change with the share price. A negative or unavailable P/E may be missing or not meaningful.
- This app initially covers US-listed securities available in Business Quant. It does not promise coverage of every ticker.
- The free API plan currently limits the API history to the latest two years for financial metrics and 30 calls per day. The app uses one main data request for up to five tickers and three metrics.
- This is a research and learning tool, not a buy/sell recommendation.
    """)
    st.caption("Always check the original company filing for context and definitions. Provider coverage and plan limits can change.")
