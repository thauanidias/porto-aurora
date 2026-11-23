import { useState } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api, rows, str, type Row, type Collection } from "../lib/api";
import { date } from "../lib/labels";
import { Badge, Empty, ErrorBox } from "./ui";
import { InterviewAttachmentButton } from "./InterviewAttachmentButton";
import { VacancyFitMessage } from "./VacancyFitMessage";
import { ArrowRight, BriefcaseBusiness, ChevronDown, CalendarDays } from "lucide-react";

function Process({ application }: { application: Row }) {
  const [open, setOpen] = useState(false);
  const detail = useQuery({ queryKey: ["application", application.id], queryFn: () => api<Row>(`/applications/${application.id}`), enabled: open });
  const current = detail.data ?? application;
  const active = ["ACTIVE", "RESERVE"].includes(str(current.status));
  return <article className="candidate-process candidate-process-card">
    <div className="section-heading"><div className="candidate-process-identity"><span className="candidate-process-icon" aria-hidden="true"><BriefcaseBusiness size={23} /></span><div><p className="privacy-eyebrow">{application.recruitment_type === "INTERNAL" ? "SELEÇÃO INTERNA" : "SELEÇÃO EXTERNA"}</p><h3>{str(application.vacancy_title)}</h3></div></div><Badge value={current.status} /></div>
    <div className="candidate-process-summary"><div><span>{active ? "ETAPA ATUAL" : "ÚLTIMA ETAPA"}</span><strong>{str(current.stage_name)}</strong></div><p><CalendarDays size={15} aria-hidden="true" />Inscrição em {date(application.created_at)}</p></div>
    <VacancyFitMessage application={current} compact />
    <div className="actions candidate-process-actions">
      <Link className="button small" to={`/app/candidaturas/${application.id}`}>Acompanhar seleção<ArrowRight size={16} aria-hidden="true" /></Link>
      <button className="button secondary small" aria-expanded={open} aria-controls={"process-details-" + application.id} onClick={() => setOpen(!open)}>{open ? "Ocultar histórico" : "Ver histórico"}<ChevronDown size={16} aria-hidden="true" className={open ? "is-open" : ""} /></button>
      <InterviewAttachmentButton application={application} />
    </div>
    {open && <div id={"process-details-" + application.id} className="candidate-process-details">
      <ErrorBox error={detail.error} />
      {detail.isPending ? <p role="status">Carregando histórico…</p> : detail.isError ? <button className="text-button" onClick={() => void detail.refetch()}>Tentar novamente</button> : <details className="rh-simple-details"><summary>Histórico das mudanças de etapa</summary><ol className="timeline">
        {rows(detail.data?.history).map(stage => <li key={stage.id}>
          <strong>{str(stage.stage_name)}</strong>
          <p>Início: {date(stage.entered_at)}</p>
          <p>{stage.left_at ? "Concluída em " + date(stage.left_at) : "Etapa em andamento"}</p>
        </li>)}
      </ol></details>}
    </div>}
  </article>;
}

export function CandidateProcesses({ candidateId }: { candidateId: string }) {
  const [page, setPage] = useState(1);
  const query = useQuery({ queryKey: ["candidate-processes", candidateId, page], queryFn: () => api<Collection>(`/applications?candidate_id=${encodeURIComponent(candidateId)}&page_number=${page}&page_size=25`) });
  return <section className="surface padded candidate-processes">
    <div className="section-heading"><div><h2>Vagas em que esta pessoa participa</h2><p className="muted">Veja a situação de cada seleção e abra a vaga que deseja acompanhar.</p></div>{query.isSuccess && <span className="candidate-process-count">{query.data.total} {query.data.total === 1 ? "candidatura" : "candidaturas"}</span>}</div>
    <ErrorBox error={query.error} />
    {query.isPending ? <p role="status">Carregando processos…</p> : query.isError ? <button className="button secondary" onClick={() => void query.refetch()}>Tentar novamente</button> : !query.data?.items.length ? <Empty title="Nenhum processo disponível">O cadastro do perfil, por si só, não representa uma inscrição em vaga.</Empty> : query.data.items.map(application => <Process key={application.id} application={application} />)}
    {(query.data?.total ?? 0) > 25 && <div className="pagination"><button className="button secondary small" disabled={page === 1} onClick={() => setPage(page - 1)}>Anterior</button><span>Página {page}</span><button className="button secondary small" disabled={page * 25 >= (query.data?.total ?? 0)} onClick={() => setPage(page + 1)}>Próxima</button></div>}
  </section>;
}
