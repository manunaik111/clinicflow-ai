"""
main.py: the FastAPI backend. It exposes the ClinicFlow workflow as a web API.

Endpoints:
    GET  /health     check that the server is running
    POST /process    run one patient message through the workflow and log it
    GET  /requests   recent processed messages (for the dashboard)
    GET  /stats      summary numbers (for the dashboard)

Start the server from the main clinicflow-ai folder:
    uvicorn app.main:app --reload

Then open http://127.0.0.1:8000/docs to try every endpoint in your browser.
"""

from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

from app.database import get_recent_requests, get_stats, init_db, log_request
from app.graph import run_clinicflow
from app.prompts import ACTIVE_VERSION, PROMPTS


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Runs once when the server starts: make sure the database table exists."""
    init_db()
    yield


app = FastAPI(
    title="ClinicFlow AI",
    description="AI-powered triage automation for patient messages (demo with synthetic data).",
    version="1.0.0",
    lifespan=lifespan,
)


# ----------------------------------------------------------------------
# Data shapes (Pydantic checks incoming and outgoing data automatically)
# ----------------------------------------------------------------------
class ProcessRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000, description="The patient's message")
    prompt_version: Optional[str] = Field(
        default=None, description="Prompt version to use, e.g. v1. Defaults to the active version."
    )


class ProcessResponse(BaseModel):
    id: int
    prompt_version: str
    category: Optional[str]
    needs_human: bool
    reply: Optional[str]
    staff_alert: Optional[str]
    details: dict
    retrieved_sections: list[str]


# ----------------------------------------------------------------------
# Endpoints
# ----------------------------------------------------------------------
@app.get("/health")
def health() -> dict:
    return {"status": "ok", "active_prompt_version": ACTIVE_VERSION}


@app.post("/process", response_model=ProcessResponse)
def process_message(body: ProcessRequest) -> ProcessResponse:
    version = body.prompt_version or ACTIVE_VERSION
    if version not in PROMPTS:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown prompt version '{version}'. Available: {list(PROMPTS)}",
        )

    try:
        result = run_clinicflow(body.message, version)
    except RuntimeError as error:
        # For example: an API key is missing from .env
        raise HTTPException(status_code=500, detail=str(error))
    except Exception as error:
        raise HTTPException(status_code=502, detail=f"The AI workflow failed: {error}")

    row_id = log_request(result, version)

    return ProcessResponse(
        id=row_id,
        prompt_version=version,
        category=result.get("category"),
        needs_human=bool(result.get("needs_human", False)),
        reply=result.get("reply"),
        staff_alert=result.get("staff_alert"),
        details=result.get("details", {}),
        retrieved_sections=result.get("retrieved_sections", []),
    )


@app.get("/requests")
def list_requests(limit: int = Query(50, ge=1, le=500)) -> list[dict]:
    return get_recent_requests(limit)


@app.get("/stats")
def stats() -> dict:
    return get_stats()
