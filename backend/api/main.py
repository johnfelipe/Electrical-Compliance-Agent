from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

load_dotenv(ROOT / ".env")

os.environ.setdefault("OPENAI_API_KEY", os.getenv("OPENAI_API_KEY", ""))
os.environ.setdefault("OPENAI_MODEL", os.getenv("OPENAI_MODEL", "gpt-4o-mini"))

from app.supabase_store import insert_audit  # noqa: E402
from crew_app.compliance_crew import kickoff_audit  # noqa: E402


app = FastAPI(title="The Electrical Compliance Agent API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv(
        "CORS_ORIGINS",
        "http://localhost:3000,http://127.0.0.1:3000",
    ).split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class AuditRequest(BaseModel):
    project_description: str = Field(..., min_length=10)


class AuditResponse(BaseModel):
    audit_id: str | None = None
    norms_touched: list[str]
    findings: list | None = None
    support_suggestions: list[dict] | None = None
    raw_report: str


def _is_rate_limit_error(exc: Exception) -> bool:
    message = str(exc).lower()
    return "rate limit" in message or "ratelimit" in message or "tokens per min" in message


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/audit", response_model=AuditResponse)
def audit(req: AuditRequest) -> AuditResponse:
    try:
        out = kickoff_audit(req.project_description)
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
    except Exception as e:
        if _is_rate_limit_error(e):
            raise HTTPException(
                status_code=429,
                detail=(
                    "O provedor de LLM atingiu o limite temporario de tokens por minuto. "
                    "Tente novamente em alguns segundos."
                ),
            ) from e
        raise HTTPException(status_code=500, detail=f"Crew falhou: {e!s}") from e

    norms = list(out.get("norms_touched") or [])
    findings = out.get("findings")
    support_suggestions = out.get("support_suggestions")
    raw = out.get("raw_report") or ""

    audit_id: str | None = None
    try:
        audit_id = insert_audit(
            user_input=req.project_description,
            normalized_summary=out.get("normalized_summary_estimate"),
            norms_touched=norms,
            findings=findings if isinstance(findings, list) else None,
            full_report=raw,
            agent_trace={
                "compliance_json": out.get("compliance_json"),
            },
        )
    except RuntimeError:
        audit_id = None

    return AuditResponse(
        audit_id=audit_id,
        norms_touched=norms,
        findings=findings if isinstance(findings, list) else None,
        support_suggestions=support_suggestions if isinstance(support_suggestions, list) else [],
        raw_report=raw,
    )
