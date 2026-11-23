import { ProfilePhoto } from "./ProfilePhoto";
import { useState } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { ArrowRight, FolderOpen, Search } from "lucide-react";
import { api, rows, str, type Collection, type Row } from "../lib/api";
import { AdmissionDocuments } from "./AdmissionDocuments";
import { CandidateDocumentFiles } from "./CandidateDocumentFiles";
import { RHSelectionDocuments } from "./RHSelectionDocuments";
import { RHInternalDownloads } from "./RHInternalDownloads";
import { Empty, ErrorBox } from "./ui";

export function RHDocumentProfiles({ candidateId }: { candidateId?: string }) {
  const [q, setQ] = useState("");
  const [page, setPage] = useState(1);
  const query = useQuery({ queryKey: ["document-candidates", q, page], queryFn: () => api<Collection>("/document-candidates?" + new URLSearchParams({ q, page_number: String(page) })), enabled: !candidateId, refetchInterval: 15000 });
  const profile = useQuery({ queryKey: ["candidate", candidateId], queryFn: () => api<Row>("/candidates/" + candidateId), enabled: Boolean(candidateId) });
  if (candidateId) return <>
    <Link className="back-link" to="/app/documentos">← Voltar aos perfis de documentos</Link>
    <ErrorBox error={profile.error} />
    {profile.isPending ? <p role="status">Carregando perfil…</p> : profile.data && <>
      <section className="surface padded candidate-document-profile-heading"><div className="document-folder-person">{!profile.data.blind && <ProfilePhoto candidateId={candidateId} name={str(profile.data.name)} />}<div><p className="eyebrow">PASTA DO CANDIDATO</p><h2>{str(profile.data.name)}</h2></div></div><Link className="button secondary" to={"/app/candidatos/" + candidateId}>Ver perfil completo <ArrowRight size={16} /></Link></section>
      {profile.data.blind ? <p className="alert">Os documentos ficam disponíveis quando a identidade for liberada para esta candidatura.</p> : <>
        <RHInternalDownloads candidateId={candidateId} />
        <CandidateDocumentFiles key={candidateId} candidateId={candidateId} />
        <RHSelectionDocuments candidate={profile.data} />
        <AdmissionDocuments candidateId={candidateId} />
      </>}
    </>}
  </>;
  return <>
    <section className="surface candidate-document-directory"><header className="document-directory-toolbar"><div><h2>Pastas dos candidatos{query.data && <span className="document-directory-count">{query.data.total} {query.data.total === 1 ? "perfil" : "perfis"}</span>}</h2><p>Currículos, fichas e anexos organizados por pessoa.</p></div><label className="document-directory-search"><Search size={18} aria-hidden="true" /><input aria-label="Buscar perfil de documentos" value={q} onChange={e => { setQ(e.target.value); setPage(1); }} placeholder="Buscar candidato pelo nome" />{q && <button type="button" className="text-button" onClick={() => { setQ(""); setPage(1); }}>Limpar</button>}</label></header>
      <ErrorBox error={query.error} />
      {query.isPending ? <p className="loading" role="status">Carregando perfis…</p> : query.isError ? <div className="padded"><button className="button secondary" onClick={() => void query.refetch()}>Tentar novamente</button></div> : !query.data?.items.length ? <Empty title={q ? "Nenhum perfil encontrado" : "Nenhum candidato avançou para esta fase"}>{q ? "Tente outro nome." : "Os perfis aparecerão quando os candidatos chegarem à fase de testes."}</Empty> : <div className="candidate-document-profile-grid">{query.data.items.map(person => <article className="candidate-document-profile" key={person.id}>
        <header className="document-folder-person">{!person.blind ? <ProfilePhoto candidateId={str(person.id)} name={str(person.name)} /> : <span className="rediscovery-heading-icon"><FolderOpen size={24} aria-hidden="true" /></span>}<div><h3>{str(person.name)}</h3><span className="muted">Pasta de documentos</span></div></header>
        <div className="candidate-document-processes">{rows(person.processes).map((process, index) => <div className="document-process-entry" key={index}><strong>{str(process.vacancy_title)}</strong><span className={"document-process-stage" + (str(process.stage_name).toLowerCase().includes("finalista") ? " is-finalist" : "")}>{str(process.stage_name)}</span></div>)}</div>
        <div className="document-folder-count"><FolderOpen size={20} aria-hidden="true" /><div><strong>{person.blind ? "Acesso protegido" : str(person.document_count)}</strong><span>{person.blind ? "Identidade protegida nesta etapa" : person.document_count === 1 ? "arquivo enviado" : "arquivos enviados"}</span></div></div>
        <Link className="button document-folder-open" to={"/app/documentos/" + person.id} aria-label={"Ver documentos de " + str(person.name)}>Abrir documentos<ArrowRight size={16} /></Link>
      </article>)}</div>}
      {(query.data?.total ?? 0) > 25 && <div className="pagination"><button className="button secondary small" disabled={page === 1} onClick={() => setPage(page - 1)}>Anterior</button><span>Página {page}</span><button className="button secondary small" disabled={page * 25 >= (query.data?.total ?? 0)} onClick={() => setPage(page + 1)}>Próxima</button></div>}
    </section>
  </>;
}
