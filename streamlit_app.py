"""
streamlit_app.py: the web interface for ClinicFlow AI.

Two tabs:
    1. Process a message: type (or load) a patient message and see what the AI does.
    2. Dashboard: summary numbers and the history of processed messages.

Two ways to run (the page picks automatically):
    - API mode: if the FastAPI backend is running, the page talks to it.
        Terminal 1:  uvicorn app.main:app --reload
        Terminal 2:  streamlit run streamlit_app.py
    - All-in-one mode: if no backend is found (for example on Streamlit Community
        Cloud), the page runs the same workflow directly. Only one command is needed:
        streamlit run streamlit_app.py
"""

import json
import sys

# Optional: some hosts ship an old SQLite that Chroma rejects. If the
# pysqlite3-binary package is installed, use it. If not, nothing changes.
try:
    __import__("pysqlite3")
    sys.modules["sqlite3"] = sys.modules.pop("pysqlite3")
except ImportError:
    pass

import pandas as pd
import requests
import streamlit as st

from app.config import BACKEND_URL, TEST_MESSAGES_PATH
from app.prompts import ACTIVE_VERSION, PROMPTS

st.set_page_config(page_title="ClinicFlow AI", page_icon="🏥", layout="wide")

NO_SAMPLE = "(type my own message)"


# ----------------------------------------------------------------------
# Which mode are we in?
# ----------------------------------------------------------------------
@st.cache_data(ttl=30)
def api_available() -> bool:
    """True if the FastAPI backend answers at BACKEND_URL."""
    try:
        return requests.get(f"{BACKEND_URL}/health", timeout=2).status_code == 200
    except requests.exceptions.RequestException:
        return False


USE_API = api_available()


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------
@st.cache_data
def load_samples() -> dict:
    """Sample patient messages from the test set, for quick demos."""
    data = json.loads(TEST_MESSAGES_PATH.read_text(encoding="utf-8"))
    return {f"{m['id']}: {m['message'][:70]}": m["message"] for m in data["messages"]}


def call_direct(method: str, path: str, **kwargs):
    """All-in-one mode: run the workflow and database code directly. Returns (data, error)."""
    from app.database import get_recent_requests, get_stats, log_request

    try:
        if path == "/health":
            return {"status": "ok", "mode": "direct"}, None
        if path == "/stats":
            return get_stats(), None
        if path == "/requests":
            limit = (kwargs.get("params") or {}).get("limit", 50)
            return get_recent_requests(limit), None
        if path == "/process":
            from app.graph import run_clinicflow

            body = kwargs["json"]
            version = body.get("prompt_version") or ACTIVE_VERSION
            result = run_clinicflow(body["message"], version)
            row_id = log_request(result, version)
            return {
                "id": row_id,
                "prompt_version": version,
                "category": result.get("category"),
                "needs_human": bool(result.get("needs_human", False)),
                "reply": result.get("reply"),
                "staff_alert": result.get("staff_alert"),
                "details": result.get("details", {}),
                "retrieved_sections": result.get("retrieved_sections", []),
            }, None
    except RuntimeError as error:  # for example: the API key is missing
        return None, str(error)
    except Exception as error:
        return None, f"The AI workflow failed: {error}"
    return None, f"Unknown request: {method} {path}"


def call_backend(method: str, path: str, **kwargs):
    """Talk to the app. Returns (data, error_message)."""
    if not USE_API:
        return call_direct(method, path, **kwargs)

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

if USE_API:
    health, health_error = call_backend("GET", "/health")
    if health_error:
        st.sidebar.error("Backend: not reachable")
    else:
        st.sidebar.success("Backend: running (API mode)")
else:
    st.sidebar.success("All-in-one mode: no separate backend needed")

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
