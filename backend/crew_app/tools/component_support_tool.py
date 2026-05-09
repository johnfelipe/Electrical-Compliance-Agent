"""Stable mock catalog for demo support recommendations."""

from __future__ import annotations

import json
import re
import unicodedata
from typing import Any

from crewai.tools import BaseTool
from pydantic import BaseModel, Field

MOCK_CATALOG = [
    {
        "sku": "DISJ-DIN-10A-B",
        "description": "Disjuntor termomagnetico monopolar 10A curva B (6kA)",
        "technical_specs": "Indicado para circuitos de iluminacao e cargas resistivas.",
        "typical_notes": "Usar quando o circuito pedir corrente baixa e curva B.",
        "categories": ["breaker"],
        "keywords": ["disjuntor", "curva b", "10a", "iluminacao", "protecao"],
    },
    {
        "sku": "DISJ-DIN-20A-C",
        "description": "Disjuntor termomagnetico monopolar 20A curva C (10kA)",
        "technical_specs": "Indicado para TUGs e pequenos motores.",
        "typical_notes": "Adequado para partidas moderadas sem disparo intempestivo.",
        "categories": ["breaker"],
        "keywords": ["disjuntor", "curva c", "20a", "tug", "motor", "protecao"],
    },
    {
        "sku": "DISJ-DIN-32A-C",
        "description": "Disjuntor termomagnetico monopolar 32A curva C",
        "technical_specs": "Capacidade nominal de 32A para circuitos dedicados.",
        "typical_notes": "Verificar coordenacao com cabo de 4 mm2 ou 6 mm2.",
        "categories": ["breaker"],
        "keywords": ["disjuntor", "curva c", "32a", "chuveiro", "ar condicionado", "coordenacao"],
    },
    {
        "sku": "DISJ-DIN-40A-C",
        "description": "Disjuntor termomagnetico monopolar 40A curva C",
        "technical_specs": "Indicado para cargas elevadas em 220V.",
        "typical_notes": "Usar quando o circuito pedir protecao para corrente nominal mais alta.",
        "categories": ["breaker"],
        "keywords": ["disjuntor", "curva c", "40a", "chuveiro", "220v", "coordenacao"],
    },
    {
        "sku": "DR-30MA-2P-40A",
        "description": "Interruptor diferencial residual 2P 40A 30mA",
        "technical_specs": "Sensibilidade de 30mA para protecao contra fuga de corrente.",
        "typical_notes": "Uso tipico em banheiros, cozinhas e areas molhadas.",
        "categories": ["dr"],
        "keywords": ["dr", "idr", "diferencial", "residual", "30ma", "banheiro", "cozinha", "fuga", "choque"],
    },
    {
        "sku": "CABO-FLEX-1.5-BR",
        "description": "Cabo flexivel PVC 750V 1,5 mm2 branco",
        "technical_specs": "Capacidade tipica em torno de 15,5A em metodo B1.",
        "typical_notes": "Uso tipico em circuitos de iluminacao.",
        "categories": ["cable"],
        "keywords": ["cabo", "condutor", "bitola", "1.5mm2", "1,5mm2", "iluminacao"],
    },
    {
        "sku": "CABO-FLEX-2.5-AZ",
        "description": "Cabo flexivel PVC 750V 2,5 mm2 azul",
        "technical_specs": "Capacidade tipica entre 21A e 24A em metodo B1.",
        "typical_notes": "Bitola comum para circuitos de tomadas de uso geral.",
        "categories": ["cable"],
        "keywords": ["cabo", "condutor", "bitola", "2.5mm2", "2,5mm2", "tug", "tomada"],
    },
    {
        "sku": "CABO-FLEX-4.0-PR",
        "description": "Cabo flexivel PVC 750V 4,0 mm2 preto",
        "technical_specs": "Capacidade tipica entre 28A e 32A em metodo B1.",
        "typical_notes": "Uso comum em circuitos dedicados leves.",
        "categories": ["cable"],
        "keywords": ["cabo", "condutor", "bitola", "4.0mm2", "4,0mm2", "tue", "coordenacao"],
    },
    {
        "sku": "CABO-FLEX-6.0-VD",
        "description": "Cabo flexivel PVC 750V 6,0 mm2 verde",
        "technical_specs": "Capacidade tipica entre 36A e 41A em metodo B1.",
        "typical_notes": "Uso comum em circuitos com cargas mais altas, como chuveiro.",
        "categories": ["cable"],
        "keywords": ["cabo", "condutor", "bitola", "6.0mm2", "6,0mm2", "chuveiro", "terra"],
    },
    {
        "sku": "CABO-FLEX-10.0-PR",
        "description": "Cabo flexivel PVC 750V 10,0 mm2 preto",
        "technical_specs": "Capacidade tipica entre 50A e 57A em metodo B1.",
        "typical_notes": "Uso comum para alimentacao de quadros ou cargas muito altas.",
        "categories": ["cable"],
        "keywords": ["cabo", "condutor", "bitola", "10.0mm2", "10,0mm2", "quadro", "alimentacao"],
    },
]

CATEGORY_HINTS = {
    "dr": [
        "dr",
        "idr",
        "diferencial",
        "residual",
        "30ma",
        "fuga",
        "choque",
        "banheiro",
        "cozinha",
        "area molhada",
        "area umida",
    ],
    "breaker": [
        "disjuntor",
        "curva",
        "sobrecarga",
        "curto",
        "coordenacao",
        "seletividade",
    ],
    "cable": [
        "cabo",
        "condutor",
        "bitola",
        "secao",
        "mm2",
        "fio",
    ],
}


def _normalize_text(text: Any) -> str:
    value = unicodedata.normalize("NFKD", str(text or ""))
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = value.lower().replace("mm²", "mm2")
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def _extract_text(need_summary: Any) -> str:
    if isinstance(need_summary, dict):
        for key in ("title", "detail", "description", "need_summary"):
            value = need_summary.get(key)
            if value:
                return str(value)
    return str(need_summary or "")


def _matched_categories(text: str) -> set[str]:
    matches: set[str] = set()
    for category, hints in CATEGORY_HINTS.items():
        if any(hint in text for hint in hints):
            matches.add(category)
    return matches


def _item_score(text: str, categories: set[str], item: dict[str, Any]) -> int:
    score = 0
    item_categories = set(item.get("categories") or [])
    item_keywords = [_normalize_text(keyword) for keyword in item.get("keywords") or []]

    if categories & item_categories:
        score += 5 * len(categories & item_categories)
    elif categories:
        return 0

    for keyword in item_keywords:
        if keyword and keyword in text:
            score += 2

    if "chuveiro" in text and "cable" in item_categories:
        score += 2
    if "chuveiro" in text and "breaker" in item_categories:
        score += 1

    return score


def _public_item(item: dict[str, Any]) -> dict[str, str]:
    return {
        "sku": str(item["sku"]),
        "description": str(item["description"]),
        "typical_notes": str(item["typical_notes"]),
    }


def _select_suggestions(need_summary: Any) -> tuple[str, list[dict[str, str]]]:
    text_input = _extract_text(need_summary)
    normalized = _normalize_text(text_input)
    categories = _matched_categories(normalized)

    scored: list[tuple[int, dict[str, Any]]] = []
    for item in MOCK_CATALOG:
        score = _item_score(normalized, categories, item)
        if score > 0:
            scored.append((score, item))

    scored.sort(key=lambda pair: (-pair[0], pair[1]["sku"]))

    suggestions: list[dict[str, str]] = []
    seen_skus: set[str] = set()
    for score, item in scored:
        if score < 4:
            continue
        sku = str(item["sku"])
        if sku in seen_skus:
            continue
        seen_skus.add(sku)
        suggestions.append(_public_item(item))
        if len(suggestions) == 3:
            break

    return text_input, suggestions


def get_component_suggestions_payload(need_summary: Any) -> dict[str, Any]:
    text_input, suggestions = _select_suggestions(need_summary)
    return {
        "input": text_input,
        "suggestions": suggestions,
        "disclaimer": "Precos e disponibilidade variam; esta e uma camada demo estavel.",
    }


class SuggestComponentsInput(BaseModel):
    need_summary: Any = Field(
        ...,
        description="Resumo do problema de conformidade ou dispositivo a substituir",
    )


class SuggestComponentSubstitutesTool(BaseTool):
    name: str = "suggest_component_substitutes"
    description: str = (
        "Sugere substitutos e referencias para componentes quando a auditoria apontar "
        "um problema claro de material ou dispositivo. Use somente quando houver problema claro."
    )
    args_schema: type[BaseModel] = SuggestComponentsInput

    def _run(self, need_summary: Any) -> str:
        return json.dumps(get_component_suggestions_payload(need_summary), ensure_ascii=False)
