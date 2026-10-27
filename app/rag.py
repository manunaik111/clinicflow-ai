"""
rag.py: the retrieval half of RAG (Retrieval-Augmented Generation).

What it does:
1. Splits clinic_faq.md into sections (one chunk per "##" heading).
2. Turns each section into an embedding (numbers that capture meaning) with Gemini.
3. Stores the sections in a Chroma vector database on disk.
4. Given a patient question, finds the most similar sections.

The "generation" half (Claude writing the answer from the retrieved text) happens
later in the workflow, using the faq_answer prompt from prompts.py.

Quick test from the main clinicflow-ai folder:
    python -m app.rag              (use the existing database, build it if empty)
    python -m app.rag --rebuild    (delete and rebuild after editing clinic_faq.md)
"""

import re
import sys
from functools import lru_cache

from app.config import CHROMA_DIR, COLLECTION_NAME, FAQ_PATH, get_embeddings


def load_faq_chunks() -> list[dict]:
    """Split clinic_faq.md into one chunk per '## Heading' section."""
    text = FAQ_PATH.read_text(encoding="utf-8")

    # Split wherever a line starts with "## ". The first piece is the title and
    # the fictional-clinic note, so we skip it.
    parts = re.split(r"^## ", text, flags=re.MULTILINE)

    chunks = []
    for part in parts[1:]:
        heading, _, body = part.partition("\n")
        heading = heading.strip()
        body = body.strip()
        # Keep the heading inside the text so the embedding knows the topic.
        chunks.append({"section": heading, "text": f"{heading}\n{body}"})
    return chunks


def build_vectorstore(rebuild: bool = False):
    """Open the Chroma database, and fill it from the FAQ if it is empty."""
    from langchain_chroma import Chroma

    store = Chroma(
        collection_name=COLLECTION_NAME,
        embedding_function=get_embeddings(),
        persist_directory=str(CHROMA_DIR),
    )

    if rebuild:
        store.reset_collection()

    # Only embed and store the FAQ if nothing is in the database yet.
    if len(store.get()["ids"]) == 0:
        chunks = load_faq_chunks()
        store.add_texts(
            texts=[c["text"] for c in chunks],
            metadatas=[{"section": c["section"]} for c in chunks],
            ids=[f"faq-{i}" for i in range(len(chunks))],
        )
    return store


@lru_cache(maxsize=1)
def get_vectorstore():
    """Open the database once and reuse it for every question."""
    return build_vectorstore()


def retrieve(question: str, k: int = 2) -> list[dict]:
    """Return the k FAQ sections most similar in meaning to the question.

    'distance' is how far apart the question and section are in meaning:
    SMALLER means a BETTER match.
    """
    results = get_vectorstore().similarity_search_with_score(question, k=k)
    return [
        {
            "section": doc.metadata["section"],
            "text": doc.page_content,
            "distance": round(float(score), 4),
        }
        for doc, score in results
    ]


def format_context(chunks: list[dict]) -> str:
    """Join retrieved sections into one block of text for the {context} placeholder."""
    return "\n\n".join(c["text"] for c in chunks)


if __name__ == "__main__":
    if "--rebuild" in sys.argv:
        build_vectorstore(rebuild=True)
        print(f"Rebuilt the vector database in {CHROMA_DIR}\n")

    demo_questions = [
        "How much does a standard consultation cost?",
        "What time do you open on Saturdays?",
        "Do you offer vaccinations for overseas travel?",
    ]
    for q in demo_questions:
        print(f"Question: {q}")
        for hit in retrieve(q):
            print(f"  - {hit['section']} (distance {hit['distance']})")
        print()
