import { lazy, Suspense, useState } from "react";
import { Link } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api, documentBlob, download, obj, post, str, type Collection, type Row } from "../lib/api";
import { useSession } from "../lib/session";
import { CandidateScreeningProfile } from "./CandidateScreeningProfile";
import { Empty, ErrorBox, Modal } from "./ui";
import { ProfilePhoto } from "./ProfilePhoto";
import { compatibilityPercentage, compatibilityCategory, compatibilityReport } from "./CandidateCompatibility";
import { ArrowRight, CheckCircle2, Eye, Search, Trophy, UserRound, XCircle } from "lucide-react";

const ResumePreview = lazy(() => import("./ResumePreview"));

export function ResumeScreening({ vacancyId }: { vacancyId: string; stages: Row[] }) {
  const session = useSession();
  const client = useQueryClient();
  const [q, setQ] = useState("");
  const [status, setStatus] = useState("ACTIVE");
  const [order, setOrder] = useState("compatibility");
  const [page, setPage] = useState(1);
  const [decision, setDecision] = useState<{ application: Row; approved: boolean } | null>(null);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>();
  const [message, setMessage] = useState("");
  const [loadingResume, setLoadingResume] = useState("");
  const [preview, setPreview] = useState<{ data: Uint8Array; pdf: boolean; documentId: string; name: string }>();
  const query = useQuery({ queryKey: ["resume-screening", vacancyId, q, status, page, order],
    queryFn: () => api<Collection>("/applications?" + new URLSearchParams({ vacancy_id: vacancyId, q, status, order_by: order, screening_only: status === "REJECTED" ? "false" : "true", page_number: String(page), page_size: "25" })),
    enabled: Boolean(session.data?.permissions.includes("candidate.view")),
  });
  const feedback = useQuery({ queryKey: ["rejection-email", decision?.application.id],
    queryFn: () => api<Row>(`/applications/${decision?.application.id}/rejection-email`),
    enabled: Boolean(decision && !decision.approved && session.data?.permissions.includes("message.send")),
  });
  const choose = (application: Row, approved: boolean) => { setDecision({ application, approved }); setReason(""); setError(undefined); setMessage(""); };
  const confirm = async () => {
    if (!decision || busy || reason.trim().length < 5) return;
    setBusy(true); setError(undefined);
    const { application, approved } = decision;
    try {
      const result = await post<Row>(`/applications/${application.id}/${approved ? "approve-screening" : "decision"}`, approved
        ? { reason: reason.trim(), version: application.version }
        : { decision: "REJECTED", reason: reason.trim(), version: application.version, send_rejection_email: true });
      setDecision(null);
      if (query.data?.items.length === 1 && page > 1) setPage(page - 1);
      setMessage(approved ? "Triagem aprovada. A pessoa saiu da triagem e avançou para " + str(result.stage_name) + "." : "Candidatura encerrada nesta vaga. E-mail de retorno colocado na fila de envio. O cadastro e o currículo foram preservados.");
      await Promise.all(["resume-screening", "vacancy-applications", "rh-applications", "candidate-processes", "application", "dashboard"].map(key => client.invalidateQueries({ queryKey: [key] })));
    } catch (err) { setError(err); } finally { setBusy(false); }
  };
  if (!session.isPending && !session.data?.permissions.includes("candidate.view")) return <p className="alert">Você não tem permissão para consultar a triagem desta vaga.</p>;
  return <section className="surface padded resume-screening" aria-label="Triagem de currículos da vaga">
    <header className="screening-overview"><div><p className="privacy-eyebrow">TRIAGEM DE CURRÍCULOS</p><h2>Quem segue para a próxima etapa?</h2><p>Leia o currículo, confira a compatibilidade e confirme sua decisão no cartão.</p></div><span className="screening-result-count" role="status">{query.isPending ? "Consultando…" : query.isError ? "Consulta indisponível" : `${query.data?.total ?? 0} ${(query.data?.total ?? 0) === 1 ? "candidatura encontrada" : "candidaturas encontradas"}`}</span></header>
    <div className="screening-decision-guide" aria-label="Como funcionam as decisões da triagem"><div><CheckCircle2 size={19} aria-hidden="true" /><p><strong>Apto e avançar</strong><span>Aprova o currículo e libera a próxima etapa.</span></p></div><div><XCircle size={19} aria-hidden="true" /><p><strong>Não apto para esta vaga</strong><span>Encerra a candidatura e prepara o e-mail de retorno. O histórico é preservado.</span></p></div></div>
    <div className="process-filters screening-main-filters">
      <label className="field screening-search"><span>Buscar candidato</span><div><Search size={17} aria-hidden="true" /><input type="search" value={q} placeholder="Digite o nome do candidato" onChange={e => { setQ(e.target.value); setPage(1); }} /></div></label>
      <label className="field"><span>Quais currículos mostrar?</span><select value={status} onChange={e => { setStatus(e.target.value); setPage(1); }}><option value="ACTIVE">Em análise</option><option value="RESERVE">Em reserva</option><option value="REJECTED">Não selecionados nesta vaga</option></select></label>
      <label className="field"><span>Ordenar candidatos</span><select value={order} onChange={e => { setOrder(e.target.value); setPage(1); }}><option value="compatibility">Maior compatibilidade com a vaga</option><option value="recent">Inscrições mais recentes</option></select></label>
    </div>
    {(q || status !== "ACTIVE" || order !== "compatibility") && <button type="button" className="text-button" onClick={() => {setQ("");setStatus("ACTIVE");setOrder("compatibility");setPage(1);}}>Limpar filtros</button>}
    <ErrorBox error={query.error ?? (!decision ? error : undefined)} />
    {message && <p className="alert success" role="status">{message}</p>}
    {query.isPending ? <p role="status">Carregando currículos…</p> : query.isError ? <button className="button secondary" onClick={() => void query.refetch()}>Tentar novamente</button> : !query.data?.items.length ? <Empty title="Nenhum currículo nesta visualização">Altere os filtros ou consulte os não selecionados para ver as candidaturas encerradas.</Empty> : <>
      <div className="screening-cards">{query.data.items.map(application => <article className="screening-card" key={application.id}>
        <div className="section-heading"><div className="screening-person">{!obj(application.candidate).blind && Boolean(application.candidate_id) && <ProfilePhoto candidateId={str(application.candidate_id)} name={str(obj(application.candidate).name)} />}<div><h3>{str(obj(application.candidate).name)}</h3><p>{application.recruitment_type === "INTERNAL" ? "Colaborador · Seleção interna" : "Candidato · Seleção externa"} · {str(application.stage_name)}</p></div></div><span className="screening-label">{application.status === "REJECTED" ? "Não selecionado nesta vaga" : "Aguardando decisão do RH"}</span></div>
        <div className="screening-fit-row"><Link className={"screening-fit-badge fit-" + compatibilityCategory(application)} to={`/app/candidaturas/${application.id}?aba=score`} aria-label={`Ver compatibilidade de ${str(obj(application.candidate).name)}`}>
          {application.compatibility_rank != null && <span className="screening-rank"><Trophy size={17} aria-hidden="true" />{str(application.compatibility_rank)}º no ranking</span>}
          <strong>{compatibilityPercentage(application) === null ? "Compatibilidade não calculada" : compatibilityPercentage(application)!.toLocaleString("pt-BR", { maximumFractionDigits: 2 }) + "% de compatibilidade"}</strong>
          {compatibilityReport(application).status === "PENDING" && <small>Resultado provisório</small>}
          {compatibilityPercentage(application) !== null && <progress className="screening-fit-progress" max={100} value={compatibilityPercentage(application)!} aria-label="Compatibilidade com a vaga" />}
        </Link>{["ACTIVE", "RESERVE"].includes(str(application.status)) && session.data?.permissions.includes("candidate.move") && <button className="button small screening-advance" disabled={busy} onClick={() => choose(application, true)}><CheckCircle2 size={17} aria-hidden="true" />Apto e avançar<ArrowRight size={16} aria-hidden="true" /></button>}</div>
        <CandidateScreeningProfile candidate={obj(application.candidate) as Row} />
        <div className="actions">
          {Boolean(application.cv_id) && !obj(application.candidate).blind && <button className="button secondary" disabled={Boolean(loadingResume)} onClick={async () => {
            if (loadingResume) return;
            setError(undefined); setLoadingResume(application.id);
            try {
              const blob = await documentBlob(`/documents/${application.cv_id}/download`);
              const data = new Uint8Array(await blob.arrayBuffer());
              setPreview({ data, pdf: new TextDecoder().decode(data.slice(0, 5)) === "%PDF-", documentId: str(application.cv_id), name: str(obj(application.candidate).name) });
            } catch (err) { setError(err); } finally { setLoadingResume(""); }
          }}><Eye size={17} aria-hidden="true" />{loadingResume === application.id ? "Carregando currículo…" : "Visualizar currículo"}</button>}
          {!application.cv_id && <span className="muted">Currículo não disponível nesta candidatura.</span>}
          <Link className="button secondary" to={`/app/candidaturas/${application.id}?aba=profile`}><UserRound size={17} aria-hidden="true" />Ver perfil completo</Link>
          {["ACTIVE", "RESERVE"].includes(str(application.status)) && <>
            {session.data?.permissions.includes("candidate.select") && session.data.permissions.includes("message.send") && <button className="button secondary screening-reject" disabled={busy} onClick={() => choose(application, false)}><XCircle size={17} aria-hidden="true" />Não apto para esta vaga</button>}
          </>}
          <Link className="text-button" to={`/app/candidaturas/${application.id}`}>Acompanhar etapas<ArrowRight size={16} aria-hidden="true" /></Link>
        </div>
      </article>)}</div>
      {query.data.total > 25 && <div className="pagination"><button className="button secondary" disabled={page === 1} onClick={() => setPage(page - 1)}>Anterior</button><span>Página {page}</span><button className="button secondary" disabled={page * 25 >= query.data.total} onClick={() => setPage(page + 1)}>Próxima</button></div>}
    </>}
    <Modal open={Boolean(preview)} title={"Currículo · " + (preview?.name ?? "")} onOpenChange={open => { if (!open) setPreview(undefined); }}>
      {preview && (preview.pdf ? <Suspense fallback={<p role="status">Carregando currículo…</p>}><ResumePreview data={preview.data} /></Suspense> : <><p>Este currículo está em formato Word. Baixe o arquivo para consultar o conteúdo.</p><button className="button" onClick={async () => { try { await download(`/documents/${preview.documentId}/download`, "curriculo"); } catch (err) { setError(err); } }}>Baixar currículo</button></>)}
    </Modal>
    <Modal open={Boolean(decision)} title={decision?.approved ? "Marcar currículo como apto" : "Não apto para esta vaga"} onOpenChange={open => { if (!open && !busy) setDecision(null); }}>
      {decision && <form onSubmit={e => { e.preventDefault(); void confirm(); }}>
        <p><strong>{str(obj(decision.application.candidate).name)}</strong> · {str(decision.application.stage_name)}</p>
        <p>{decision.approved ? "O parecer será registrado e a pessoa avançará para a próxima etapa da vaga, saindo da triagem. Se houver pendências, nenhuma alteração será concluída." : "A candidatura será encerrada nesta vaga e o e-mail de não seleção será colocado na fila de envio. Seu cadastro e currículo serão preservados. A justificativa interna abaixo não será incluída no e-mail."}</p>
        {!decision.approved && <>
          {feedback.data?.test_mode === true && <p className="alert">Modo de testes: o retorno será entregue na caixa de e-mails de teste, sem envio externo.</p>}
          {feedback.data?.delivery_enabled === false && <p className="alert" role="alert">O envio de e-mails está desativado. Configure o serviço antes de confirmar a não seleção com retorno automático.</p>}
          <ErrorBox error={feedback.error} />
          {Boolean(feedback.data?.body) && <details><summary>Conferir e-mail de retorno</summary><strong>{str(feedback.data?.subject)}</strong><p style={{ whiteSpace: "pre-wrap" }}>{str(feedback.data?.body)}</p></details>}
        </>}
        <label className="field"><span>Justificativa profissional</span><textarea required minLength={5} maxLength={4000} rows={4} value={reason} onChange={e => setReason(e.target.value)} placeholder="Explique quais requisitos da vaga foram ou não atendidos." disabled={busy} /></label>
        <ErrorBox error={error} />
        <div className="actions"><button type="button" className="button secondary" disabled={busy} onClick={() => setDecision(null)}>Cancelar</button><button className="button" disabled={busy || reason.trim().length < 5 || !decision.approved && (feedback.isPending || feedback.isError || feedback.data?.delivery_enabled === false)}>{busy ? "Registrando…" : decision.approved ? "Confirmar apto e avançar" : "Confirmar não apto e enviar retorno"}</button></div>
      </form>}
    </Modal>
  </section>;
}
