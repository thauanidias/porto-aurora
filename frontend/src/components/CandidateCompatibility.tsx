import { obj, str, type Row } from "../lib/api";
export { CompatibilityRanking } from "./CompatibilityRanking";

const statuses: Record<string, string> = {
  NOT_CONFIGURED: "Configure os critérios da vaga",
  OUTDATED: "Aguardando atualização do cálculo",
  SEALED: "Aguardando avaliações independentes",
  PENDING: "Resultado provisório · faltam informações",
};

function compatibilityPercentage(row: Row): number | null {
  const value = compatibilityReport(row).percentage;
  if (["OUTDATED", "NOT_CONFIGURED", "SEALED"].includes(str(compatibilityReport(row).status))) return null;
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

export function compatibilityReport(row: Row) {
  const summary = obj(row.compatibility);
  return Object.keys(obj(summary.curriculum)).length ? obj(summary.curriculum) : summary;
}

export { compatibilityPercentage };
export function compatibilityCategory(row: Row) {
  const value = compatibilityPercentage(row);
  const bands = Array.isArray(obj(row.compatibility).bands) ? obj(row.compatibility).bands as Record<string, unknown>[] : [];
  const high = Number(bands.find(b => b.key === "high")?.min ?? 80);
  const moderate = Number(bands.find(b => b.key === "moderate")?.min ?? 60);
  return value === null ? "pending" : value >= high ? "high" : value >= moderate ? "moderate" : "low";
}
export const categoryNames: Record<string, string> = { high: "Alta compatibilidade", moderate: "Compatibilidade moderada", low: "Baixa compatibilidade", pending: "Sem nota disponível" };
export function mandatoryPending(row: Row) {
  const items = compatibilityReport(row).items;
  return Array.isArray(items) && items.some(item => (item.mandatory || item.knockout) && (item.status ? item.status !== "MET" : item.value == null || item.met === false));
}

export function CandidateCompatibility({ row, details = false }: { row: Row; details?: boolean }) {
  const summary = compatibilityReport(row);
  const percentage = compatibilityPercentage(row);
  const items = Array.isArray(summary.items) ? summary.items as Record<string, unknown>[] : [];
  const evidenceLabels: Record<string, string> = { MET: "Atendido", PARTIAL: "Atendido parcialmente", NOT_MET: "Aparentemente não atendido", UNKNOWN: "Não informado — verificar com o candidato" };
  return <div className={"candidate-compatibility compatibility-" + compatibilityCategory(row)}>
    <strong>{percentage === null ? "Sem nota disponível" : `${percentage.toLocaleString("pt-BR", { maximumFractionDigits: 2 })}% de compatibilidade`}</strong>
    <span className="compatibility-category">{categoryNames[compatibilityCategory(row)]}</span>
    {percentage !== null && <progress max={100} value={percentage} aria-label="Compatibilidade com a vaga" />}
    {statuses[str(summary.status)] && <small>{statuses[str(summary.status)]}</small>}
    {Boolean(summary.engine) && <small>Análise por IA local · revisão humana necessária</small>}
    {Boolean(summary.analyzed_at) && <small>{new Date(str(summary.analyzed_at)).toLocaleString("pt-BR", { timeZone: "America/Fortaleza" })}</small>}
    {(mandatoryPending(row) || summary.knockout === true) && <small className="compatibility-warning">Requisito obrigatório precisa de revisão pelo RH.</small>}
    {percentage === null && summary.status === "PENDING" && <small>Informações insuficientes não significam baixa compatibilidade.</small>}
    {details && items.length > 0 && <details className="compatibility-evidence"><summary>Ver análise e evidências</summary>
      <p className="muted">{summary.engine ? "Critérios profissionais comparados ao currículo." : `Modelo ${str(summary.model_version)} · Pontuação ponderada pelos critérios da vaga.`}</p>
      {summary.coverage != null && <p>Evidências identificadas em {str(summary.coverage)}% do peso dos critérios.</p>}
      <ul>{items.map(item => <li key={str(item.key)}>
        <strong>{str(item.name)}</strong> · peso {str(item.weight)}%{item.mandatory || item.knockout ? " · obrigatório" : " · desejável"}
        <p>{item.status ? evidenceLabels[str(item.status)] : item.value == null ? evidenceLabels.UNKNOWN : `Atendimento ${str(item.normalized)}%`}</p>
        {item.evidence ? <blockquote>{str(item.evidence)}</blockquote> : null}
        {item.expected != null && <small>Requisito: {Array.isArray(item.expected) ? item.expected.join(", ") : str(item.expected)}</small>}
      </li>)}</ul>
      {Boolean(summary.methodology) && <p className="muted">{str(summary.methodology)}</p>}
      {Boolean(summary.recommendation) && <p><strong>Próximo passo:</strong> {str(summary.recommendation)}</p>}
      {Array.isArray(summary.pending_components) && summary.pending_components.length > 0 && <p>Aguardando resultados de: {summary.pending_components.map(str).join(", ")}.</p>}
    </details>}
  </div>;
}

