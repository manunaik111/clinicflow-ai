"""
config.py: loads settings from the .env file and creates the AI model connections.

Every other file gets its settings and models from here, so keys and model
names are managed in exactly one place.

All language models run on Groq. Embeddings (for the FAQ search) run locally,
so no extra API key is needed for them.
"""

import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

# ----------------------------------------------------------------------
# Paths
# ----------------------------------------------------------------------
# BASE_DIR is the main clinicflow-ai folder (one level above this app/ folder).
BASE_DIR = Path(__file__).resolve().parent.parent

# Read the .env file in the main folder. If it is missing, nothing breaks here;
# the model functions below will give a clear error when a key is needed.
load_dotenv(BASE_DIR / ".env")

FAQ_PATH = BASE_DIR / "data" / "clinic_faq.md"
TEST_MESSAGES_PATH = BASE_DIR / "data" / "test_messages.json"
HELDOUT_MESSAGES_PATH = BASE_DIR / "data" / "heldout_messages.json"

# ----------------------------------------------------------------------
# Settings from .env (with safe defaults where that makes sense)
# ----------------------------------------------------------------------
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# Small, fast model: used for quick structured tasks (classify, extract).
GROQ_FAST_MODEL = os.getenv("GROQ_FAST_MODEL", "llama-3.1-8b-instant")
# Larger model: used for careful writing and judgment (answers, replies, escalation).
GROQ_SMART_MODEL = os.getenv("GROQ_SMART_MODEL", "llama-3.3-70b-versatile")

BACKEND_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:8000")

# If DATABASE_PATH is relative (like "clinicflow.db"), place it inside the project folder.
_db_path = Path(os.getenv("DATABASE_PATH", "clinicflow.db"))
DATABASE_PATH = _db_path if _db_path.is_absolute() else BASE_DIR / _db_path

# Chroma vector database: stored in a local folder and rebuilt from clinic_faq.md if empty.
CHROMA_DIR = BASE_DIR / os.getenv("CHROMA_DIR", "chroma_db")
COLLECTION_NAME = "clinic_faq"


def _require_key(name: str, value: str | None) -> str:
    """Stop with a friendly message if a needed API key is missing or still a placeholder."""
    if not value or value.startswith("your-"):
        raise RuntimeError(
            f"{name} is missing. Copy .env.example to .env and add your real key."
        )
    return value


# ----------------------------------------------------------------------
# Model connections
# ----------------------------------------------------------------------
# @lru_cache means each connection is created once and then reused.
# Imports are inside the functions so the app can start (and show the friendly
# error above) even before every library or key is ready.

@lru_cache(maxsize=None)
def get_fast_llm(temperature: float = 0.0):
    """Fast Groq model: used for structured tasks (classify, extract).

    Temperature 0 makes the output as consistent as possible.
    """
    from langchain_groq import ChatGroq

    return ChatGroq(
        model=GROQ_FAST_MODEL,
        api_key=_require_key("GROQ_API_KEY", GROQ_API_KEY),
        temperature=temperature,
    )


@lru_cache(maxsize=None)
def get_smart_llm(temperature: float = 0.3):
    """Larger Groq model: used for writing and judgment (FAQ answers, replies, escalation)."""
    from langchain_groq import ChatGroq

    return ChatGroq(
        model=GROQ_SMART_MODEL,
        api_key=_require_key("GROQ_API_KEY", GROQ_API_KEY),
        temperature=temperature,
        max_tokens=1024,
    )


@lru_cache(maxsize=None)
def get_embeddings():
    """Local embedding model that ships with Chroma.

    It turns text into numbers so we can search the FAQ by meaning. It runs on
    your own computer (no API key). The first use downloads a small model file.
    """
    from chromadb.utils.embedding_functions import DefaultEmbeddingFunction
    from langchain_core.embeddings import Embeddings

    class LocalEmbeddings(Embeddings):
        """Adapter so LangChain's Chroma wrapper can use Chroma's own embedder."""

        def __init__(self) -> None:
            self._embed = DefaultEmbeddingFunction()

        def embed_documents(self, texts: list[str]) -> list[list[float]]:
            return [[float(x) for x in vector] for vector in self._embed(texts)]

        def embed_query(self, text: str) -> list[float]:
            return self.embed_documents([text])[0]

    return LocalEmbeddings()
