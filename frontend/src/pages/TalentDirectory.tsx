import { Search, History, UsersRound, MapPin, CheckCircle2, ArrowRight } from "lucide-react";
import { ProfilePhoto } from "../components/ProfilePhoto";
import { useState } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api, str, type Row, type Collection } from "../lib/api";
import { useSession } from "../lib/session";
import { Badge, DataTable, Empty, ErrorBox, PageTitle } from "../components/ui";

export function TalentDirectory({ onHistory }: { onHistory: () => void }) {
  const session = useSession();
  const canView = Boolean(session.data?.permissions.includes("candidate.view"));
  const [q, setQ] = useState("");
  const [audience, setAudience] = useState("");
  const [page, setPage] = useState(1);
  const query = useQuery({
    queryKey: ["talent-profiles", q, audience, page],
    queryFn: () => api<Collection>("/candidates?" + new URLSearchParams({ q, recruitment_type: audience, page_number: String(page) })),
    enabled: canView,
    refetchInterval: 15000,
  });
  return <>
    <PageTitle title="Banco de talentos" subtitle="Perfis e participações em processos seletivos, reunidos em um só lugar." actions={<><button className="button" onClick={onHistory}><History size={17} />Histórico de candidaturas</button><Link className="button secondary" to="/app/grupos-talentos"><UsersRound size={17} />Grupos de talentos</Link></>} />
    <div className="talent-bank-intro"><History size={19} aria-hidden="true" /><div><strong>Uma visão completa de cada trajetória</strong><p>Consulte o perfil e abra uma vaga do histórico para conferir as etapas e os registros da candidatura.</p></div><details><summary>Sobre este banco</summary><p>Os perfis permanecem disponíveis independentemente do resultado do processo. A participação em novas oportunidades depende da autorização vigente e das permissões de acesso.</p></details></div>
    {!session.isPending && !canView ? <p className="alert" role="alert">Você não tem permissão para consultar perfis.</p> : <section className="surface applications-directory talent-bank-directory" aria-label="Perfis do banco de talentos">
      <div className="talent-bank-filters"><label className="field"><span>Buscar perfil</span><div className="search-field"><Search size={18} aria-hidden="true" /><input value={q} placeholder="Digite o nome, a cidade ou uma competência" onChange={e => { setQ(e.target.value); setPage(1); }} /></div></label><label className="field"><span>Público</span><select value={audience} onChange={e => { setAudience(e.target.value); setPage(1); }}><option value="">Internos e externos</option><option value="INTERNAL">Internos</option><option value="EXTERNAL">Externos</option></select></label>{Boolean(q || audience) && <button className="text-button" onClick={() => { setQ(""); setAudience(""); setPage(1); }}>Limpar filtros</button>}</div>
      <ErrorBox error={query.error} />
      {query.isPending ? <p className="loading" role="status">Carregando perfis…</p> : query.isError ? <div className="padded"><button className="button secondary" onClick={() => void query.refetch()}>Tentar novamente</button></div> : !query.data?.items.length ? <Empty title="Nenhum perfil encontrado">Os perfis cadastrados aparecerão aqui, mesmo sem candidaturas ou com processos ainda em andamento.</Empty> : <DataTable
        data={query.data.items} columns={["name", "recruitment_type", "vacancy_titles", "talent_available"]}
        columnLabels={{ name: "Pessoa", recruitment_type: "Público", talent_available: "Uso em novas vagas", vacancy_titles: "Histórico de vagas" }}
        cells={{
          name: row => <div className="talent-profile-identity">{!row.blind && <ProfilePhoto candidateId={str(row.id)} name={str(row.name)} />}<div><Link to={"/app/candidatos/" + row.id}>{str(row.name)}</Link>{!row.blind && <span><MapPin size={13} aria-hidden="true" />{str(row.city) || "Cidade não informada"}</span>}</div></div>,
          recruitment_type: row => <span className={"talent-audience-tag " + (row.recruitment_type === "INTERNAL" ? "is-internal" : "")}>{row.recruitment_type === "INTERNAL" ? "Colaborador interno" : "Candidato externo"}</span>,
          talent_available: row => <span className={"talent-permission-tag " + (row.talent_available ? "is-authorized" : "")}>{Boolean(row.talent_available) && <CheckCircle2 size={14} aria-hidden="true" />}{row.talent_available ? "Autorizado" : "Sem autorização vigente"}</span>,
          vacancy_titles: row => Array.isArray(row.process_history) && row.process_history.length ? <ul className="talent-process-history">{row.process_history.map((process: Row) => <li key={str(process.application_id)}><Link to={"/app/candidaturas/" + str(process.application_id)}>{str(process.vacancy_title)}<ArrowRight size={13} aria-hidden="true" /></Link><div>{process.stage_kind === "FINALIST" && <span className="candidate-finalist-badge">Finalista</span>}<Badge value={process.status} /></div>{process.stage_kind !== "FINALIST" && <small>{str(process.stage_name)}</small>}</li>)}</ul> : <span className="muted">Ainda não participou de uma vaga</span>,
        }}
        total={query.data.total} page={page} pageSize={query.data.page_size ?? 25} onPage={setPage}
        actions={row => <Link className="button secondary small" to={"/app/candidatos/" + row.id}>Ver perfil e registros</Link>}
      />}
    </section>}
  </>;
}
