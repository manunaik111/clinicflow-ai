"""
state_and_llm_helpers.py: two things the LangGraph workflow needs.

1. ClinicState: the "folder" of information that travels through the workflow.
2. Helper functions: one small function per AI task. Each one fills a prompt from
   prompts.py, calls the right model (the fast or the larger Groq model), and cleans up the answer.

The graph (next file) will simply call these helpers from its nodes.

Quick key check from the main clinicflow-ai folder:
    python -m app.state_and_llm_helpers
"""

import json
import re
from typing import Optional, TypedDict

from app.config import get_fast_llm, get_smart_llm
from app.prompts import ACTIVE_VERSION, get_prompts

# The only categories the classifier is allowed to return.
CATEGORIES = ["booking", "reschedule", "billing_faq", "refill", "urgent"]


# ----------------------------------------------------------------------
# 1. Workflow state
# ----------------------------------------------------------------------
class ClinicState(TypedDict, total=False):
    """Everything we learn about one patient message as it moves through the workflow.

    total=False means a field can be missing until a node fills it in.
    """

    message: str                    # the patient's original message
    prompt_version: str             # which prompt version to use (v1, v2, ...)
    category: str                   # booking / reschedule / billing_faq / refill / urgent / unknown
    details: dict                   # extracted name, date/time, medication, symptoms
    retrieved_sections: list        # FAQ sections found by the RAG step
    reply: str                      # the final reply for the patient
    staff_alert: Optional[str]      # note for clinic staff (urgent cases)
    needs_human: bool               # True when a human must take over


# ----------------------------------------------------------------------
# Small utilities
# ----------------------------------------------------------------------
def _text(response) -> str:
    """Get plain text out of a model response.

    Some models return a simple string, others return a list of content blocks.
    This handles both.
    """
    content = response.content
    if isinstance(content, str):
        return content.strip()

    parts = []
    for block in content:
        if isinstance(block, str):
            parts.append(block)
        elif isinstance(block, dict) and block.get("type") == "text":
            parts.append(block.get("text", ""))
    return "".join(parts).strip()


def _parse_json(text: str) -> dict:
    """Turn the model's JSON answer into a Python dict.

    Models sometimes wrap JSON in ```json fences. We strip those, then try to parse.
    If parsing fails we return an error marker instead of crashing, so the failure
    shows up in our tests.
    """
    cleaned = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.MULTILINE).strip()
    try:
        result = json.loads(cleaned)
        return result if isinstance(result, dict) else {"parse_error": True, "raw": text}
    except json.JSONDecodeError:
        return {"parse_error": True, "raw": text}


# ----------------------------------------------------------------------
# 2. AI task helpers (one per workflow step)
# ----------------------------------------------------------------------
def classify_raw(message: str, version: str = ACTIVE_VERSION) -> str:
    """Fast model: return its exact reply to the classify prompt, before any cleaning."""
    prompt = get_prompts(version)["classify"].format(message=message)
    return _text(get_fast_llm().invoke(prompt))


def clean_category(raw_reply: str) -> str:
    """Turn the model's reply into a category.

    We only accept an answer that is EXACTLY one of the five categories (ignoring
    capitals, spaces and punctuation). Anything else becomes "unknown" so wrong
    formats are counted as failures in testing.
    """
    cleaned = raw_reply.lower().strip().strip(".,!\"'` ")
    return cleaned if cleaned in CATEGORIES else "unknown"


def classify_message(message: str, version: str = ACTIVE_VERSION) -> str:
    """Fast model: decide which category the message belongs to."""
    return clean_category(classify_raw(message, version))


def extract_details(message: str, version: str = ACTIVE_VERSION) -> dict:
    """Fast model: pull out name, preferred date/time, medication and symptoms as a dict."""
    prompt = get_prompts(version)["extract"].format(message=message)
    return _parse_json(_text(get_fast_llm().invoke(prompt)))


def answer_faq(message: str, context: str, version: str = ACTIVE_VERSION) -> str:
    """Larger model: answer a question using the clinic information found by the RAG step."""
    prompt = get_prompts(version)["faq_answer"].format(message=message, context=context)
    return _text(get_smart_llm().invoke(prompt))


def draft_reply(message: str, category: str, details: dict, version: str = ACTIVE_VERSION) -> str:
    """Larger model: write a short, polite reply for booking, reschedule or refill messages."""
    prompt = get_prompts(version)["draft_reply"].format(
        message=message, category=category, details=json.dumps(details)
    )
    return _text(get_smart_llm().invoke(prompt))


def escalate_urgent(message: str, version: str = ACTIVE_VERSION) -> str:
    """Larger model: write the emergency advice for the patient and a one-line staff alert."""
    prompt = get_prompts(version)["escalate"].format(message=message)
    return _text(get_smart_llm().invoke(prompt))


# ----------------------------------------------------------------------
# Quick check that your API keys and model names work
# ----------------------------------------------------------------------
if __name__ == "__main__":
    samples = [
        "Hi, I'd like to book a general check-up for next week.",
        "How much does a standard consultation cost?",
        "I've had crushing chest pain since this morning. Can I get an appointment this week?",
    ]
    for sample in samples:
        print(f"Message : {sample}")
        print(f"Category: {classify_message(sample)}\n")
