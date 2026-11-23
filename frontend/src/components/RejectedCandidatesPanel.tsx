import { useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { Eye, ArrowRight } from "lucide-react";
import { obj, str, type Collection, type Row } from "../lib/api";
import { ProfilePhoto } from "./ProfilePhoto";
import { CandidateResume } from "./CandidateResume";
import { Modal } from "./ui";

export function RejectedCandidatesPanel({ data, pending, page, onPage }: { data?: Collection; pending: boolean; page: number; onPage: (page: number) => void }) {
  const [preview, setPreview] = useState<Row | null>(null);
  const location = useLocation();
  const base = location.pathname.startsWith("/gestor") ? "/gestor" : "/app";
  return <section className="surface padded rejected-candidates-panel"><h2>Não selecionados</h2><p className="muted">Candidaturas encerradas sem seleção nesta vaga. Os currículos e o histórico permanecem disponíveis para consulta.</p>
    {pending && <p role="status">Carregando candidaturas…</p>}
    {!pending && data && !data.total && <p className="compare-help">Nenhuma candidatura foi encerrada como não selecionada nesta vaga.</p>}
    <div className="rejected-candidate-grid">{data?.items.map(row => <article className="rejected-candidate-card" key={row.id}><div className="rediscovery-person">{!obj(row.candidate).blind && <ProfilePhoto candidateId={str(row.candidate_id)} name={str(obj(row.candidate).name)} />}<div><h3>{str(obj(row.candidate).name)}</h3><span className="muted">Última etapa: {str(row.stage_name)}</span></div></div><span className="rejected-candidate-label">Não selecionado</span>{Boolean(row.closure_reason) && <p className="preserve">{str(row.closure_reason)}</p>}<div className="actions">{!obj(row.candidate).blind && <button className="button secondary" onClick={() => setPreview(row)}><Eye size={16} />Visualizar currículo</button>}<Link className="button secondary" to={`${base}/candidaturas/${row.id}`}>Ver candidatura<ArrowRight size={16} /></Link></div></article>)}</div>
    {data && data.total > 25 && <div className="pagination"><button className="button secondary" disabled={page === 1} onClick={() => onPage(page - 1)}>Anterior</button><span>Página {page}</span><button className="button secondary" disabled={page * 25 >= data.total} onClick={() => onPage(page + 1)}>Próxima</button></div>}
    <Modal open={Boolean(preview)} onOpenChange={open => { if (!open) setPreview(null); }} title="Currículo da candidatura não selecionada">{preview && <CandidateResume candidateId={str(preview.candidate_id)} />}</Modal>
  </section>;
}
