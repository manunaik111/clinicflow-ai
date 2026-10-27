"""
evaluate.py: scores a prompt version against the labelled test messages.

It runs every message in data/test_messages.json through the classifier (the fast Groq model),
compares the answer with the expected category, and prints a report. The full
results are also saved to results/eval_<version>.csv as evidence for your project.

Run from the main clinicflow-ai folder:
    python -m app.evaluate                 (uses the active version in prompts.py)
    python -m app.evaluate --version v2    (test a specific version)
    python -m app.evaluate --heldout       (use the held-out messages instead)
"""

import argparse
import json
import time

import pandas as pd

from app.config import BASE_DIR, HELDOUT_MESSAGES_PATH, TEST_MESSAGES_PATH
from app.prompts import ACTIVE_VERSION
from app.state_and_llm_helpers import CATEGORIES, classify_raw, clean_category

RESULTS_DIR = BASE_DIR / "results"


def load_test_messages(path=TEST_MESSAGES_PATH) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return data["messages"]


def run_evaluation(version: str, messages: list[dict]) -> pd.DataFrame:
    """Classify every message in the list and return one row per message."""
    rows = []

    for i, item in enumerate(messages, start=1):
        try:
            raw_reply = classify_raw(item["message"], version)
            predicted = clean_category(raw_reply)
        except Exception as error:  # e.g. rate limit or network problem
            print(f"  ! {item['id']} failed to run: {error}")
            raw_reply = f"ERROR: {error}"
            predicted = "error"

        rows.append(
            {
                "id": item["id"],
                "message": item["message"],
                "expected": item["expected_category"],
                "predicted": predicted,
                "raw_reply": raw_reply,
                "correct": predicted == item["expected_category"],
                "notes": item["notes"],
            }
        )
        shown = f"got {predicted}" if predicted in CATEGORIES else f"got {predicted} (raw reply: {raw_reply!r})"
        print(f"  [{i}/{len(messages)}] {item['id']}: expected {item['expected_category']}, {shown}")
        time.sleep(0.3)  # small pause to avoid hitting API rate limits

    return pd.DataFrame(rows)


def print_report(df: pd.DataFrame, version: str) -> None:
    total = len(df)
    correct = int(df["correct"].sum())

    print("\n" + "=" * 70)
    print(f"RESULTS FOR PROMPT VERSION: {version}")
    print("=" * 70)
    print(f"Overall accuracy: {correct}/{total} = {correct / total:.1%}\n")

    # Accuracy for each category
    print("Accuracy by category:")
    by_category = df.groupby("expected")["correct"].agg(["sum", "count"])
    for category, row in by_category.iterrows():
        print(f"  {category:<12} {int(row['sum'])}/{int(row['count'])}")

    # Safety check 1: urgent messages that were NOT classified as urgent
    urgent = df[df["expected"] == "urgent"]
    missed = urgent[urgent["predicted"] != "urgent"]
    print(f"\nSAFETY: urgent messages caught: {len(urgent) - len(missed)}/{len(urgent)}")
    for _, row in missed.iterrows():
        print(f"  MISSED {row['id']} (classified as {row['predicted']}): {row['message'][:70]}")

    # Safety check 2: non-urgent messages wrongly flagged as urgent
    false_alarms = df[(df["predicted"] == "urgent") & (df["expected"] != "urgent")]
    print(f"\nFalse urgent alarms: {len(false_alarms)}")
    for _, row in false_alarms.iterrows():
        print(f"  {row['id']} (expected {row['expected']}): {row['message'][:70]}")

    # Format problems: answers that were not one of the five categories
    unknown = df[df["predicted"].isin(["unknown", "error"])]
    print(f"\nUnusable answers (unknown or error): {len(unknown)}")
    for _, row in unknown.iterrows():
        print(f"  {row['id']} raw model reply: {row['raw_reply']!r}")

    # All failures
    failures = df[~df["correct"]]
    print(f"\nAll failures ({len(failures)}):")
    for _, row in failures.iterrows():
        print(f"  {row['id']}: expected {row['expected']}, got {row['predicted']}")
        print(f"      {row['message'][:80]}")

    # Expected vs predicted table
    print("\nExpected (rows) vs predicted (columns):")
    print(pd.crosstab(df["expected"], df["predicted"]).to_string())


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate a ClinicFlow AI prompt version.")
    parser.add_argument("--version", default=ACTIVE_VERSION, help="prompt version, e.g. v1")
    parser.add_argument(
        "--heldout", action="store_true", help="use data/heldout_messages.json instead of the development set"
    )
    args = parser.parse_args()

    path = HELDOUT_MESSAGES_PATH if args.heldout else TEST_MESSAGES_PATH
    suffix = "_heldout" if args.heldout else ""
    label = f"{args.version} (held-out set)" if args.heldout else args.version
    messages = load_test_messages(path)

    print(f"Running {len(messages)} messages from {path.name} with prompt version {args.version}...\n")
    df = run_evaluation(args.version, messages)

    print_report(df, label)

    RESULTS_DIR.mkdir(exist_ok=True)
    output_path = RESULTS_DIR / f"eval_{args.version}{suffix}.csv"
    df.to_csv(output_path, index=False)
    print(f"\nFull results saved to {output_path}")


if __name__ == "__main__":
    main()
