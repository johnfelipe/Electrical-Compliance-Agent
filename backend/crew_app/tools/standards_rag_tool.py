"""Ferramenta RAG contra Supabase (usada pelo Agente Pesquisador)."""

from __future__ import annotations

import threading
from typing import Any

from crewai.tools import BaseTool
from pydantic import BaseModel, Field

from app.supabase_store import format_retrieval_for_agents, match_chunks

TRACE_LOCK = threading.Lock()
TRACE: dict[str, Any] = {"norms_touched": set(), "hits": []}


def reset_trace() -> None:
    with TRACE_LOCK:
        TRACE.clear()
        TRACE["norms_touched"] = set()
        TRACE["hits"] = []


class SearchStandardsInput(BaseModel):
    query: str = Field(..., description="Consulta técnica para buscar trechos das normas")
    norm_code: str = Field(
        default="",
        description='Filtrar por código de norma, ex.: "NBR 5410" ou vazio para todas',
    )
    match_count: int = Field(default=8, ge=1, le=24)


class SearchTechnicalStandardsTool(BaseTool):
    name: str = "search_technical_standards"
    description: str = (
        "Consulta semanticamente o armazém de normas técnicos (Supabase/pgvector). "
        "Use para recuperar apenas trechos reais antes de auditoria. "
        "Chame quando precisar de evidências de NBR/IEC."
    )
    args_schema: type[BaseModel] = SearchStandardsInput

    def _run(self, query: str, norm_code: str = "", match_count: int = 8) -> str:
        norm_filter = norm_code.strip() or None
        rows = match_chunks(query=query, match_count=int(match_count), norm_code=norm_filter)
        with TRACE_LOCK:
            for r in rows:
                if r.get("norm_code"):
                    TRACE["norms_touched"].add(str(r["norm_code"]))
            TRACE["hits"].append({"query": query, "norm_filter": norm_filter, "rows": rows})
        if not rows:
            return (
                "Nenhum trecho recuperado para esta consulta. "
                "Não invente itens/cláusulas; considere outra consulta ou marque evidência insuficiente."
            )
        return format_retrieval_for_agents(rows)

