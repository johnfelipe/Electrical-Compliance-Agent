from __future__ import annotations

import json
import re
from typing import Any

from crewai import Agent, Crew, Process, Task
from langchain_openai import ChatOpenAI

from app.config import settings
from crew_app.tools.component_support_tool import get_component_suggestions_payload
from crew_app.tools.standards_rag_tool import (
    TRACE,
    TRACE_LOCK,
    SearchTechnicalStandardsTool,
    reset_trace,
)


def build_llm() -> ChatOpenAI:
    api_key = settings.openai_api_key
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is required to run compliance crew")
    return ChatOpenAI(
        api_key=api_key,
        model=settings.openai_model,
        temperature=0.1,
        max_retries=3,
    )


def extract_balanced_json_objects(text: str) -> list[dict[str, Any]]:
    objects: list[dict[str, Any]] = []
    for match in re.finditer(r"{", text):
        start = match.start()
        depth = 0
        in_string = False
        escaped = False
        for idx in range(start, len(text)):
            ch = text[idx]
            if in_string:
                if escaped:
                    escaped = False
                elif ch == "\\":
                    escaped = True
                elif ch == '"':
                    in_string = False
                continue
            if ch == '"':
                in_string = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    candidate = text[start : idx + 1]
                    try:
                        obj = json.loads(candidate)
                    except json.JSONDecodeError:
                        break
                    if isinstance(obj, dict):
                        objects.append(obj)
                    break
    return objects


def extract_task_output(task: Task) -> str:
    output = getattr(task, "output", None)
    if output is None:
        return ""
    raw = getattr(output, "raw", None)
    if isinstance(raw, str):
        return raw
    return str(output)


def extract_json_from_text(text: str) -> dict[str, Any] | None:
    for obj in reversed(extract_balanced_json_objects(text)):
        return obj
    return None


def extract_compliance_json(text: str) -> tuple[list | None, dict | None]:
    marker = "COMPLIANCE_JSON"
    idx = text.rfind(marker)
    if idx == -1:
        return None, None
    tail = text[idx:]

    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", tail, flags=re.DOTALL)
    if fenced:
        candidate = fenced.group(1)
        try:
            obj = json.loads(candidate)
            if isinstance(obj, dict) and isinstance(obj.get("findings"), list):
                return obj["findings"], obj
        except json.JSONDecodeError:
            pass

    for obj in reversed(extract_balanced_json_objects(tail)):
        findings = obj.get("findings")
        if isinstance(findings, list):
            return findings, obj
    return None, None


def _normalize_text(text: str | None) -> str:
    return re.sub(r"\s+", " ", str(text or "").strip()).lower()


def _metadata_as_text(meta: Any) -> str:
    if isinstance(meta, str):
        return meta
    try:
        return json.dumps(meta or {}, ensure_ascii=False, sort_keys=True)
    except TypeError:
        return str(meta)


def _text_supported(candidate: str | None, haystacks: list[str]) -> bool:
    needle = _normalize_text(candidate)
    if len(needle) < 12:
        return False
    return any(needle in _normalize_text(haystack) for haystack in haystacks)


def _trace_rows() -> list[dict[str, Any]]:
    with TRACE_LOCK:
        hits = list(TRACE.get("hits") or [])
    rows: list[dict[str, Any]] = []
    for hit in hits:
        for row in hit.get("rows") or []:
            if isinstance(row, dict):
                rows.append(row)
    return rows


def enforce_evidence_guardrails(
    findings: list | None,
    retrieved_rows: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    candidate_rows = retrieved_rows if retrieved_rows is not None else _trace_rows()
    evidence_texts = [str(row.get("content") or "") for row in candidate_rows]
    metadata_texts = [_metadata_as_text(row.get("metadata")) for row in candidate_rows]
    kept: list[dict[str, Any]] = []

    for finding in findings or []:
        if not isinstance(finding, dict):
            continue

        item = dict(finding)
        severity = str(item.get("severity") or "low").lower()
        if severity not in {"low", "medium", "high"}:
            severity = "low"
        item["severity"] = severity

        quote = item.get("evidence_quote_or_none")
        clause_ref = item.get("evidence_clause_ref_or_none")

        quote_ok = _text_supported(str(quote) if quote is not None else None, evidence_texts)
        clause_ok = _text_supported(
            str(clause_ref) if clause_ref is not None else None,
            evidence_texts + metadata_texts,
        )

        if not quote_ok:
            item["evidence_quote_or_none"] = None
        if not clause_ok:
            item["evidence_clause_ref_or_none"] = None

        if severity in {"medium", "high"} and not quote_ok:
            continue
        kept.append(item)

    if kept:
        return kept

    if findings:
        return [
            {
                "severity": "low",
                "title": "Evidencia normativa insuficiente",
                "detail": (
                    "A busca recuperou contexto insuficiente para afirmar nao conformidades "
                    "com seguranca. Revise as consultas RAG ou amplie o corpus indexado."
                ),
                "evidence_clause_ref_or_none": None,
                "evidence_quote_or_none": None,
            }
        ]

    return []


def build_support_suggestions(findings: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    support_by_finding: list[dict[str, Any]] = []

    for finding in findings or []:
        if not isinstance(finding, dict):
            continue
        severity = str(finding.get("severity") or "").lower()
        if severity not in {"medium", "high"}:
            continue

        need_summary = {
            "title": finding.get("title"),
            "detail": finding.get("detail"),
        }
        payload = get_component_suggestions_payload(need_summary)
        suggestions = payload.get("suggestions") or []

        if suggestions:
            notes = (
                "Sugestoes obtidas da camada mock de componentes para demonstracao estavel."
            )
            status = "suggested"
        else:
            notes = (
                "Sem substituto compativel no catalogo mock atual. O finding permanece no relatorio."
            )
            status = "skipped"

        support_by_finding.append(
            {
                "finding_title": finding.get("title"),
                "status": status,
                "notes": notes,
                "suggestions": suggestions,
            }
        )

    return support_by_finding


def render_support_json(support_by_finding: list[dict[str, Any]]) -> str:
    payload = {
        "support_by_finding": support_by_finding,
        "source": "mock_catalog",
    }
    return "SUPPORT_JSON: " + json.dumps(payload, ensure_ascii=False)


def kickoff_audit(project_description: str) -> dict[str, Any]:
    reset_trace()
    llm = build_llm()
    rag_tool = SearchTechnicalStandardsTool()

    triador = Agent(
        role="Agente Triador",
        goal="Organizar input do projeto em dados auditaveis sem extrapolar dados ausentes.",
        backstory="Voce e um engenheiro senior e prepara um briefing tecnico claro.",
        verbose=True,
        llm=llm,
    )

    pesquisador = Agent(
        role="Agente Pesquisador (RAG)",
        goal="Recuperar evidencias no Supabase via ferramenta e consolidar somente trechos reais.",
        backstory="Voce e um consultor de normas e nao escreve clausulas sem evidencia recuperada.",
        verbose=True,
        llm=llm,
        tools=[rag_tool],
        allow_delegation=False,
    )

    auditor = Agent(
        role="Agente Auditor de Conformidade",
        goal="Emitir parecer com severidade e evidencias somente quando elas estiverem no contexto recuperado.",
        backstory=(
            "Voce prioriza seguranca eletrica e falha de forma conservadora quando a evidencia for insuficiente."
        ),
        verbose=True,
        llm=llm,
        allow_delegation=False,
    )

    t1 = Task(
        description=(
            "Normalize o seguinte texto de projeto para auditoria:\n\n"
            f"{project_description}\n\n"
            "Entregue JSON com campos "
            "{'summary_pt','equipment','voltages_kw_if_any','conductors_breakers_if_any','uncertainties'}.\n"
            "Se algo nao esta explicito, liste em uncertainties e nao invente."
        ),
        expected_output="JSON valido apenas, sem texto fora do JSON.",
        agent=triador,
    )

    t2 = Task(
        description=(
            "Use a ferramenta search_technical_standards para recuperar somente evidencias "
            "realmente relacionadas ao briefing do Triador. Se a ferramenta nao trouxer "
            "trechos suficientes, declare EVIDENCE_GAP em vez de completar com conhecimento "
            "geral. Se necessario faca varias chamadas com consultas diferentes. "
            "Ao final escreva um resumo objetivo apenas com base nos trechos retornados."
        ),
        expected_output=(
            "(1) Log breve das consultas realizadas a ferramenta. "
            "(2) Lista de trechos copiados apenas quando relevantes."
        ),
        agent=pesquisador,
        context=[t1],
    )

    t3 = Task(
        description=(
            "Com base apenas no briefing do Triador e nas evidencias do Pesquisador, "
            "produza um relatorio de conformidade.\n\n"
            "- findings: lista de objetos "
            "{severity(low|medium|high),title,detail,evidence_clause_ref_or_none,evidence_quote_or_none}\n"
            "- Para qualquer finding medium/high, evidence_quote_or_none e obrigatorio e deve "
            "ser uma citacao curta copiada dos trechos recuperados.\n"
            "- So use evidence_clause_ref_or_none quando a referencia estiver textualmente nos trechos.\n"
            "- Se nao houver quote verificavel, nao emita nao conformidade medium/high.\n\n"
            "No final imprima tambem o JSON inteiro precedido pela linha exata COMPLIANCE_JSON:"
        ),
        expected_output=(
            "Relatorio em portugues seguido de uma linha 'COMPLIANCE_JSON:' "
            "e entao um JSON valido com a estrutura descrita."
        ),
        agent=auditor,
        context=[t1, t2],
    )

    crew = Crew(
        agents=[triador, pesquisador, auditor],
        tasks=[t1, t2, t3],
        process=Process.sequential,
        verbose=True,
    )

    result = crew.kickoff()
    final_raw = str(result)
    triage_raw = extract_task_output(t1)
    compliance_raw = extract_task_output(t3)

    with TRACE_LOCK:
        norms = sorted(str(n) for n in (TRACE.get("norms_touched") or set()))

    findings, compliance_obj = extract_compliance_json(compliance_raw or final_raw)
    guarded_findings = enforce_evidence_guardrails(findings)
    if compliance_obj is not None:
        compliance_obj["findings"] = guarded_findings

    support_suggestions = build_support_suggestions(guarded_findings)
    support_raw = render_support_json(support_suggestions)
    normalized_summary = extract_json_from_text(triage_raw)
    combined_report = "\n\n".join(
        block
        for block in [triage_raw, compliance_raw, support_raw]
        if isinstance(block, str) and block.strip()
    ) or final_raw

    return {
        "raw_report": combined_report,
        "norms_touched": norms,
        "findings": guarded_findings,
        "support_suggestions": support_suggestions,
        "compliance_json": compliance_obj,
        "normalized_summary_estimate": normalized_summary,
    }
