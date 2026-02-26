from __future__ import annotations

import os

import streamlit as st

from chatbot.services.assistant import ChatbotService


st.set_page_config(page_title="Support Multi-Agent Chatbot", layout="wide")
st.title("Customer Support Chatbot")

if "service" not in st.session_state:
    st.session_state.service = ChatbotService()
elif not hasattr(st.session_state.service, "ask_with_meta"):
    st.session_state.service = ChatbotService()
if "history" not in st.session_state:
    st.session_state.history = []

service: ChatbotService = st.session_state.service
show_setup_ui = os.getenv("SHOW_SETUP_UI", "false").lower() == "true"
auto_seed_sql_if_empty = os.getenv("AUTO_SEED_SQL_IF_EMPTY", "true").lower() == "true"

if "sql_bootstrap_done" not in st.session_state:
    if auto_seed_sql_if_empty:
        st.session_state.sql_bootstrap_message = service.ensure_sql_data()
    else:
        st.session_state.sql_bootstrap_message = "Auto-seed disabled. Using existing local SQL data if available."
    st.session_state.sql_bootstrap_done = True

with st.sidebar:
    st.caption(f"SQL Demo Data: {st.session_state.sql_bootstrap_message}")
    st.subheader("Ingest Policy PDFs")
    policy_dir = st.text_input("Policy folder path", value="./policy_docs")
    if st.button("Ingest PDFs", use_container_width=True):
        message = service.ingest_policy_directory(policy_dir)
        if "Invalid" in message or "No PDF" in message:
            st.warning(message)
        else:
            st.success(message)

    if show_setup_ui:
        st.header("Admin Setup")
        if st.button("Initialize SQL Dummy Data", use_container_width=True):
            st.success(service.initialize_sql_data())

st.markdown("Ask questions about customer data, support tickets, and policy documents.")

for turn in st.session_state.history:
    with st.chat_message("user"):
        st.write(turn["user"])
    with st.chat_message("assistant"):
        st.caption(f"Route: {turn.get('route', 'NONE')}")
        st.write(turn["assistant"])

question = st.chat_input("Ask the assistant...")
if question:
    with st.chat_message("user"):
        st.write(question)

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            result = service.ask_with_meta(question)
            answer = result["answer"]
            route = result["route"]
        st.caption(f"Route: {route}")
        st.write(answer)

    st.session_state.history.append({"user": question, "assistant": answer, "route": route})
