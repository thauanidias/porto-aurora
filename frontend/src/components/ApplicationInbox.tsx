import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api, str, obj, type Collection } from "../lib/api";
import { ApplicationConversation } from "./ApplicationConversation";
import { Empty, ErrorBox } from "./ui";
import { ArrowRight, BriefcaseBusiness, LockKeyhole, MessageCircle, Search, X } from "lucide-react";

export function ApplicationInbox({ candidate = false }: { candidate?: boolean }) {
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [selection, setSelected] = useState<{ id: string; title: string } | null>();
  const query = useQuery({ queryKey: ["conversation-applications", candidate, page, search], queryFn: () => api<Collection>(`/applications?page_number=${page}&page_size=25&q=${encodeURIComponent(search)}`), refetchInterval: 5000, refetchIntervalInBackground: true, refetchOnWindowFocus: "always", refetchOnReconnect: "always" });
  const available = query.data?.items.filter(item => obj(obj(item.candidate_access).permissions).messages === true) ?? [];
  const selected = selection === undefined && candidate && available.length === 1 ? { id: available[0].id, title: str(available[0].vacancy_title) } : selection;
  return <div className={`message-workspace ${selected ? "has-conversation" : ""}`}>
    <section className="surface message-directory">
      <header className="message-directory-heading"><span className="message-directory-icon"><MessageCircle size={23} aria-hidden="true" /></span><div><h2>{candidate ? "Minhas conversas com o RH" : "Conversas com candidatos"}</h2>
      <p>Selecione uma candidatura para conversar.</p></div></header>
      <div className="message-directory-tools"><label className="message-search"><Search size={18} aria-hidden="true" /><input aria-label="Buscar conversas" type="search" placeholder={candidate ? "Buscar por vaga" : "Buscar candidato ou vaga"} value={search} onChange={event => { setSearch(event.target.value); setPage(1); }} /></label><span role="status">{query.data ? `${query.data.total} ${query.data.total === 1 ? "candidatura" : "candidaturas"}` : "Carregando…"}</span></div>
      <ErrorBox error={query.error} />
      {query.isPending ? <p role="status">Carregando candidaturas…</p> : query.isError ? <button className="text-button" onClick={() => void query.refetch()}>Tentar novamente</button> : !query.data?.items.length ? <Empty title="Nenhuma candidatura disponível">{candidate ? "Suas conversas aparecerão após a inscrição em uma vaga." : "As candidaturas dos processos vinculados ao seu acesso aparecerão aqui."}</Empty> : <ul className="candidate-vacancy-list">
        {query.data.items.map(application => {
          const title = str(application.vacancy_title) + (candidate ? "" : " · " + (str(obj(application.candidate).name) || "Candidato"));
          const name = candidate ? "RH" : str(obj(application.candidate).name) || "Candidato";
          const locked = candidate && obj(obj(application.candidate_access).permissions).messages !== true;
          return <li key={application.id} className={selected?.id === application.id ? "message-row selected" : "message-row"}><span className="message-person-avatar" aria-hidden="true">{name.trim().split(/\s+/).slice(0, 2).map(part => part[0]).join("").toUpperCase()}</span><div className="message-person"><strong>{candidate ? str(application.vacancy_title) : name}</strong><span><BriefcaseBusiness size={14} aria-hidden="true" />{candidate ? "Conversa com o RH" : str(application.vacancy_title)}</span></div><button className="button secondary small" disabled={locked} aria-label={locked ? `Conversa bloqueada: ${title}` : `Abrir conversa: ${title}`} aria-pressed={selected?.id === application.id} onClick={() => setSelected({ id: application.id, title })}>{locked ? <><LockKeyhole size={15} aria-hidden="true" /> Após a triagem</> : <>{selected?.id === application.id ? "Aberta" : "Conversar"}<ArrowRight size={15} aria-hidden="true" /></>}</button></li>;
        })}
      </ul>}
      {(query.data?.total ?? 0) > 25 && <div className="pagination"><button className="button secondary small" disabled={page === 1} onClick={() => setPage(page - 1)}>Anterior</button><span>Página {page}</span><button className="button secondary small" disabled={page * 25 >= (query.data?.total ?? 0)} onClick={() => setPage(page + 1)}>Próxima</button></div>}
    </section>
    {selected && (!candidate || query.data?.items.some(item => item.id === selected.id && obj(obj(item.candidate_access).permissions).messages === true)) && <div className="message-selected"><header><div><span>CONVERSA SELECIONADA</span><h2>{selected.title}</h2></div><button className="button secondary small" aria-label="Fechar conversa" onClick={() => setSelected(null)}><X size={17} /></button></header><ApplicationConversation key={selected.id} applicationId={selected.id} /></div>}
  </div>;
}
