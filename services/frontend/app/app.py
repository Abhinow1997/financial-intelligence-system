# Analyst Dashboard (R1+) - Streamlit frontend.
import os

import requests
import streamlit as st

GATEWAY = os.getenv("GATEWAY_URL", "http://localhost:8080")

st.set_page_config(page_title="Financial Intelligence System", layout="wide")
st.title("Financial Intelligence System")
st.caption("Analyst dashboard - predictions, grounded answers, agent traces, unit economics.")

tab1, tab2, tab3, tab4 = st.tabs(["Predict (R1)", "Ask/RAG (R2)", "Agent (R3)", "Economics"])

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
