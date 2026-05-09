from __future__ import annotations

import json
from typing import Any

from supabase import Client, create_client

from app.config import settings
from app.embeddings import embed_texts


def _to_pgvector(values: list[float]) -> str:
    # PostgREST compatibility: vector columns/RPC args are reliably accepted as string literals.
    return "[" + ",".join(f"{float(v):.8f}" for v in values) + "]"


def get_client() -> Client:
    if not settings.supabase_url or not settings.supabase_service_role_key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set")
    return create_client(settings.supabase_url, settings.supabase_service_role_key)


def match_chunks(
    query: str,
    match_count: int = 8,
    norm_code: str | None = None,
) -> list[dict[str, Any]]:
    client = get_client()
    qv = embed_texts([query])[0]
    payload = {
        "query_embedding": _to_pgvector(qv),
        "match_count": match_count,
        "filter_norm_code": norm_code,
    }
    res = client.rpc("match_doc_chunks", payload).execute()
    return list(res.data or [])


def insert_audit(
    user_input: str,
    normalized_summary: dict | None,
    norms_touched: list[str],
    findings: list | None,
    full_report: str,
    agent_trace: dict | None = None,
) -> str:
    client = get_client()
    row = {
        "user_input": user_input,
        "normalized_summary": normalized_summary,
        "norms_touched": norms_touched,
        "findings": findings,
        "full_report": full_report,
        "agent_trace": agent_trace,
    }
    ins = client.table("project_audits").insert(row).execute()
    if not ins.data:
        raise RuntimeError("Failed to insert project_audits")
    return str(ins.data[0]["id"])


def format_retrieval_for_agents(rows: list[dict[str, Any]]) -> str:
    parts: list[str] = []
    for i, r in enumerate(rows, 1):
        meta = r.get("metadata") or {}
        if isinstance(meta, str):
            try:
                meta = json.loads(meta)
            except json.JSONDecodeError:
                meta = {}
        sim = r.get("similarity")
        sim_text = f"{float(sim):.4f}" if sim is not None else "n/a"
        parts.append(
            f"[{i}] norm={r.get('norm_code')} similarity={sim_text}\n"
            f"metadata={meta}\n"
            f"content:\n{r.get('content', '')}"
        )
    return "\n\n---\n\n".join(parts) if parts else "(nenhum trecho recuperado no Supabase)"
