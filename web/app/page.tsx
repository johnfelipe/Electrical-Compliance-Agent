"use client";

import { FormEvent, useMemo, useState } from "react";

type Finding = {
  severity?: string | null;
  title?: string | null;
  detail?: string | null;
  evidence_clause_ref_or_none?: string | null;
  evidence_quote_or_none?: string | null;
};

type Suggestion = {
  sku?: string;
  description?: string;
  typical_notes?: string;
};

type SupportByFinding = {
  finding_title?: string | null;
  status?: string | null;
  notes?: string | null;
  suggestions?: Suggestion[];
};

type AuditResponse = {
  audit_id?: string | null;
  norms_touched?: string[];
  findings?: Finding[] | null;
  support_suggestions?: Array<Suggestion | SupportByFinding> | null;
  raw_report?: string;
};

type ProgressStep = {
  step: number;
  agent: string;
  message: string;
  status: "pending" | "running" | "done";
};

const API_URL =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") ?? "http://127.0.0.1:8000";

const INITIAL_STEPS: ProgressStep[] = [
  { step: 1, agent: "Triador", message: "Normalizando dados do projeto...", status: "pending" },
  { step: 2, agent: "Pesquisador", message: "Buscando evidencias nas normas...", status: "pending" },
  { step: 3, agent: "Auditor", message: "Gerando relatorio de conformidade...", status: "pending" },
];

const demoInputs = [
  {
    label: "Caso inseguro",
    value:
      "Projeto residencial com circuito de banheiro 127V, tomada proxima ao lavatorio, sem informacao de DR, sem quadro detalhado e sem memoria de calculo dos condutores.",
  },
  {
    label: "Caso parcial",
    value:
      "Circuito de chuveiro 220V com carga de 7500W, disjuntor informado de 32A, mas sem confirmacao de bitola, metodo de instalacao e seletividade com os demais circuitos.",
  },
  {
    label: "Caso conservador",
    value:
      "Memorial simplificado de reforma eletrica com descricao geral de tomadas e iluminacao, mas sem tabela de cargas, sem quadro de distribuicao e sem referencias normativas anexadas.",
  },
];

function severityLabel(value?: string | null) {
  switch ((value ?? "").toLowerCase()) {
    case "high":
      return "Alta";
    case "medium":
      return "Media";
    default:
      return "Baixa";
  }
}

function severityClass(value?: string | null) {
  switch ((value ?? "").toLowerCase()) {
    case "high":
      return "severity severity-high";
    case "medium":
      return "severity severity-medium";
    default:
      return "severity severity-low";
  }
}

function isSupportByFinding(item: Suggestion | SupportByFinding): item is SupportByFinding {
  return "suggestions" in item && ("finding_title" in item || "status" in item || "notes" in item);
}

function parseSSELines(buffer: string): { events: Array<{ event: string; data: string }>; remainder: string } {
  const events: Array<{ event: string; data: string }> = [];
  const lines = buffer.split("\n");
  let currentEvent = "";
  let currentData = "";
  let remainder = "";

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];

    if (line.startsWith("event: ")) {
      currentEvent = line.slice(7).trim();
    } else if (line.startsWith("data: ")) {
      currentData = line.slice(6);
    } else if (line === "" && currentEvent) {
      events.push({ event: currentEvent, data: currentData });
      currentEvent = "";
      currentData = "";
    } else if (line === "" && currentData) {
      events.push({ event: "message", data: currentData });
      currentData = "";
    }
  }

  if (currentEvent || currentData) {
    const parts: string[] = [];
    if (currentEvent) parts.push(`event: ${currentEvent}`);
    if (currentData) parts.push(`data: ${currentData}`);
    remainder = parts.join("\n");
  }

  return { events, remainder };
}

export default function HomePage() {
  const [projectDescription, setProjectDescription] = useState(demoInputs[0].value);
  const [result, setResult] = useState<AuditResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isAuditing, setIsAuditing] = useState(false);
  const [steps, setSteps] = useState<ProgressStep[]>(INITIAL_STEPS);
  const [elapsedSeconds, setElapsedSeconds] = useState(0);

  const supportGroups = useMemo(() => {
    const rows = result?.support_suggestions ?? [];
    return rows.filter(isSupportByFinding);
  }, [result]);

  const flatSuggestions = useMemo(() => {
    const rows = result?.support_suggestions ?? [];
    return rows.filter((item): item is Suggestion => !isSupportByFinding(item));
  }, [result]);

  function updateStep(stepNum: number, status: "running" | "done") {
    setSteps((prev) =>
      prev.map((s) => (s.step === stepNum ? { ...s, status } : s)),
    );
  }

  async function submitAudit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setResult(null);
    setIsAuditing(true);
    setSteps(INITIAL_STEPS.map((s) => ({ ...s, status: "pending" as const })));
    setElapsedSeconds(0);

    const timerInterval = setInterval(() => {
      setElapsedSeconds((prev) => prev + 1);
    }, 1000);

    try {
      const response = await fetch(`${API_URL}/audit/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ project_description: projectDescription }),
      });

      if (!response.ok) {
        let detail = "Falha ao executar a auditoria.";
        try {
          const payload = (await response.json()) as { detail?: string };
          detail = payload.detail || detail;
        } catch {
          const text = await response.text();
          if (text) detail = text;
        }
        throw new Error(detail);
      }

      const reader = response.body?.getReader();
      if (!reader) throw new Error("Stream not supported");

      const decoder = new TextDecoder();
      let sseBuffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        sseBuffer += decoder.decode(value, { stream: true });
        const { events, remainder } = parseSSELines(sseBuffer);
        sseBuffer = remainder;

        for (const evt of events) {
          if (evt.event === "ping") continue;

          let payload;
          try {
            payload = JSON.parse(evt.data);
          } catch {
            continue;
          }

          if (evt.event === "step_start") {
            updateStep(payload.step, "running");
          } else if (evt.event === "step_done") {
            updateStep(payload.step, "done");
          } else if (evt.event === "result") {
            setResult(payload as AuditResponse);
          } else if (evt.event === "error") {
            throw new Error(payload.detail || "Erro durante a auditoria.");
          }
        }
      }
    } catch (submissionError) {
      const message =
        submissionError instanceof Error
          ? submissionError.message
          : "Falha inesperada ao chamar a API.";
      setResult(null);
      setError(message);
    } finally {
      clearInterval(timerInterval);
      setIsAuditing(false);
    }
  }

  const activeStep = steps.find((s) => s.status === "running");

  return (
    <main className="shell">
      <section className="hero-panel">
        <div className="hero-copy">
          <p className="eyebrow">AMD Hackathon · Track 1</p>
          <h1>The Electrical Compliance Agent</h1>
          <p className="hero-text">
            Um fluxo multiagente para triagem, busca normativa, auditoria de conformidade e
            suporte a materiais em projetos eletricos.
          </p>
          <div className="hero-badges">
            <span>CrewAI</span>
            <span>Supabase pgvector</span>
            <span>FastAPI</span>
            <span>Next.js</span>
          </div>
        </div>

        <div className="hero-rail">
          <div className="rail-card">
            <span className="rail-step">01</span>
            <strong>Triador</strong>
            <p>Estrutura o projeto sem inventar dados ausentes.</p>
          </div>
          <div className="rail-card">
            <span className="rail-step">02</span>
            <strong>Pesquisador</strong>
            <p>Recupera evidencias reais em normas indexadas.</p>
          </div>
          <div className="rail-card">
            <span className="rail-step">03</span>
            <strong>Auditor + Suporte</strong>
            <p>Gera findings rastreaveis e sugere itens quando o problema e claro.</p>
          </div>
        </div>
      </section>

      <section className="workspace">
        <form className="panel panel-form" onSubmit={submitAudit}>
          <div className="panel-heading">
            <div>
              <p className="eyebrow">Entrada</p>
              <h2>Descreva o projeto a ser auditado</h2>
            </div>
            <div className="status-badge">
              API: <code>{API_URL}</code>
            </div>
          </div>

          <div className="demo-chips">
            {demoInputs.map((demo) => (
              <button
                key={demo.label}
                className="chip"
                type="button"
                onClick={() => setProjectDescription(demo.value)}
              >
                {demo.label}
              </button>
            ))}
          </div>

          <label className="field-label" htmlFor="project-description">
            Descricao do projeto
          </label>
          {isAuditing ? (
            <div className="progress-tracker">
              <div className="progress-header">
                <span className="progress-timer">{elapsedSeconds}s</span>
              </div>
              <div className="progress-steps">
                {steps.map((s) => (
                  <div
                    key={s.step}
                    className={`progress-step progress-step--${s.status}`}
                  >
                    <div className="step-indicator">
                      {s.status === "done" ? (
                        <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                          <path d="M3 8.5L6.5 12L13 4" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                        </svg>
                      ) : s.status === "running" ? (
                        <div className="step-spinner" />
                      ) : (
                        <span className="step-number">{s.step}</span>
                      )}
                    </div>
                    <div className="step-content">
                      <strong>{s.agent}</strong>
                      <span>{s.message}</span>
                    </div>
                  </div>
                ))}
              </div>
              {activeStep ? (
                <p className="progress-active-msg">
                  {activeStep.agent}: {activeStep.message}
                </p>
              ) : null}
            </div>
          ) : null}

          <textarea
            id="project-description"
            className={`project-input${isAuditing ? " project-input--collapsed" : ""}`}
            value={projectDescription}
            onChange={(event) => setProjectDescription(event.target.value)}
            placeholder="Ex.: circuito de banheiro, quadro, cargas, protecoes, bitolas, ambiente..."
            minLength={10}
            rows={12}
            disabled={isAuditing}
          />

          <div className="form-footer">
            <p>
              Dica: quanto mais claro o texto sobre ambiente, carga e protecao, melhor a auditoria.
            </p>
            <button className="primary-button" type="submit" disabled={isAuditing}>
              {isAuditing ? "Auditando..." : "Executar auditoria"}
            </button>
          </div>

          {error ? <div className="error-box">{error}</div> : null}
        </form>

        <div className="results-stack">
          <section className="panel">
            <div className="panel-heading">
              <div>
                <p className="eyebrow">Saida</p>
                <h2>Relatorio estruturado</h2>
              </div>
              <div className="status-badge">
                {result?.audit_id ? `Audit ID: ${result.audit_id}` : "Sem execucao"}
              </div>
            </div>

            {result ? (
              <div className="summary-grid">
                <div className="metric-card">
                  <span>Normas tocadas</span>
                  <strong>{result.norms_touched?.length ?? 0}</strong>
                </div>
                <div className="metric-card">
                  <span>Findings</span>
                  <strong>{result.findings?.length ?? 0}</strong>
                </div>
                <div className="metric-card">
                  <span>Suporte</span>
                  <strong>
                    {(supportGroups.length || flatSuggestions.length) > 0 ? "Ativo" : "Sem sugestoes"}
                  </strong>
                </div>
              </div>
            ) : (
              <p className="empty-state">
                Execute uma auditoria para visualizar findings, normas consultadas e sugestoes.
              </p>
            )}

            {result?.norms_touched?.length ? (
              <div className="tag-row">
                {result.norms_touched.map((norm) => (
                  <span key={norm} className="tag">
                    {norm}
                  </span>
                ))}
              </div>
            ) : null}

            <div className="findings-list">
              {(result?.findings ?? []).map((finding, index) => (
                <article key={`${finding.title ?? "finding"}-${index}`} className="finding-card">
                  <div className="finding-header">
                    <span className={severityClass(finding.severity)}>
                      {severityLabel(finding.severity)}
                    </span>
                    <h3>{finding.title ?? "Finding sem titulo"}</h3>
                  </div>
                  <p>{finding.detail ?? "Sem detalhe informado."}</p>
                  <div className="evidence-grid">
                    <div>
                      <span className="mini-label">Clausula</span>
                      <p>{finding.evidence_clause_ref_or_none ?? "Nao validada no contexto recuperado"}</p>
                    </div>
                    <div>
                      <span className="mini-label">Trecho de evidencia</span>
                      <p>{finding.evidence_quote_or_none ?? "Nao ha citacao rastreavel"}</p>
                    </div>
                  </div>
                </article>
              ))}
            </div>
          </section>

          <section className="panel support-panel">
            <div className="panel-heading">
              <div>
                <p className="eyebrow">Suporte</p>
                <h2>Sugestoes de materiais</h2>
              </div>
            </div>

            {supportGroups.length > 0 ? (
              <div className="support-groups">
                {supportGroups.map((group, index) => (
                  <article key={`${group.finding_title ?? "support"}-${index}`} className="support-card">
                    <div className="support-card-header">
                      <h3>{group.finding_title ?? "Finding sem titulo"}</h3>
                      <span className="status-pill">{group.status ?? "suggested"}</span>
                    </div>
                    <p>{group.notes ?? "Sem notas adicionais."}</p>
                    <div className="suggestion-list">
                      {(group.suggestions ?? []).map((suggestion) => (
                        <div key={suggestion.sku} className="suggestion-item">
                          <strong>{suggestion.sku}</strong>
                          <p>{suggestion.description}</p>
                          <span>{suggestion.typical_notes}</span>
                        </div>
                      ))}
                    </div>
                  </article>
                ))}
              </div>
            ) : flatSuggestions.length > 0 ? (
              <div className="suggestion-list">
                {flatSuggestions.map((suggestion) => (
                  <div key={suggestion.sku} className="suggestion-item">
                    <strong>{suggestion.sku}</strong>
                    <p>{suggestion.description}</p>
                    <span>{suggestion.typical_notes}</span>
                  </div>
                ))}
              </div>
            ) : (
              <p className="empty-state">
                O suporte so aparece quando o finding aponta um problema claro de componente.
              </p>
            )}
          </section>

          <section className="panel">
            <div className="panel-heading">
              <div>
                <p className="eyebrow">Trace</p>
                <h2>Relatorio bruto da crew</h2>
              </div>
            </div>
            <pre className="report-box">{result?.raw_report ?? "Sem execucao ainda."}</pre>
          </section>
        </div>
      </section>
    </main>
  );
}
