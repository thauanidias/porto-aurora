import { ArrowUpRight, BriefcaseBusiness, CalendarDays, Check, ChevronLeft, ChevronRight, ExternalLink, Link2 } from "lucide-react";
import { obj, str, type Collection, type Row } from "../lib/api";

type Props = {
  data?: Collection;
  page: number;
  onPage: (page: number) => void;
  onOpen: (row: Row) => void;
  onAttach: (row: Row) => void;
  onSchedule: (row: Row) => void;
  canAttach: boolean;
  canSchedule: boolean;
};

export function InterviewCandidates({ data, page, onPage, onOpen, onAttach, onSchedule, canAttach, canSchedule }: Props) {
  const total = data?.total ?? 0;
  const pages = Math.max(1, Math.ceil(total / (data?.page_size ?? 25)));
  return <div className="interview-candidates">
    <div className="interview-list-heading">
      <span><strong>{total}</strong> {total === 1 ? "candidato para entrevista" : "candidatos para entrevista"}</span>
      <span className="interview-list-hint"><Link2 size={14} aria-hidden="true" /> Links e orientações enviados ao candidato</span>
    </div>
    <div className="interview-candidate-list">
      {data?.items.map(row => {
        const name = str(obj(row.candidate).name);
        const initials = name.trim().split(/\s+/).filter(Boolean).slice(0, 2).map(part => part[0]).join("").toUpperCase();
        const links = Array.isArray(row.interview_links) ? row.interview_links as Record<string, unknown>[] : [];
        return <article className="interview-candidate" key={row.id} aria-label={`Entrevista de ${name}`}>
          <div className="interview-candidate-header">
            <div className="interview-candidate-person">
              <span className="interview-person-avatar" aria-hidden="true">{initials}</span>
              <div><h2>{name}</h2><p><BriefcaseBusiness size={15} aria-hidden="true" /> {str(row.vacancy_title)}</p></div>
            </div>
            <span className={`interview-link-status ${links.length ? "ready" : "pending"}`}>
              {links.length ? <Check size={14} aria-hidden="true" /> : <span className="interview-status-dot" />}
              {links.length ? "Link disponível" : "Link pendente"}
            </span>
          </div>
          <div className="interview-candidate-body">
            <div className={`interview-link-panel ${links.length ? "has-link" : ""}`}>
              {links.length ? links.map(link => <div className="interview-saved-link" key={str(link.id)}>
                <span className="interview-link-icon"><Link2 size={18} aria-hidden="true" /></span>
                <div><a href={str(link.url)} target="_blank" rel="noopener noreferrer">{str(link.title)} <ExternalLink size={14} aria-hidden="true" /></a>
                  <p className="preserve">{str(link.description)}</p></div>
              </div>) : <div className="interview-awaiting-link">
                <span className="interview-link-icon"><Link2 size={19} aria-hidden="true" /></span>
                <div><strong>Adicione o link da entrevista</strong><p>Inclua uma legenda com a data, o horário e as orientações.</p></div>
              </div>}
            </div>
            {canAttach && <button className="button interview-attach-button" onClick={() => onAttach(row)}>
              <Link2 size={16} aria-hidden="true" />{links.length ? "Anexar outro link" : "Anexar link da entrevista"}
            </button>}
          </div>
          <div className="interview-candidate-footer">
            <span className="interview-stage"><span />{str(row.stage_name)}</span>
            <div className="interview-secondary-actions">
              {canSchedule && <button className="text-button" onClick={() => onSchedule(row)}><CalendarDays size={15} aria-hidden="true" /> Agendar entrevista</button>}
              <button className="text-button" onClick={() => onOpen(row)}>Ver candidatura <ArrowUpRight size={15} aria-hidden="true" /></button>
            </div>
          </div>
        </article>;
      })}
    </div>
    {pages > 1 && <nav className="interview-pagination" aria-label="Páginas de candidatos para entrevista">
      <span>Página {page} de {pages}</span>
      <button className="button secondary small" aria-label="Página anterior" disabled={page <= 1} onClick={() => onPage(page - 1)}><ChevronLeft size={16} /></button>
      <button className="button secondary small" aria-label="Próxima página" disabled={page >= pages} onClick={() => onPage(page + 1)}><ChevronRight size={16} /></button>
    </nav>}
  </div>;
}
