import { useImperativeHandle, useState, type Ref } from "react";
import { Link } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowRight, CheckCircle2, LockKeyholeOpen } from "lucide-react";
import { api, obj, post, str, type Row } from "../lib/api";
import { useSession } from "../lib/session";
import { ErrorBox, Modal } from "./ui";
import { InterviewAttachmentButton } from "./InterviewAttachmentButton";
import { ReleaseAdmissionDocuments } from "./ReleaseAdmissionDocuments";

const activityNames: Record<string, string> = { resume: "Currículo e perfil", selection_registration: "Ficha de inscrição", process_form: "Ficha por link", interviews: "Entrevistas", tests: "Testes", questions: "Perguntas da vaga", messages: "Conversa com o RH", admission: "Documentos (com liberação de envio)" };
const impacts: Record<string, string> = { REGISTER: "Preenchimento do cadastro.", RECRUITMENT: "Envio do currículo e preenchimento do perfil profissional.", SELECTION: "Análise do currículo pelo RH.", FORM: "Preenchimento da ficha e das perguntas deste processo.", INTERVIEW: "Acesso às entrevistas que o RH disponibilizar.", TEST: "Acesso às perguntas e aos testes que o RH atribuir.", ADMISSION: "Preparação da decisão e da documentação. O envio de documentos é liberado separadamente." };

export function StageReleaseActions({ application, stages, advanceRef }: { application: Row; stages: Row[]; advanceRef?: Ref<{ open: () => void }> }) {
  const session = useSession();
  const client = useQueryClient();
  const [expanded, setExpanded] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>();
  const [message, setMessage] = useState("");
  const [link, setLink] = useState("");
  const access = obj(application.candidate_access);
  const permissions = obj(access.permissions);
  const person = application.recruitment_type === "INTERNAL" ? "colaborador" : "candidato";
  const active = ["ACTIVE", "RESERVE"].includes(str(application.status));
  const index = stages.findIndex(stage => stage.id === application.stage_id);
  const next = index >= 0 && stages[index]?.kind !== "FINALIST" ? stages.slice(index + 1).find(stage => !["OFFER", "HIRED"].includes(str(stage.kind))) : undefined;
  const screening = access.phase === "SELECTION";
  const canMove = Boolean(session.data?.permissions.includes("candidate.move"));
  useImperativeHandle(advanceRef, () => ({ open: () => {
    if (active && canMove && next) { setConfirming(true); setReason(""); setError(undefined); }
  } }), [active, canMove, next]);
  const form = useQuery({ queryKey: ["process-form", application.id], queryFn: () => api<Row>(`/applications/${application.id}/process-form`), enabled: expanded && permissions.process_form === true && Boolean(session.data?.permissions.includes("candidate.view")), refetchInterval: 15000 });
  const refresh = async () => Promise.all(["application", "vacancy-applications", "resume-screening", "candidate-processes", "candidate-journey", "rh-applications", "dashboard", "process-form"].map(key => client.invalidateQueries({ queryKey: [key] })));
  return <div className="stage-release-actions">
    {active && canMove && next && <><button type="button" className="button small stage-release-next" onClick={() => { setConfirming(true); setReason(""); setError(undefined); }}><LockKeyholeOpen size={16} aria-hidden="true" />{screening ? "Aprovar currículo e avançar" : "Liberar próxima etapa"}<ArrowRight size={15} aria-hidden="true" /></button><small className="muted">Próxima etapa: <strong>{str(next.name)}</strong></small></>}
    {active && !next && <p className="stage-final-label"><CheckCircle2 size={16} aria-hidden="true" />{stages[index]?.kind === "FINALIST" ? "Candidato finalista" : "Última etapa do processo"}</p>}
    {active && !next && <Link className="button secondary small" to={`/app/candidaturas/${application.id}`}>Registrar decisão do processo</Link>}
    <button type="button" className="text-button stage-release-expand" aria-expanded={expanded} onClick={() => setExpanded(!expanded)}>{expanded ? "Recolher atividades" : "Ver atividades e liberações"}</button>
    {expanded && <div className="stage-release-activities"><strong>Painel do {person}</strong>
      <ul>{Object.entries(activityNames).filter(([key]) => permissions[key] === true).map(([key, title]) => <li key={key}><CheckCircle2 size={14} aria-hidden="true" />{title}</li>)}</ul>
      {active && permissions.process_form === true && <div className="stage-release-form">
        <p>Ficha: {form.isPending ? "consultando…" : ({ COMPLETED: "preenchida", SENT: "link disponibilizado", PENDING: "preenchimento pendente", NOT_SENT: "ainda não enviada" } as Record<string, string>)[str(form.data?.status)] ?? "consultar situação"}</p>
        <ErrorBox error={form.error} />
        {canMove && form.isSuccess && form.data.status !== "COMPLETED" && <button type="button" className="button secondary small" disabled={busy} onClick={async () => {
          setBusy(true); setError(undefined);
          try { const result = await post<Row>(`/applications/${application.id}/process-form`, { version: application.version, send_email: false }); setLink(str(result.link)); setMessage("Link da ficha gerado. Compartilhe com a pessoa candidata."); await refresh(); }
          catch (err) { setError(err); } finally { setBusy(false); }
        }}>{busy ? "Gerando…" : "Gerar link da ficha"}</button>}
        {link && <label className="field"><span>Link da ficha · válido por 7 dias</span><input readOnly value={link} onFocus={event => event.target.select()} /></label>}
        {canMove && form.data?.status !== "COMPLETED" && <small className="muted">Gerar outro link invalida o anterior.</small>}
      </div>}
      {permissions.interviews === true && <InterviewAttachmentButton application={application} />}
      {(permissions.interviews === true || permissions.tests === true) && <Link className="button secondary small" to={`/app/candidaturas/${application.id}?aba=activities`}>Agendar entrevista ou atribuir teste</Link>}
      {permissions.interviews === true && session.data?.permissions.includes("candidate.evaluate") && <Link className="text-button" to={`/app/candidaturas/${application.id}?aba=evaluations`}>Preencher avaliação</Link>}
      {access.phase === "ADMISSION" && !obj(application.candidate).blind && Boolean(application.candidate_id) && <ReleaseAdmissionDocuments candidateId={str(application.candidate_id)} />}
      {access.phase === "ADMISSION" && <Link className="text-button" to={`/app/candidaturas/${application.id}?aba=checklist`}>Conferir documentos admissionais</Link>}
      <Link className="text-button" to={`/app/candidaturas/${application.id}?aba=history`}>Consultar histórico e pendências</Link>
    </div>}
    {message && <p className="stage-release-message" role="status">{message}</p>}
    {!confirming && <ErrorBox error={error} />}
    <Modal open={confirming} onOpenChange={open => { if (!busy) setConfirming(open); }} title={"Liberar próxima etapa: " + str(next?.name)}>
      <form onSubmit={async event => {
        event.preventDefault(); if (!next || busy || !canMove || !active) return;
        setBusy(true); setError(undefined);
        try {
          const updated = await post<Row>(`/applications/${application.id}/${screening ? "approve-screening" : "move"}`, screening ? { version: application.version, reason: reason.trim() } : { version: application.version, stage_id: next.id, reason: reason.trim() });
          client.setQueryData(["application", application.id], updated); setConfirming(false);
          setMessage("Etapa liberada: " + str(next.name) + ". As atividades ficam disponíveis no painel do " + person + ".");
          await refresh();
        } catch (err) { setError(err); } finally { setBusy(false); }
      }}>
        <p><strong>{str(obj(application.candidate).name)}</strong></p><p>{str(application.stage_name)} → <strong>{str(next?.name)}</strong></p>
        <p>{impacts[str(next?.candidate_phase)] ?? "As permissões serão atualizadas conforme as regras desta etapa."} Atividades obrigatórias pendentes impedem o avanço.</p>
        <label className="field"><span>{screening ? "Justificativa da aprovação do currículo" : "Observação do RH (opcional)"}</span><textarea required={screening} minLength={screening ? 5 : undefined} maxLength={2000} rows={3} value={reason} onChange={event => setReason(event.target.value)} disabled={busy} /></label>
        <ErrorBox error={error} /><div className="actions"><button type="button" className="button secondary" disabled={busy} onClick={() => setConfirming(false)}>Cancelar</button><button className="button" disabled={busy || screening && reason.trim().length < 5}>{busy ? "Liberando…" : "Confirmar liberação"}</button></div>
      </form>
    </Modal>
  </div>;
}
