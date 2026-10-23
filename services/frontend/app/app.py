# Analyst Dashboard (R1+) - Streamlit frontend.
import os

import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st

GATEWAY = os.getenv("GATEWAY_URL", "http://localhost:8080")
# Lab 01 calls the backend directly. Later releases route this through the gateway
# once it does real authN/Z, redaction and audit.
BACKEND = os.getenv("BACKEND_URL", "http://localhost:8000")

st.set_page_config(page_title="Financial Intelligence System", layout="wide")
st.title("Financial Intelligence System")
st.caption("Analyst dashboard - predictions, grounded answers, agent traces, unit economics.")

tab_market, tab_facts, tab1, tab2, tab3, tab4 = st.tabs(
    ["Market (Lab 01)", "Facts (DuckDB)", "Predict (R1)", "Ask/RAG (R2)", "Agent (R3)", "Economics"]
)

FACT_METRICS = {
    "revenue": "Revenue",
    "operating_income": "Operating income",
    "net_income": "Net income",
    "eps_diluted": "Diluted EPS",
}
# Where the backend found the facts -> how to say so (st.<kind>, message)
FACT_SOURCES = {
    "fact_store": ("success", "From the fact store, data/facts/facts.duckdb (built by src/facts/build.py)."),
    "sec_cache": ("info", "From the fact store, data/facts/facts.duckdb (fetched from the SEC earlier and saved there)."),
    "sec_live": ("warning", "Not in DuckDB yet: fetched live from the SEC just now and saved to data/facts/facts.duckdb."),
}


def compact(value: float | None) -> str:
    if not value:
        return "-"
    for threshold, suffix in ((1e12, "T"), (1e9, "B"), (1e6, "M")):
        if abs(value) >= threshold:  # abs: net income can be a loss
            return f"{value / threshold:,.2f}{suffix}"
    return f"{value:,.0f}"


def fetch(path: str):
    """Return (payload, error_message). Errors are shown, never raised."""
    try:
        response = requests.get(f"{BACKEND}{path}", timeout=30)
    except requests.RequestException as exc:
        return None, f"Backend unreachable at {BACKEND} ({exc.__class__.__name__})."
    if response.status_code != 200:
        return None, response.json().get("detail", response.text)
    return response.json(), None


with tab_market:
    st.subheader("Market data (yfinance)")

    controls = st.columns([2, 2, 2, 1])
    ticker = controls[0].text_input("Ticker", value="AAPL").strip().upper()
    period = controls[1].selectbox("Period", ["5d", "1mo", "3mo", "6mo", "1y", "5y", "max"], index=3)
    interval = controls[2].selectbox("Interval", ["1h", "1d", "1wk", "1mo"], index=1)
    controls[3].markdown("&nbsp;", unsafe_allow_html=True)
    go_clicked = controls[3].button("Load", type="primary", use_container_width=True)

    if go_clicked or ticker:
        quote, quote_error = fetch(f"/market/quote/{ticker}")

        if quote_error:
            st.error(quote_error)
        else:
            metrics = st.columns(5)
            currency = quote.get("currency") or ""
            metrics[0].metric(
                f"Price ({currency})",
                f"{quote['price']:,.2f}",
                delta=(
                    f"{quote['change']:,.2f} ({quote['change_pct']:.2f}%)"
                    if quote.get("change") is not None
                    else None
                ),
            )
            metrics[1].metric("Previous close", f"{quote.get('previous_close') or 0:,.2f}")
            metrics[2].metric("Day high", f"{quote.get('day_high') or 0:,.2f}")
            metrics[3].metric("Day low", f"{quote.get('day_low') or 0:,.2f}")
            metrics[4].metric("Market cap", compact(quote.get("market_cap")))
            st.caption(f"quote latency: {quote['latency_ms']} ms")

        history, history_error = fetch(
            f"/market/history/{ticker}?period={period}&interval={interval}"
        )

        if history_error:
            st.warning(history_error)
        else:
            frame = pd.DataFrame(history["bars"])
            frame["timestamp"] = pd.to_datetime(frame["timestamp"])

            figure = go.Figure(
                go.Candlestick(
                    x=frame["timestamp"],
                    open=frame["open"],
                    high=frame["high"],
                    low=frame["low"],
                    close=frame["close"],
                    name=ticker,
                )
            )
            figure.update_layout(
                height=440,
                margin=dict(l=0, r=0, t=10, b=0),
                xaxis_rangeslider_visible=False,
            )
            st.plotly_chart(figure, use_container_width=True)
            st.caption(
                f"{history['count']} bars · {history['period']} / {history['interval']} "
                f"· history latency: {history['latency_ms']} ms"
            )

            with st.expander("Raw OHLCV"):
                st.dataframe(frame, use_container_width=True)

        with st.expander("Fundamentals"):
            fundamentals, fundamentals_error = fetch(f"/market/fundamentals/{ticker}")
            if fundamentals_error:
                st.warning(fundamentals_error)
            else:
                st.write(
                    f"**{fundamentals.get('name') or ticker}** — "
                    f"{fundamentals.get('sector') or '?'} / "
                    f"{fundamentals.get('industry') or '?'}"
                )
                st.table(
                    {
                        "Metric": [
                            "Trailing P/E",
                            "Forward P/E",
                            "Trailing EPS",
                            "Beta",
                            "52w high",
                            "52w low",
                        ],
                        "Value": [
                            fundamentals.get("trailing_pe"),
                            fundamentals.get("forward_pe"),
                            fundamentals.get("trailing_eps"),
                            fundamentals.get("beta"),
                            fundamentals.get("week52_high"),
                            fundamentals.get("week52_low"),
                        ],
                    }
                )
                if fundamentals.get("summary"):
                    st.caption(fundamentals["summary"])

with tab_facts:
    st.subheader("XBRL facts (DuckDB)")
    st.caption(
        "Annual 10-K figures, each tied to its filing and XBRL concept so it can be cited. "
        "A ticker that isn't in DuckDB yet is fetched from the SEC once and saved, then served from DuckDB."
    )

    controls = st.columns([2, 2, 1])
    facts_ticker = controls[0].text_input("Ticker", value="AAPL", key="facts_ticker").strip().upper()
    facts_metric = controls[1].selectbox(
        "Metric",
        ["all", *FACT_METRICS],
        format_func=lambda m: FACT_METRICS.get(m, "All metrics"),
        key="facts_metric",
    )
    controls[2].markdown("&nbsp;", unsafe_allow_html=True)
    controls[2].button("Load", type="primary", use_container_width=True, key="facts_load")

    if facts_ticker:
        query = "" if facts_metric == "all" else f"?metric={facts_metric}"
        with st.spinner(f"Looking up {facts_ticker}..."):
            payload, facts_error = fetch(f"/facts/{facts_ticker}{query}")

        if facts_error:
            st.error(facts_error)
        elif not payload["facts"]:
            st.info(f"No {FACT_METRICS.get(facts_metric, '')} facts for {payload['ticker']}.")
        else:
            kind, note = FACT_SOURCES[payload["source"]]
            getattr(st, kind)(note)

            facts = pd.DataFrame(payload["facts"])
            facts["period_end"] = pd.to_datetime(facts["period_end"])
            facts = facts.sort_values("period_end")
            facts["fiscal_year"] = "FY" + facts["period_end"].dt.year.astype(str)  # named by the year it ends
            present = [m for m in FACT_METRICS if m in set(facts["metric"])]

            # Latest year per metric, with growth over the year before
            headline = st.columns(len(present))
            for column, metric in zip(headline, present):
                series = facts[facts["metric"] == metric]
                latest = series.iloc[-1]
                previous = series.iloc[-2]["value"] if len(series) > 1 else None
                growth = (latest["value"] - previous) / abs(previous) if previous else None
                column.metric(
                    f"{FACT_METRICS[metric]} · {latest['fiscal_year']}",
                    f"{latest['value']:,.2f}" if latest["unit"] == "USD/shares" else compact(latest["value"]),
                    delta=f"{growth:+.1%}" if growth is not None else None,
                )

            money = [m for m in present if m != "eps_diluted"]
            charts = st.columns([3, 2]) if money and "eps_diluted" in present else [st.container()]
            if money:
                figure = go.Figure(
                    [
                        go.Bar(
                            x=facts.loc[facts["metric"] == m, "fiscal_year"],
                            y=facts.loc[facts["metric"] == m, "value"] / 1e9,
                            name=FACT_METRICS[m],
                        )
                        for m in money
                    ]
                )
                figure.update_layout(
                    barmode="group",
                    height=380,
                    margin=dict(l=0, r=0, t=10, b=0),
                    xaxis=dict(type="category", categoryorder="category ascending"),
                    yaxis_title="USD billions",
                    legend=dict(orientation="h"),
                )
                charts[0].plotly_chart(figure, use_container_width=True)
            if "eps_diluted" in present:
                eps = facts[facts["metric"] == "eps_diluted"]
                figure = go.Figure(go.Scatter(x=eps["fiscal_year"], y=eps["value"], mode="lines+markers"))
                figure.update_layout(
                    height=380,
                    margin=dict(l=0, r=0, t=10, b=0),
                    xaxis=dict(type="category"),
                    yaxis_title="Diluted EPS (USD)",
                )
                charts[-1].plotly_chart(figure, use_container_width=True)
                charts[-1].caption("As reported in each 10-K, not split-adjusted: a stock split shows up as a drop.")

            st.dataframe(
                facts.sort_values(["period_end", "metric"], ascending=[False, True]).assign(
                    period_end=facts["period_end"].dt.date,
                    metric=facts["metric"].map(FACT_METRICS),
                    citation=facts["citation"].map(lambda c: c.get("kind")),
                )[["period_end", "metric", "value", "unit", "doc_id", "concept", "tier", "citation"]],
                column_config={
                    "period_end": "Period end",
                    "metric": "Metric",
                    "value": st.column_config.NumberColumn("Value", format="localized"),
                    "unit": "Unit",
                    "doc_id": "Filing (accession)",
                    "concept": "XBRL concept",
                    "tier": "Tier",
                    "citation": "Citation",
                },
                use_container_width=True,
                hide_index=True,
            )
            st.caption(f"{payload['count']} facts · source: {payload['source']} · latency: {payload['latency_ms']} ms")

            with st.expander("One fact as the API returns it"):
                st.json(payload["facts"][0])

    with st.expander("Tickers already in DuckDB"):
        tickers, tickers_error = fetch("/facts")
        if tickers_error:
            st.warning(tickers_error)
        else:
            st.dataframe(pd.DataFrame(tickers), use_container_width=True, hide_index=True)

with tab1:
    st.subheader("Credit-default prediction")
    st.info("Wire this to the model_service /predict endpoint.")
with tab2:
    st.subheader("Ask the evidence base")
    st.text_input("Question", key="q")
    st.info("Wire this to backend /ask (retriever + generation + citations).")
with tab3:
    st.subheader("Bounded agent")
    st.info("Wire this to agent_runtime /run and render the trace + cost.")
with tab4:
    st.subheader("Standing unit-economics table")
    st.table(
        {
            "Metric": ["Cost/task", "Latency p50/p95", "Minutes saved", "Quality", "Tasks/mo"],
            "Value": ["-", "-", "-", "-", "-"],
        }
    )

try:
    h = requests.get(f"{GATEWAY}/health", timeout=1).json()
    st.sidebar.success(f"gateway: {h.get('status')}")
except Exception:
    st.sidebar.warning("gateway offline (start it with docker compose up)")

try:
    h = requests.get(f"{BACKEND}/health", timeout=1).json()
    st.sidebar.success(f"backend: {h.get('status')}")
except Exception:
    st.sidebar.warning("backend offline (start it with docker compose up)")
