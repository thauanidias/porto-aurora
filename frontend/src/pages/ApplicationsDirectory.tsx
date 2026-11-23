import { useState } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { ArrowRight, BriefcaseBusiness, Search, FileText } from "lucide-react";
import { api, obj, str, type Collection, type Row } from "../lib/api";
import { useSession } from "../lib/session";
import { Badge, DataTable, Empty, ErrorBox, PageTitle } from "../components/ui";
import { date } from "../lib/labels";
import { TalentDirectory } from "./TalentDirectory";
import { compatibilityPercentage } from "../components/CandidateCompatibility";

export function ApplicationsDirectory({ internal = false, archive = false }: { internal?: boolean; archive?: boolean }) {
  const session = useSession();
  const [history, setHistory] = useState(false);
  const canView = Boolean(session.data?.permissions.includes("candidate.view"));
  const [q, setQ] = useState("");
  const [status, setStatus] = useState("");
  const [page, setPage] = useState(1);
  const [audience, setAudience] = useState("");
  const [selectedVacancy, setSelectedVacancy] = useState<Row | null>(null);
  const grouped = !archive && !selectedVacancy;
  const type = archive ? audience : internal ? "INTERNAL" : "EXTERNAL";
  const effectiveStatus = status;
  const query = useQuery({
    queryKey: ["rh-applications", type, q, effectiveStatus, page, selectedVacancy?.id],
    queryFn: () => api<Collection>("/applications?" + new URLSearchParams({ ...(type ? { recruitment_type: type } : {}), ...(selectedVacancy ? { vacancy_id: selectedVacancy.id } : {}), passed_screening: String(!archive), group_by_vacancy: String(grouped), include_ranking: String(!grouped && !archive), q, status: effectiveStatus, page_number: String(page) })),
    enabled: canView && (!archive || history),
    refetchInterval: 15000,
  });
  if (archive && !history) return <TalentDirectory onHistory={() => setHistory(true)} />;
  return <>
    {archive && <button className="button secondary" onClick={() => setHistory(false)}>Voltar aos perfis</button>}
    <PageTitle title={archive ? "Banco de talentos" : internal ? "Candidaturas internas" : "Candidaturas externas"} subtitle={archive ? "Histórico de todas as candidaturas internas e externas, em qualquer situação." : internal ? "Acompanhe os colaboradores inscritos nos processos seletivos internos." : "Acompanhe as inscrições nos processos seletivos externos."} actions={archive ? <Link className="button secondary" to="/app/grupos-talentos">Grupos de talentos</Link> : undefined} />
    {selectedVacancy && !archive && <div className="application-selected-vacancy"><button className="text-button" onClick={() => { setSelectedVacancy(null); setQ(""); setPage(1); }}>← Voltar às vagas</button><div><BriefcaseBusiness size={22} aria-hidden="true" /><h2>{str(selectedVacancy.title)}</h2></div><p>Somente pessoas aprovadas na triagem e que já avançaram para a próxima etapa.</p></div>}
    {archive && <p className="alert">Este histórico reúne as participações em todas as vagas às quais você tem acesso. Use os filtros para consultar processos em andamento ou encerrados e abra a candidatura para conferir seus registros.</p>}
    {!session.isPending && !canView ? <p className="alert" role="alert">Você não tem permissão para consultar candidaturas.</p> : <section className={"surface applications-directory" + (archive ? " application-archive" : "")} aria-label={archive ? "Histórico de todas as candidaturas" : internal ? "Lista de candidaturas internas" : "Lista de candidaturas externas"}>
      <div className="list-toolbar"><label className="field application-search-field"><span>Buscar pessoa ou vaga</span><div className="search-field"><Search size={18} aria-hidden="true" /><input aria-label="Buscar candidatura" placeholder="Digite o nome ou o cargo" value={q} onChange={e => { setQ(e.target.value); setPage(1); }} /></div></label><label className="field"><span>Situação</span><select value={effectiveStatus} onChange={e => { setStatus(e.target.value); setPage(1); }}><option value="">Todas as situações</option><option value="ACTIVE">Em andamento</option><option value="SELECTED">Selecionada</option><option value="RESERVE">Banco de reserva</option><option value="REJECTED">Não selecionada</option><option value="WITHDRAWN">Desistência</option><option value="PRE_ADMISSION">Pré-admissão</option><option value="HIRED">Contratada</option></select></label></div>
      {archive && <div className="archive-audience-filter"><label className="field"><span>Público</span><select value={audience} onChange={event => { setAudience(event.target.value); setPage(1); }}><option value="">Internas e externas</option><option value="INTERNAL">Internas</option><option value="EXTERNAL">Externas</option></select></label></div>}
      {(q || status || audience) && <div className="application-filter-summary"><span>{query.data?.total ?? "…"} resultados para os filtros selecionados</span><button className="text-button" onClick={() => { setQ(""); setStatus(""); setAudience(""); setPage(1); }}>Limpar filtros</button></div>}
      <ErrorBox error={query.error} />
      {query.isPending ? <p className="loading" role="status">{grouped ? "Carregando vagas…" : "Carregando candidaturas…"}</p> : query.isError ? <div className="padded"><button className="button secondary" onClick={() => void query.refetch()}>Tentar novamente</button></div> : !query.data?.items.length ? <Empty title={grouped ? "Nenhuma vaga com candidaturas" : q || status ? "Nenhuma candidatura encontrada" : archive ? "Nenhuma candidatura recebida" : internal ? "Nenhuma candidatura interna recebida" : "Nenhuma candidatura externa recebida"}>{q || status ? "Altere a busca ou a situação para consultar outros resultados." : "As inscrições aparecerão aqui quando os candidatos se inscreverem nas vagas."}</Empty> : grouped ? <div className="application-vacancy-groups"><p>{query.data.total} {query.data.total === 1 ? "vaga com candidaturas" : "vagas com candidaturas"}</p>{query.data.items.map(job => <article key={job.id} className="application-vacancy-group"><div className="application-vacancy-group-icon"><BriefcaseBusiness size={24} aria-hidden="true" /></div><div className="application-vacancy-group-body"><h2>{str(job.title)}</h2><small>{str(job.code)}</small><p><strong>{Number(job.application_count)} {Number(job.application_count) === 1 ? "candidatura" : "candidaturas"}</strong> nos filtros selecionados</p></div><div className="application-vacancy-group-actions"><Badge value={job.status} /><button type="button" className="button" onClick={() => { setSelectedVacancy(job); setQ(""); setPage(1); }}>Ver candidatos<ArrowRight size={16} aria-hidden="true" /></button></div></article>)}{query.data.total > 25 && <div className="pagination"><button className="button secondary small" disabled={page === 1} onClick={() => setPage(page - 1)}>Anterior</button><span>Página {page}</span><button className="button secondary small" disabled={page * 25 >= query.data.total} onClick={() => setPage(page + 1)}>Próxima</button></div>}</div> : <DataTable
        showDensity={false}
        data={query.data.items.map(row => ({ ...row, applicant: str(obj(row.candidate).name), enrolled_at: row.created_at }))} columns={archive ? ["applicant", "recruitment_type", "stage_name", "status"] : ["applicant", "compatibility_rank", "stage_name", "status"]}
        columnLabels={{ applicant: internal ? "Colaborador e vaga" : "Pessoa e vaga", compatibility_rank: "Posição na vaga", stage_name: "Etapa atual", ...(archive ? { recruitment_type: "Público" } : {}) }}
        cells={{
          recruitment_type: row => <span>{row.recruitment_type === "INTERNAL" ? "Interna" : "Externa"}</span>,
          compatibility_rank: row => <div className="application-list-rank" title="Entre candidaturas em andamento e em reserva da mesma vaga e público, considerando os registros disponíveis para seu acesso."><strong>{!["ACTIVE", "RESERVE"].includes(str(row.status)) ? "Fora do ranking" : row.compatibility_rank != null ? `${str(row.compatibility_rank)}º lugar` : "Sem posição"}</strong><small>{compatibilityPercentage(row) === null ? "Ainda não calculado" : `${compatibilityPercentage(row)!.toLocaleString("pt-BR", { maximumFractionDigits: 2 })}% de compatibilidade`}</small></div>,
          applicant: row => <div className="application-person">{!obj(row.candidate).blind && <span className="application-person-avatar" aria-hidden="true">{str(row.applicant).replace(/\[TESTE\]\s*/g, "").split(/\s+/).filter(Boolean).slice(0, 2).map(part => part[0]).join("")}</span>}<div className="application-person-info"><Link to={"/app/candidaturas/" + row.id}>{str(row.applicant)}</Link><span><BriefcaseBusiness size={13} aria-hidden="true" />{str(row.vacancy_title)}</span><small>Inscrição: {date(row.enrolled_at)}</small></div></div>,
          stage_name: row => <span className="application-stage">{str(row.stage_name)}</span>,
          enrolled_at: row => <span className="application-date">{date(row.enrolled_at)}</span>,
        }}
        total={query.data.total} page={page} pageSize={query.data.page_size ?? 25} onPage={setPage}
        actions={row => <div className="application-row-actions"><Link className="application-open" to={"/app/candidaturas/" + row.id} aria-label={"Acompanhar candidatura de " + str(row.applicant)}>Acompanhar <ArrowRight size={15} aria-hidden="true" /></Link>{internal && !obj(row.candidate).blind && <Link className="application-documents" title="Ver documentos" to={"/app/documentos/" + str(row.candidate_id)} aria-label={"Ver documentos de " + str(row.applicant)}><FileText size={18} aria-hidden="true" /></Link>}</div>}
      />}
    </section>}
  </>;
}

