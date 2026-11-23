import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { CalendarDays, Clock, Users, ExternalLink } from "lucide-react";
import { api, rows, str, type Collection } from "../lib/api";
import { date, label } from "../lib/labels";
import { Empty, ErrorBox, PageTitle } from "../components/ui";

export function ManagerAgenda() {
  const [page, setPage] = useState(1);
  const query = useQuery({ queryKey: ["manager-interview-agenda", page], queryFn: () => api<Collection>(`/interviews/manager-agenda?page_number=${page}`), refetchInterval: 15000 });
  return <><PageTitle title="Agenda de entrevistas" subtitle="Entrevistas agendadas pelo RH nas vagas sob sua responsabilidade." /><ErrorBox error={query.error} />
    {query.isPending && <p role="status">Consultando agenda…</p>}
    {query.data && !query.data.total && <Empty title="Nenhuma entrevista agendada">Os agendamentos feitos pelo RH aparecerão automaticamente aqui.</Empty>}
    <div className="manager-agenda-list">{query.data?.items.map(interview => {
      const location = str(interview.location);
      const url = /^https?:\/\//i.test(location) && !/\s/.test(location) ? location : "";
      return <section className="surface padded manager-agenda-card" key={interview.id}>
        <div className="manager-agenda-heading"><div><p className="privacy-eyebrow">{str(interview.vacancy_title)}</p><h2><CalendarDays size={21} aria-hidden="true" />{str(interview.title)}</h2></div><span className={"badge " + (interview.status === "COMPLETED" ? "success" : "")}>{label(str(interview.status))}</span></div>
        <p><Clock size={17} aria-hidden="true" /><strong>{date(interview.starts_at)}</strong><span>até {date(interview.ends_at)}</span></p>
        <p><Users size={17} aria-hidden="true" /><span>{rows(interview.candidates).map(candidate => str(candidate.name)).join(", ") || "Participantes ainda não definidos"}</span></p>
        <div className="manager-agenda-location"><strong>{url ? "Acesso à entrevista" : "Local e orientações"}</strong>{url ? <a className="button secondary" href={url} target="_blank" rel="noopener noreferrer">Abrir link da entrevista<ExternalLink size={16} /></a> : <p>{location || "A confirmar pelo RH"}</p>}</div>
      </section>;
    })}</div>
    {query.data && query.data.total > 50 && <div className="actions"><button className="button secondary" disabled={page === 1} onClick={() => setPage(value => value - 1)}>Anterior</button><span>Página {page}</span><button className="button secondary" disabled={page * 50 >= query.data.total} onClick={() => setPage(value => value + 1)}>Próxima</button></div>}
  </>;
}
