"""
Demo Streamlit app with LLM connection.
Run: streamlit run demo_llm.py
"""
"""
Demo Streamlit app with LLM connection.
Run: streamlit run services/frontend/app/demo_llm.py
"""
import os
import streamlit as st
from pathlib import Path
from dotenv import load_dotenv
from anthropic import Anthropic

# Load .env from repo root
env_path = Path(__file__).resolve().parents[3] / ".env"
load_dotenv(env_path)

st.set_page_config(page_title="LLM Demo", layout="wide")
st.title("💬 LLM Demo - Financial Q&A")
st.caption("Ask questions about finance, credit, risk, etc.")

# Initialize Anthropic client
client = Anthropic()

# Session state for conversation history
if "messages" not in st.session_state:
    st.session_state.messages = []

# Display chat history
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])

# User input
if user_input := st.chat_input("Ask a question..."):
    # Add user message to history
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.write(user_input)

    # Call Claude API
    with st.spinner("Thinking..."):
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1024,
            system="You are a helpful financial expert. Answer questions about credit, risk, portfolios, and finance clearly and concisely.",
            messages=st.session_state.messages,
        )
        assistant_message = response.content[0].text

    # Add assistant response to history
    st.session_state.messages.append({"role": "assistant", "content": assistant_message})
    with st.chat_message("assistant"):
        st.write(assistant_message)

# Sidebar
with st.sidebar:
    st.subheader("ℹ️ Setup")
    st.info(
        "Set your API key:\n"
        "```\nexport ANTHROPIC_API_KEY=sk-ant-...\n```\n"
        "Then run this app."
    )
    if st.button("Clear chat"):
        st.session_state.messages = []
        st.rerun()
