import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api, str, type Collection } from "../lib/api";
import { VacancyConversation } from "../components/VacancyConversation";
import { ApplicationInbox } from "../components/ApplicationInbox";
import { isManager, useSession } from "../lib/session";
import { Empty, ErrorBox, PageTitle } from "../components/ui";

export function MessagesPage({ candidate = false }: { candidate?: boolean }) {
  const session = useSession();
  const manager = isManager(session.data);
  const [area, setArea] = useState(candidate || !manager ? "candidates" : "internal");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState<{ id: string; title: string } | null>(null);
  const query = useQuery({ queryKey: ["conversation-vacancies", search, page], queryFn: () => api<Collection>(`/vacancies?q=${encodeURIComponent(search)}&page_number=${page}&page_size=25`), enabled: !candidate && area === "internal" });
  return <>
    <PageTitle title="Mensagens" subtitle={candidate ? "Converse com o RH sobre suas candidaturas." : "Acompanhe as conversas dos seus processos seletivos."} />
    {!candidate && !manager && <div className="tabs"><button className={area === "candidates" ? "active" : ""} onClick={() => setArea("candidates")}>Candidatos e RH</button><button className={area === "internal" ? "active" : ""} onClick={() => setArea("internal")}>Gestor e RH</button></div>}
    {area === "candidates" ? <ApplicationInbox candidate={candidate} /> : <><section className="surface padded admission-documents">
      <label className="field"><span>Buscar vaga</span><input type="search" value={search} onChange={e => { setSearch(e.target.value); setPage(1); }} placeholder="Digite o nome da vaga" /></label>
      <ErrorBox error={query.error} />
      {query.isPending ? <p role="status">Carregando vagas…</p> : query.isError ? <button className="button secondary" onClick={() => void query.refetch()}>Tentar novamente</button> : !query.data?.items.length ? <Empty title="Nenhuma vaga disponível para conversar">As conversas aparecem quando há uma vaga vinculada ao seu acesso.</Empty> : <ul className="candidate-vacancy-list">
        {query.data.items.map(vacancy => <li key={vacancy.id}><strong>{str(vacancy.title)}</strong><button className="button secondary small" aria-pressed={selected?.id === vacancy.id} onClick={() => setSelected({ id: vacancy.id, title: str(vacancy.title) })}>{selected?.id === vacancy.id ? "Conversa aberta" : "Abrir conversa"}</button></li>)}
      </ul>}
      {(query.data?.total ?? 0) > 25 && <div className="pagination"><button className="button secondary small" disabled={page === 1} onClick={() => setPage(page - 1)}>Anterior</button><span>Página {page}</span><button className="button secondary small" disabled={page * 25 >= (query.data?.total ?? 0)} onClick={() => setPage(page + 1)}>Próxima</button></div>}
    </section>
    {selected && <><h2>{selected.title}</h2><VacancyConversation key={selected.id} vacancyId={selected.id} /></>}</>}
  </>;
}
