"""
streamlit_app.py: the web interface for ClinicFlow AI.

Two tabs:
    1. Process a message: type (or load) a patient message and see what the AI does.
    2. Dashboard: summary numbers and the history of processed messages.

The page talks to the FastAPI backend, so start the backend first.

Terminal 1 (backend):   uvicorn app.main:app --reload
Terminal 2 (this page): streamlit run streamlit_app.py
"""

import json

import pandas as pd
import requests
import streamlit as st

from app.config import BACKEND_URL, TEST_MESSAGES_PATH
from app.prompts import ACTIVE_VERSION, PROMPTS

st.set_page_config(page_title="ClinicFlow AI", page_icon="🏥", layout="wide")

NO_SAMPLE = "(type my own message)"


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------
@st.cache_data
def load_samples() -> dict:
    """Sample patient messages from the test set, for quick demos."""
    data = json.loads(TEST_MESSAGES_PATH.read_text(encoding="utf-8"))
    return {f"{m['id']}: {m['message'][:70]}": m["message"] for m in data["messages"]}


def call_backend(method: str, path: str, **kwargs):
    """Call the FastAPI backend. Returns (data, error_message)."""
    try:
        response = requests.request(method, f"{BACKEND_URL}{path}", timeout=120, **kwargs)
    except requests.exceptions.ConnectionError:
        return None, (
            f"Cannot reach the backend at {BACKEND_URL}. "
            "Start it with: uvicorn app.main:app --reload"
        )
    except requests.exceptions.Timeout:
        return None, "The backend took too long to respond. Please try again."

    if response.status_code != 200:
        try:
            detail = response.json().get("detail", response.text)
        except ValueError:
            detail = response.text
        return None, f"Backend error ({response.status_code}): {detail}"
    return response.json(), None


samples = load_samples()


def use_sample() -> None:
    """When a sample is chosen, copy it into the message box."""
    choice = st.session_state["sample_choice"]
    if choice != NO_SAMPLE:
        st.session_state["message_text"] = samples[choice]


st.session_state.setdefault("message_text", "")

# ----------------------------------------------------------------------
# Page header and sidebar
# ----------------------------------------------------------------------
st.title("🏥 ClinicFlow AI")
st.caption("AI triage for patient messages at a small clinic. Demo with synthetic data only.")
st.warning(
    "This demo does not give medical advice. In an emergency, call your local "
    "emergency number immediately."
)

versions = list(PROMPTS)
version = st.sidebar.selectbox(
    "Prompt version", versions, index=versions.index(ACTIVE_VERSION)
)
st.sidebar.caption("Switch versions to compare how different prompts handle the same message.")

health, health_error = call_backend("GET", "/health")
if health_error:
    st.sidebar.error("Backend: not reachable")
else:
    st.sidebar.success("Backend: running")

tab_process, tab_dashboard = st.tabs(["Process a message", "Dashboard"])

# ----------------------------------------------------------------------
# Tab 1: process a message
# ----------------------------------------------------------------------
with tab_process:
    st.selectbox(
        "Load a sample message",
        [NO_SAMPLE] + list(samples),
        key="sample_choice",
        on_change=use_sample,
    )
    message = st.text_area("Patient message", key="message_text", height=120)

    if st.button("Process message", type="primary"):
        if not message.strip():
            st.error("Please enter a message first.")
        else:
            with st.spinner("ClinicFlow AI is working on it..."):
                result, error = call_backend(
                    "POST", "/process", json={"message": message, "prompt_version": version}
                )

            if error:
                st.error(error)
            else:
                if result["needs_human"]:
                    st.error("🚨 HUMAN NEEDED: this message has been escalated to clinic staff.")
                    if result.get("staff_alert"):
                        st.write(f"**Staff alert:** {result['staff_alert']}")
                else:
                    st.success("✅ Handled automatically")

                col1, col2, col3 = st.columns(3)
                col1.metric("Category", result["category"])
                col2.metric("Prompt version", result["prompt_version"])
                col3.metric("Request id", result["id"])

                st.subheader("Reply to patient")
                st.info(result["reply"])

                if result["retrieved_sections"]:
                    st.write("**FAQ sections used:** " + ", ".join(result["retrieved_sections"]))
                if result["details"]:
                    with st.expander("Extracted details"):
                        st.json(result["details"])

# ----------------------------------------------------------------------
# Tab 2: dashboard
# ----------------------------------------------------------------------
with tab_dashboard:
    st.button("Refresh")

    stats, stats_error = call_backend("GET", "/stats")
    if stats_error:
        st.error(stats_error)
    else:
        col1, col2 = st.columns(2)
        col1.metric("Messages processed", stats["total"])
        col2.metric("Escalated to a human", stats["needs_human"])

        if stats["by_category"]:
            st.subheader("Messages by category")
            st.bar_chart(pd.Series(stats["by_category"]))

    history, history_error = call_backend("GET", "/requests", params={"limit": 100})
    if history_error:
        st.error(history_error)
    elif history:
        st.subheader("Recent messages")
        table = pd.DataFrame(history)[
            ["created_at", "prompt_version", "category", "needs_human", "message", "reply"]
        ]
        st.dataframe(table, hide_index=True)
    else:
        st.info("No messages processed yet. Try one in the first tab.")
