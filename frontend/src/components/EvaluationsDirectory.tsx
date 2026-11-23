import { CandidateFeedbackInbox } from "./CandidateFeedback";
﻿import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { ArrowRight, ClipboardCheck, Search } from "lucide-react";
import { api, str, type Collection } from "../lib/api";
import { date, label } from "../lib/labels";
import { Empty, ErrorBox } from "./ui";

export function EvaluationsDirectory({ manager = false }: { manager?: boolean }) {
  return manager ? <AssignedEvaluations manager /> : <CandidateFeedbackInbox />;
}

function AssignedEvaluations({ manager }: { manager: boolean }) {
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const query = useQuery({ queryKey: ["evaluations", "directory", search, page], queryFn: () => api<Collection>("/evaluations?" + new URLSearchParams({ q: search, page_number: String(page) })), refetchInterval: 15000 });
  return <section className="surface vacancy-board">
    <header className="vacancy-board-heading"><span><ClipboardCheck size={24} /></span><div><h2>Avaliações atribuídas a você</h2><p>Consulte as fichas pendentes e os resultados das avaliações enviadas.</p></div></header>
    <div className="vacancy-board-filters"><label className="message-search"><Search size={18} aria-hidden="true" /><input type="search" aria-label="Buscar avaliações por categoria" placeholder="Buscar pela categoria da avaliação" value={search} onChange={event => { setSearch(event.target.value); setPage(1); }} /></label></div>
    <ErrorBox error={query.error} />
    {query.isPending ? <p className="loading" role="status">Carregando avaliações…</p> : query.isError ? <button className="button secondary" onClick={() => void query.refetch()}>Tentar novamente</button> : !query.data?.items.length ? <Empty title={search ? "Nenhuma avaliação encontrada" : "Você ainda não tem avaliações atribuídas"}>{search ? "Tente buscar por outra categoria." : "O RH precisa atribuir uma ficha a você na aba Avaliações da candidatura. Após a atribuição, ela aparecerá aqui para preenchimento."}</Empty> : <><div className="vacancy-board-count" role="status">{query.data.total} {query.data.total === 1 ? "avaliação" : "avaliações"}</div><ul className="vacancy-board-list">{query.data.items.map(evaluation => <li key={evaluation.id}><div className="vacancy-board-identity"><span className="vacancy-board-code">{label(str(evaluation.category))}</span><Link to={`${manager ? "/gestor" : "/app"}/candidaturas/${str(evaluation.application_id)}?aba=evaluations`}>{str(evaluation.candidate_name) || "Pessoa candidata"}</Link><div className="vacancy-board-meta"><span>{str(evaluation.vacancy_title)}</span>{Boolean(evaluation.submitted_at) && <span>Enviada em {date(evaluation.submitted_at)}</span>}</div></div><div className="vacancy-board-tags"><span className={`task-state ${evaluation.submitted_at ? "done" : "pending"}`}>{evaluation.submitted_at ? "Concluída" : "Pendente"}</span>{Boolean(evaluation.submitted_at) && !evaluation.sealed && evaluation.score != null && <span className="vacancy-audience">Nota: {Number(evaluation.score).toLocaleString("pt-BR", { maximumFractionDigits: 2 })}/100</span>}</div><Link className="button secondary small" to={`${manager ? "/gestor" : "/app"}/candidaturas/${str(evaluation.application_id)}?aba=evaluations`}>{evaluation.submitted_at ? "Ver avaliação" : "Avaliar"}<ArrowRight size={16} /></Link></li>)}</ul></>}
    {query.data && query.data.total > 25 && <footer className="task-footer"><span>{query.data.total} avaliações</span><div className="pagination"><button className="button secondary small" disabled={page === 1} onClick={() => setPage(page - 1)}>Anterior</button><span>Página {page}</span><button className="button secondary small" disabled={page * 25 >= query.data.total} onClick={() => setPage(page + 1)}>Próxima</button></div></footer>}
  </section>;
}

