import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api, obj, post, put, rows, str, type Row } from "../lib/api";
import { useSession } from "../lib/session";
import { date, label } from "../lib/labels";
import { ErrorBox } from "./ui";
import { RecordDetail } from "../pages/Resources";

export function ProcessWorkflow({ application }: { application: Row }) {
  const client = useQueryClient();
  const session = useSession();
  const canMove = Boolean(session.data?.permissions.includes("candidate.move"));
  const active = ["ACTIVE", "RESERVE"].includes(str(application.status));
  const [status, setStatus] = useState("PENDING");
  const [reason, setReason] = useState("");
  const [source, setSource] = useState(str(application.source));
  const [sendEmail, setSendEmail] = useState(false);
  const [link, setLink] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>();
  const [message, setMessage] = useState("");
  const reviews = useQuery({ queryKey: ["stage-reviews", application.id], queryFn: () => api<{ items: Row[] }>(`/applications/${application.id}/stage-reviews`) });
  const form = useQuery({ queryKey: ["process-form", application.id], queryFn: () => api<Row>(`/applications/${application.id}/process-form`), refetchInterval: 15000 });
  const formAllowed = obj(obj(application.candidate_access).permissions).process_form === true;
  const perform = async (action: () => Promise<unknown>, success: string) => {
    if (busy) return;
    setBusy(true); setError(undefined); setMessage("");
    try { await action(); setMessage(success); await client.invalidateQueries(); }
    catch (err) { setError(err); } finally { setBusy(false); }
  };
  return <section className="surface padded process-workflow" aria-label="Parecer e ficha da candidatura">
    <h2>Análise e ficha deste processo</h2><p className="muted">Os pareceres e as respostas pertencem somente a esta candidatura. Registrar um parecer não movimenta o candidato.</p>
    <ErrorBox error={error ?? reviews.error ?? form.error} />
    {message && <p className="alert success" role="status">{message}</p>}
    {canMove && <form onSubmit={event => { event.preventDefault(); void perform(() => put(`/applications/${application.id}/source`, { source, version: application.version }), "Origem atualizada."); }} className="process-review-form">
      <label className="field"><span>Origem da candidatura</span><select value={source} onChange={e => setSource(e.target.value)}>{["PORTAL", "WHATSAPP", "INSTAGRAM", "LINKEDIN", "INDICACAO", "BANCO_TALENTOS", "IMPORTACAO", "OUTRO"].map(value => <option key={value} value={value}>{label(value)}</option>)}</select></label>
      <button className="button secondary" disabled={busy || source === application.source}>Salvar origem</button>
    </form>}
    {canMove && active && <form onSubmit={event => { event.preventDefault(); void perform(async () => { await post(`/applications/${application.id}/stage-reviews`, { status, reason, version: application.version }); setReason(""); }, "Parecer registrado. Use o controle de etapas para avançar após a aprovação."); }}>
      <label className="field"><span>Parecer da etapa: {str(application.stage_name)}</span><select value={status} onChange={e => setStatus(e.target.value)}><option value="PENDING">Pendente de análise</option><option value="APPROVED">Aprovado</option><option value="REJECTED">Reprovado</option></select></label>
      <label className="field"><span>Observações e justificativa do recrutador</span><textarea required minLength={5} maxLength={4000} rows={3} value={reason} onChange={e => setReason(e.target.value)} /></label><button className="button secondary" disabled={busy || reason.trim().length < 5}>Registrar parecer</button>
    </form>}
    {rows(reviews.data?.items).length > 0 && <details><summary>Histórico de pareceres ({reviews.data?.items.length})</summary>{reviews.data?.items.map(item => <article key={item.id}><strong>{label(str(item.status))}</strong> · {date(item.created_at)}<p>{str(item.reason)}</p></article>)}</details>}
    <hr /><h3>Perguntas e ficha externa por link seguro</h3>
    <p>Situação: <strong>{({ NOT_SENT: "Não enviada", SENT: "Link disponibilizado", PENDING: "Preenchimento pendente", COMPLETED: "Preenchida" } as Record<string, string>)[str(form.data?.status)] ?? "Carregando…"}</strong></p>
    {Boolean(form.data?.sent_at) && <p className="muted">Disponibilizada em {date(form.data?.sent_at)} · Preenchida em {date(form.data?.submitted_at)}</p>}
    {canMove && active && form.data?.status !== "COMPLETED" && <>
      {!formAllowed && <p className="muted">Avance para Perguntas e ficha externa para liberar esta atividade.</p>}
      {session.data?.permissions.includes("message.send") && <label className="check-field"><input type="checkbox" checked={sendEmail} onChange={e => setSendEmail(e.target.checked)} /><span>Enviar o link também para o e-mail cadastrado</span></label>}
      <button className="button secondary" disabled={busy || !formAllowed || form.isPending} onClick={() => void perform(async () => {
        const result = await post<Row>(`/applications/${application.id}/process-form`, { version: application.version, send_email: sendEmail }); setLink(str(result.link));
      }, sendEmail ? "Link gerado e e-mail colocado na fila." : "Link gerado. Um novo link invalida o anterior.")}>Gerar link da ficha</button>
    </>}
    {link && <label className="field"><span>Link exclusivo · validade de 7 dias · selecione para copiar</span><input readOnly value={link} onFocus={e => e.target.select()} /></label>}
    {form.data?.restricted === true && <p className="muted">As respostas pessoais exigem permissão específica e liberação da identidade.</p>}
    {Boolean(form.data?.registration) && <details><summary>Consultar ficha e respostas</summary><RecordDetail value={{ registration: form.data?.registration, answers: form.data?.answers }} /></details>}
  </section>;
}
