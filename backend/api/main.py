from __future__ import annotations

import json
import os
import queue
import sys
import threading
from pathlib import Path
from typing import Any, Generator

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

load_dotenv(ROOT / ".env")

os.environ.setdefault("OPENAI_API_KEY", os.getenv("OPENAI_API_KEY", ""))
os.environ.setdefault("OPENAI_MODEL", os.getenv("OPENAI_MODEL", "gpt-4o-mini"))

from app.supabase_store import insert_audit  # noqa: E402
from crew_app.compliance_crew import kickoff_audit  # noqa: E402

AGENT_STEPS = [
    {"step": 1, "agent": "Triador", "message": "Normalizando dados do projeto..."},
    {"step": 2, "agent": "Pesquisador", "message": "Buscando evidencias nas normas..."},
    {"step": 3, "agent": "Auditor", "message": "Gerando relatorio de conformidade..."},
]


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


def _build_audit_response(
    req_description: str, out: dict[str, Any]
) -> dict[str, Any]:
    norms = list(out.get("norms_touched") or [])
    findings = out.get("findings")
    support_suggestions = out.get("support_suggestions")
    raw = out.get("raw_report") or ""

    audit_id: str | None = None
    try:
        audit_id = insert_audit(
            user_input=req_description,
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

    return {
        "audit_id": audit_id,
        "norms_touched": norms,
        "findings": findings if isinstance(findings, list) else None,
        "support_suggestions": (
            support_suggestions if isinstance(support_suggestions, list) else []
        ),
        "raw_report": raw,
    }


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

    return AuditResponse(**_build_audit_response(req.project_description, out))


def _sse_event(event: str, data: Any) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@app.post("/audit/stream")
async def audit_stream(req: AuditRequest, request: Request) -> StreamingResponse:
    progress_q: queue.Queue[dict[str, Any]] = queue.Queue()
    completed_step = 0

    def task_callback(output: Any) -> None:
        nonlocal completed_step
        completed_step += 1
        step_info = (
            AGENT_STEPS[completed_step - 1]
            if completed_step <= len(AGENT_STEPS)
            else {"step": completed_step, "agent": "unknown", "message": ""}
        )
        progress_q.put({"type": "step_done", **step_info})
        if completed_step < len(AGENT_STEPS):
            next_info = AGENT_STEPS[completed_step]
            progress_q.put({"type": "step_start", **next_info})

    def run_crew() -> None:
        try:
            progress_q.put({"type": "step_start", **AGENT_STEPS[0]})
            out = kickoff_audit(
                req.project_description, task_callback=task_callback
            )
            progress_q.put(
                {"type": "step_start", "step": 4, "agent": "Finalizacao",
                 "message": "Salvando auditoria..."}
            )
            response_data = _build_audit_response(req.project_description, out)
            progress_q.put({"type": "result", "data": response_data})
        except Exception as exc:
            detail = str(exc)
            if _is_rate_limit_error(exc):
                detail = (
                    "O provedor de LLM atingiu o limite temporario de tokens "
                    "por minuto. Tente novamente em alguns segundos."
                )
            progress_q.put({"type": "error", "detail": detail})

    thread = threading.Thread(target=run_crew, daemon=True)
    thread.start()

    def event_generator() -> Generator[str, None, None]:
        while True:
            if not thread.is_alive() and progress_q.empty():
                break
            try:
                msg = progress_q.get(timeout=2)
            except queue.Empty:
                yield _sse_event("ping", {})
                continue

            msg_type = msg.pop("type", "unknown")
            if msg_type == "result":
                yield _sse_event("result", msg["data"])
                break
            if msg_type == "error":
                yield _sse_event("error", {"detail": msg.get("detail", "")})
                break
            yield _sse_event(msg_type, msg)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
