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

tab_market, tab1, tab2, tab3, tab4 = st.tabs(
    ["Market (Lab 01)", "Predict (R1)", "Ask/RAG (R2)", "Agent (R3)", "Economics"]
)


def compact(value: float | None) -> str:
    if not value:
        return "-"
    for threshold, suffix in ((1e12, "T"), (1e9, "B"), (1e6, "M")):
        if value >= threshold:
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
