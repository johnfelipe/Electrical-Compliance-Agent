from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from crew_app.compliance_crew import build_support_suggestions, enforce_evidence_guardrails
from crew_app.tools.component_support_tool import SuggestComponentSubstitutesTool


class GuardrailTests(unittest.TestCase):
    def test_support_tool_prefers_dr_for_residual_protection_gap(self) -> None:
        tool = SuggestComponentSubstitutesTool()
        payload = json.loads(tool._run("Falta DR de 30mA em banheiro"))
        skus = [row["sku"] for row in payload["suggestions"]]

        self.assertIn("DR-30MA-2P-40A", skus)
        self.assertNotIn("CABO-FLEX-10.0-PR", skus)

    def test_support_tool_skips_unmapped_socket_issue(self) -> None:
        tool = SuggestComponentSubstitutesTool()
        payload = json.loads(tool._run("Tomada externa sem grau de protecao adequado"))

        self.assertEqual([], payload["suggestions"])

    def test_guardrails_drop_unsupported_high_finding(self) -> None:
        findings = [
            {
                "severity": "high",
                "title": "Falta de protecao DR",
                "detail": "O projeto nao informa DR para area molhada.",
                "evidence_clause_ref_or_none": "5.1.2",
                "evidence_quote_or_none": "DR de 30mA e obrigatorio",
            }
        ]
        rows = [
            {
                "content": "Condutores devem ser dimensionados para suportar a corrente de projeto.",
                "metadata": {"section": "6.x"},
            }
        ]

        guarded = enforce_evidence_guardrails(findings, retrieved_rows=rows)

        self.assertEqual(1, len(guarded))
        self.assertEqual("low", guarded[0]["severity"])
        self.assertEqual("Evidencia normativa insuficiente", guarded[0]["title"])

    def test_guardrails_keep_supported_quote_and_strip_bad_clause(self) -> None:
        findings = [
            {
                "severity": "medium",
                "title": "Dimensionamento de condutor",
                "detail": "A bitola precisa ser revisada.",
                "evidence_clause_ref_or_none": "9.9.9",
                "evidence_quote_or_none": "condutores devem ser dimensionados para suportar a corrente de projeto",
            }
        ]
        rows = [
            {
                "content": "Condutores devem ser dimensionados para suportar a corrente de projeto.",
                "metadata": {"section": "6.x"},
            }
        ]

        guarded = enforce_evidence_guardrails(findings, retrieved_rows=rows)

        self.assertEqual(1, len(guarded))
        self.assertEqual("medium", guarded[0]["severity"])
        self.assertIsNone(guarded[0]["evidence_clause_ref_or_none"])
        self.assertEqual(
            "condutores devem ser dimensionados para suportar a corrente de projeto",
            guarded[0]["evidence_quote_or_none"],
        )

    def test_support_builder_returns_grouped_suggestions_without_llm(self) -> None:
        findings = [
            {
                "severity": "high",
                "title": "Falta de protecao DR",
                "detail": "Banheiro sem DR de 30mA informado.",
            },
            {
                "severity": "low",
                "title": "Observacao geral",
                "detail": "Detalhes adicionais podem ser revisados depois.",
            },
        ]

        support = build_support_suggestions(findings)

        self.assertEqual(1, len(support))
        self.assertEqual("Falta de protecao DR", support[0]["finding_title"])
        self.assertEqual("suggested", support[0]["status"])
        self.assertIn("DR-30MA-2P-40A", [row["sku"] for row in support[0]["suggestions"]])

    def test_support_builder_marks_unmapped_case_as_skipped(self) -> None:
        findings = [
            {
                "severity": "medium",
                "title": "Tomada externa inadequada",
                "detail": "Tomada em area externa sem grau de protecao informado.",
            }
        ]

        support = build_support_suggestions(findings)

        self.assertEqual(1, len(support))
        self.assertEqual("skipped", support[0]["status"])
        self.assertEqual([], support[0]["suggestions"])


if __name__ == "__main__":
    unittest.main()
