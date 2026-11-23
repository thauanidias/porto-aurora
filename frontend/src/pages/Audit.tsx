import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Clock3, Search, ShieldCheck, UserRound } from "lucide-react";
import { api, str, type Row, type Collection } from "../lib/api";
import { Empty, ErrorBox, Modal, PageTitle } from "../components/ui";
import { RecordDetail } from "./Resources";

const categories = [["candidate.", "Perfis de candidatos"], ["application.", "Candidaturas e etapas"], ["vacancy.", "Vagas"], ["document.", "Documentos"], ["talent", "Banco de talentos"], ["interview.", "Entrevistas"], ["evaluation.", "Avaliações"], ["auth.", "Acessos ao sistema"], ["user.", "Usuários"], ["configuration.", "Configurações"]];
const actions: Record<string, string> = {
  "candidate.accessed": "Perfil de candidato consultado", "talent.rediscovered": "Busca de talentos realizada",
  "application.stage_changed": "Candidato movimentado de etapa", "application.stage_reviewed": "Parecer da etapa registrado",
  "application.created": "Candidatura registrada", "application.decision": "Decisão da candidatura registrada",
  "application.returned": "Candidatura reaberta", "application.curriculum_analyzed": "Currículo analisado",
  "candidate.updated": "Perfil de candidato atualizado", "candidate.created": "Perfil de candidato criado",
  "vacancy.created": "Vaga criada", "vacancy.updated": "Vaga atualizada", "vacancy.published": "Vaga divulgada", "vacancy.closed": "Vaga encerrada",
  "auth.login": "Entrada no sistema", "auth.failed": "Tentativa de acesso sem sucesso", "session.revoked": "Sessão encerrada",
  "document.uploaded": "Documento enviado", "document.reviewed": "Documento analisado", "document.downloaded": "Documento baixado",
  "evaluation.submitted": "Avaliação enviada", "interview.status_updated": "Situação da entrevista atualizada",
  "configuration.created": "Configuração criada", "configuration.updated": "Configuração atualizada",
};
function auditDate(value: unknown) { return new Date(str(value)).toLocaleString("pt-BR", {timeZone: "America/Fortaleza", dateStyle: "short", timeStyle: "short"}); }
function actionTitle(row: Row) { return actions[str(row.action)] ?? "Atividade registrada · " + (categories.find(([prefix]) => str(row.action).startsWith(prefix))?.[1] ?? "Sistema"); }
export function AuditPage() {
  const [q, setQ] = useState("");
  const [action, setAction] = useState("");
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState<Row | null>(null);
  const query = useQuery({queryKey: ["audit-history", q, action, from, to, page], queryFn: () => api<Collection>("/audit?" + new URLSearchParams({q, action, ...(from ? {date_from: from} : {}), ...(to ? {date_to: to} : {}), page_number: String(page)}))});
  const filtered = Boolean(q || action || from || to);
  return <>
    <PageTitle title="Auditoria" subtitle="Veja quem realizou cada ação e quando ela aconteceu. O histórico é somente para consulta." />
    <section className="surface padded audit-history">
      <div className="audit-filters">
        <label className="field"><span>Buscar no histórico</span><span className="search-field"><Search size={17} aria-hidden="true" /><input value={q} onChange={e => {setQ(e.target.value); setPage(1);}} placeholder="Nome do responsável ou vaga" /></span></label>
        <label className="field"><span>Tipo de atividade</span><select value={action} onChange={e => {setAction(e.target.value); setPage(1);}}><option value="">Todas as atividades</option>{categories.map(([value, title]) => <option key={value} value={value}>{title}</option>)}</select></label>
        <label className="field"><span>De</span><input type="date" value={from} max={to || undefined} onChange={e => {setFrom(e.target.value); setPage(1);}} /></label>
        <label className="field"><span>Até</span><input type="date" value={to} min={from || undefined} onChange={e => {setTo(e.target.value); setPage(1);}} /></label>
      </div>
      <div className="audit-list-heading"><h2>Histórico de atividades</h2><div><span>{query.data?.total ?? 0} registros</span>{filtered && <button className="text-button" onClick={() => {setQ(""); setAction(""); setFrom(""); setTo(""); setPage(1);}}>Limpar filtros</button>}</div></div>
      <ErrorBox error={query.error} />
      {query.isPending ? <p role="status">Carregando atividades…</p> : !query.isError && (!query.data?.items.length ? <Empty title="Nenhuma atividade encontrada">Ajuste a busca ou o período para consultar outros registros.</Empty> : <ol className="audit-timeline">{query.data.items.map(row => <li key={row.id}>
        <span className="audit-event-icon"><ShieldCheck size={19} aria-hidden="true" /></span><div className="audit-event-copy"><h3>{actionTitle(row)}</h3><div className="audit-event-meta"><span><UserRound size={14} aria-hidden="true" />{str(row.user_name) || (row.user_id ? "Usuário não identificado" : "Sistema / atividade automática")}</span><span><Clock3 size={14} aria-hidden="true" />{auditDate(row.created_at)}</span></div>{Boolean(row.vacancy_title) && <p>Vaga: <strong>{str(row.vacancy_title)}</strong></p>}</div>
        <button className="button secondary small" onClick={() => setSelected(row)} aria-label={"Ver detalhes: " + actionTitle(row)}>Ver detalhes</button>
      </li>)}</ol>)}
      {Boolean(query.data?.total) && <footer className="task-footer"><span>Mais recentes primeiro · Horário de Fortaleza</span><div className="pagination"><button className="button secondary small" disabled={page === 1} onClick={() => setPage(page - 1)}>Anterior</button><span>Página {page}</span><button className="button secondary small" disabled={page * 50 >= (query.data?.total ?? 0)} onClick={() => setPage(page + 1)}>Próxima</button></div></footer>}
    </section>
    <Modal open={Boolean(selected)} onOpenChange={open => {if (!open) setSelected(null);}} title="Detalhes da atividade">{selected && <div className="audit-event-modal"><h3>{actionTitle(selected)}</h3><p><strong>Responsável:</strong> {str(selected.user_name) || "Sistema / usuário não identificado"}</p><p><strong>Quando:</strong> {auditDate(selected.created_at)}</p>{Boolean(selected.vacancy_title) && <p><strong>Vaga:</strong> {str(selected.vacancy_title)}</p>}<details><summary>Ver informações técnicas e alterações registradas</summary><RecordDetail value={selected} /></details></div>}</Modal>
  </>;
}
