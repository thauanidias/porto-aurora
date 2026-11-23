import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { ClipboardList, ExternalLink, Link2, Search } from "lucide-react";
import { api, obj, post, put, str, type Collection } from "../lib/api";
import { useSession } from "../lib/session";
import { Empty, ErrorBox, PageTitle } from "../components/ui";
import { InterviewLinkForm } from "../components/InterviewLinkForm";
import { InterviewAttachmentButton } from "../components/InterviewAttachmentButton";
import { QuestionnairePreview, TestQuestionnaireEditor } from "../components/TestQuestionnaire";
import { OperationModal, ResourcePage, type Operation } from "./Resources";

export function TestCandidatesPage() {
  const [tab, setTab] = useState("candidates");
  const [q, setQ] = useState("");
  const [page, setPage] = useState(1);
  const [operation, setOperation] = useState<Operation | null>(null);
  const session = useSession();
  const navigate = useNavigate();
  const query = useQuery({ queryKey: ["test-candidates", q, page], queryFn: () => api<Collection>("/test-candidates?" + new URLSearchParams({ q, page_number: String(page) })), refetchInterval: 15000 });
  const canEdit = Boolean(session.data?.permissions.includes("test.manage"));
  return <>
    <div className="tabs" role="tablist"><button role="tab" aria-selected={tab === "candidates"} className={tab === "candidates" ? "active" : ""} onClick={() => setTab("candidates")}>Candidatos em testes</button>
      <button role="tab" aria-selected={tab === "library"} className={tab === "library" ? "active" : ""} onClick={() => setTab("library")}>Biblioteca de testes</button></div>
    {tab === "library" ? <ResourcePage kind="tests" /> : <>
      <PageTitle title="Testes" subtitle="Candidatos que avançaram para os testes. Envie o link e prepare um questionário para cada candidatura." />
      <div className="surface interview-directory"><div className="list-toolbar"><label className="search-field"><Search size={18} /><input aria-label="Buscar candidato ou vaga" placeholder="Buscar candidato ou vaga" value={q} onChange={event => { setQ(event.target.value); setPage(1); }} /></label></div>
        <ErrorBox error={query.error} />
        {query.isPending ? <p className="loading" role="status">Carregando candidatos…</p> : !query.error && !query.data?.items.length ? <Empty title="Nenhum candidato na fase de testes">{q ? "Tente buscar por outro nome ou vaga." : "Os candidatos aparecerão aqui quando forem movidos para a etapa de testes."}</Empty> : <>
          <div className="interview-list-heading"><span><strong>{query.data?.total ?? 0}</strong> {query.data?.total === 1 ? "candidato" : "candidatos"} na fase de testes</span></div>
          <div className="interview-candidate-list">{query.data?.items.map(row => {
            const name = str(obj(row.candidate).name);
            const links = Array.isArray(row.test_links) ? row.test_links as Record<string, unknown>[] : [];
            return <article className="interview-candidate" key={row.id}>
              <div className="interview-candidate-header"><div className="interview-candidate-person"><span className="interview-person-avatar" aria-hidden="true">{name.slice(0, 2).toUpperCase()}</span><div><h2>{name}</h2><p>{str(row.vacancy_title)}</p></div></div>
                <span className={"interview-link-status " + (links.length ? "ready" : "pending")}>{links.length ? "Link disponível" : "Link pendente"}</span></div>
              <div className="interview-candidate-body"><div className="interview-link-panel">{links.length ? links.map(link => <div key={str(link.id)} className="interview-saved-link"><Link2 size={18} /><div><a href={str(link.url)} target="_blank" rel="noopener noreferrer">{str(link.title)} <ExternalLink size={14} /></a><p className="preserve">{str(link.description)}</p></div></div>) : <><strong>Adicione o link do teste</strong><p>Inclua o prazo e as orientações para realizar a atividade.</p></>}</div>
                {session.data?.permissions.includes("candidate.move") && <button className="button interview-attach-button" onClick={() => setOperation({ title: "Anexar link do teste · " + name, renderForm: submit => <InterviewLinkForm kind="TEST" onSubmit={submit} />, run: data => post("/candidate-activity-links", { ...data, kind: "TEST", application_id: row.id }) })}><Link2 size={16} />Anexar link do teste</button>}</div>
              <div className="test-candidate-questionnaire"><div className="section-heading"><h3><ClipboardList size={17} /> Miniquestionário</h3>{canEdit && <button className="button secondary small" onClick={() => setOperation({ title: "Editar questionário · " + name, renderForm: submit => <TestQuestionnaireEditor row={row} onSubmit={submit} />, run: data => put("/applications/" + row.id + "/test-questionnaire", data) })}>Editar perguntas</button>}</div>
                <QuestionnairePreview value={row.test_questionnaire} /></div>
              <div className="interview-candidate-footer"><span className="interview-stage">{str(row.stage_name)}</span><div className="interview-secondary-actions"><InterviewAttachmentButton application={row} /><button className="text-button" onClick={() => navigate("/app/candidaturas/" + row.id)}>Ver candidatura</button></div></div>
            </article>;
          })}</div>
          {(query.data?.total ?? 0) > 25 && <div className="interview-pagination"><button className="button secondary small" disabled={page === 1} onClick={() => setPage(page - 1)}>Anterior</button><span>Página {page}</span><button className="button secondary small" disabled={page * 25 >= (query.data?.total ?? 0)} onClick={() => setPage(page + 1)}>Próxima</button></div>}
        </>}
      </div>
    </>}
    <OperationModal operation={operation} onClose={() => setOperation(null)} />
  </>;
}
