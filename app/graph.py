"""
graph.py: the LangGraph workflow, the heart of ClinicFlow AI.

How a message flows:

    patient message
          |
      [classify]  (Gemini)
          |
          +-- urgent ---------------> [escalate] ----------> END
          +-- billing_faq ----------> [rag_answer] ---------> END
          +-- booking / reschedule /
          |   refill ---------------> [extract] -> [draft_reply] -> END
          +-- anything else
              (unknown) ------------> [human_handoff] ------> END

Quick test from the main clinicflow-ai folder:
    python -m app.graph
"""

from functools import lru_cache

from langgraph.graph import END, StateGraph

from app.prompts import ACTIVE_VERSION
from app.rag import format_context, retrieve
from app.state_and_llm_helpers import (
    ClinicState,
    answer_faq,
    classify_message,
    draft_reply,
    escalate_urgent,
    extract_details,
)


def _version(state: ClinicState) -> str:
    """Which prompt version this run should use."""
    return state.get("prompt_version", ACTIVE_VERSION)


# ----------------------------------------------------------------------
# Nodes: each one does one job and returns ONLY the state fields it changes.
# ----------------------------------------------------------------------
def classify_node(state: ClinicState) -> dict:
    category = classify_message(state["message"], _version(state))
    return {"category": category}


def extract_node(state: ClinicState) -> dict:
    details = extract_details(state["message"], _version(state))
    return {"details": details}


def rag_answer_node(state: ClinicState) -> dict:
    # 1. Retrieve: find the FAQ sections closest in meaning to the question.
    chunks = retrieve(state["message"])
    context = format_context(chunks)
    # 2. Generate: Claude answers using only that clinic information.
    reply = answer_faq(state["message"], context, _version(state))
    return {
        "retrieved_sections": [c["section"] for c in chunks],
        "reply": reply,
        "needs_human": False,
    }


def draft_reply_node(state: ClinicState) -> dict:
    reply = draft_reply(
        state["message"], state["category"], state.get("details", {}), _version(state)
    )
    return {"reply": reply, "needs_human": False}


def escalate_node(state: ClinicState) -> dict:
    reply = escalate_urgent(state["message"], _version(state))
    return {
        "reply": reply,
        "staff_alert": f"URGENT patient message: {state['message']}",
        "needs_human": True,
    }


def human_handoff_node(state: ClinicState) -> dict:
    """Safety net: if the category is unclear, a human reviews it. No guessing."""
    return {
        "reply": (
            "Thank you for your message. A member of our clinic staff will review it "
            "and contact you shortly. If this is an emergency, please call your local "
            "emergency number immediately."
        ),
        "staff_alert": f"Message could not be classified, please review: {state['message']}",
        "needs_human": True,
    }


# ----------------------------------------------------------------------
# Routing rule: which node comes after classification?
# ----------------------------------------------------------------------
def route_after_classify(state: ClinicState) -> str:
    category = state.get("category")
    if category == "urgent":
        return "escalate"
    if category == "billing_faq":
        return "rag_answer"
    if category in ("booking", "reschedule", "refill"):
        return "extract"
    return "human_handoff"


# ----------------------------------------------------------------------
# Build the graph
# ----------------------------------------------------------------------
def build_graph():
    graph = StateGraph(ClinicState)

    graph.add_node("classify", classify_node)
    graph.add_node("extract", extract_node)
    graph.add_node("rag_answer", rag_answer_node)
    graph.add_node("draft_reply", draft_reply_node)
    graph.add_node("escalate", escalate_node)
    graph.add_node("human_handoff", human_handoff_node)

    graph.set_entry_point("classify")

    graph.add_conditional_edges(
        "classify",
        route_after_classify,
        {
            "escalate": "escalate",
            "rag_answer": "rag_answer",
            "extract": "extract",
            "human_handoff": "human_handoff",
        },
    )

    graph.add_edge("extract", "draft_reply")
    for final_node in ("draft_reply", "rag_answer", "escalate", "human_handoff"):
        graph.add_edge(final_node, END)

    return graph.compile()


@lru_cache(maxsize=1)
def get_graph():
    """Build the workflow once and reuse it."""
    return build_graph()


def run_clinicflow(message: str, version: str = ACTIVE_VERSION) -> dict:
    """Process one patient message and return the final state as a dictionary."""
    return get_graph().invoke({"message": message, "prompt_version": version})


if __name__ == "__main__":
    samples = [
        "Hi, I'd like to book a general check-up for next week. Mornings work best. - Priya Nair",
        "How much does a standard consultation cost?",
        "I've had crushing chest pain since this morning. Can I get an appointment this week?",
    ]
    for sample in samples:
        result = run_clinicflow(sample)
        print(f"Message     : {sample}")
        print(f"Category    : {result.get('category')}")
        print(f"Needs human : {result.get('needs_human')}")
        print(f"Reply       : {result.get('reply')}")
        print("-" * 60)
