import { useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { Eye, ArrowRight, CheckCircle2, XCircle } from "lucide-react";
import { api, obj, rows, str, type Row, type Collection } from "../lib/api";
import { date, label } from "../lib/labels";
import { Modal, ErrorBox } from "./ui";
import { CandidateResume } from "./CandidateResume";
import { CandidateSummary } from "./CandidateSummary";
import { CandidateDocumentFiles } from "./CandidateDocumentFiles";
import { RHInternalDownloads } from "./RHInternalDownloads";
import { RHSelectionDocuments } from "./RHSelectionDocuments";
import { CompleteExternalTestPhase } from "./CompleteExternalTestPhase";
import { CompleteManagerInterview } from "./CompleteManagerInterview";
import { RHQuestionAnswers } from "./RHQuestionAnswers";
import { VacancyQuestions } from "./VacancyQuestions";

export function CandidateStageActivity({ application }: { application: Row }) {
  const [open, setOpen] = useState(false);
  const status = useQuery({ queryKey: ["stage-task-status", application.id], queryFn: () => api<Row>(`/applications/${application.id}/stage-task-status`), refetchInterval: 5000 });
  return <>
    <button type="button" className={`button secondary stage-view-activity ${status.data?.status === "COMPLETED" ? "task-completed" : status.data?.status === "PENDING" ? "task-pending" : ""}`} onClick={() => setOpen(true)}><Eye size={17} aria-hidden="true" />Ver o que o candidato fez{status.data && Number(status.data.completed) + Number(status.data.pending) > 0 && <small>{str(status.data.completed)}/{Number(status.data.completed) + Number(status.data.pending)} concluídas</small>}</button>
    {obj(application.candidate_access).phase === "INTERVIEW" && <CompleteManagerInterview applicationId={str(application.id)} />}
    {obj(application.candidate_access).phase === "TEST" && <CompleteExternalTestPhase applicationId={str(application.id)} />}
    <Modal open={open} onOpenChange={setOpen} title="Atividades do candidato nesta etapa">
      {open && <StageActivityContent application={application} status={status.data} />}
    </Modal>
  </>;
}

function StageActivityContent({ application, status }: { application: Row; status?: Row }) {
  const [viewRegistration, setViewRegistration] = useState(false);
  const questionsRef = useRef<HTMLElement>(null);
  const phase = str(obj(application.candidate_access).phase);
  const detail = useQuery({ queryKey: ["application", application.id], queryFn: () => api<Row>(`/applications/${application.id}`), refetchInterval: 15000 });
  const form = useQuery({ queryKey: ["process-form", application.id], queryFn: () => api<Row>(`/applications/${application.id}/process-form`), enabled: phase === "FORM", refetchInterval: 15000 });
  const interviews = useQuery({ queryKey: ["process-interviews", application.id], queryFn: () => api<Collection>(`/interviews?application_id=${application.id}`), enabled: phase === "INTERVIEW", refetchInterval: 15000 });
  const row = detail.data;
  const targetTab = phase === "FORM" ? "selection" : ["INTERVIEW", "TEST"].includes(phase) ? "activities" : phase === "ADMISSION" ? "checklist" : "profile";
  return <div className="stage-activity-content">
    <header><strong>{str(obj(application.candidate).name)}</strong><p>{str(application.stage_name)}</p></header>
    <ErrorBox error={detail.error ?? form.error ?? interviews.error} />
    {status && <section className="stage-task-list" aria-label="Situação das tarefas"><p>Verde: tarefa concluída. Vermelho: tarefa pendente. O avanço continua dependendo da conferência do RH.</p>{rows(status.tasks).map(task => <article key={task.key as string} className={`stage-task ${task.status === "COMPLETED" ? "task-completed" : task.status === "PENDING" ? "task-pending" : "task-not-applicable"}`}>
      <div>{task.status === "COMPLETED" ? <CheckCircle2 size={21} aria-hidden="true" /> : task.status === "PENDING" ? <XCircle size={21} aria-hidden="true" /> : null}<div><strong>{str(task.title)}</strong><span>{task.status === "COMPLETED" ? "Concluída pelo candidato" : task.status === "PENDING" ? "Pendente" : "Não se aplica"}</span><p>{str(task.detail)}</p></div></div>
      {task.status === "COMPLETED" && task.key === "registration" ? <button className="button secondary small" onClick={() => setViewRegistration(value => !value)}>Visualizar ficha assinada<ArrowRight size={15} /></button> : task.status === "COMPLETED" && task.key === "questions" ? <button className="button secondary small" onClick={() => questionsRef.current?.scrollIntoView({ behavior: "smooth", block: "start" })}>Visualizar respostas<ArrowRight size={15} /></button> : <Link className="button secondary small" to={`/app/candidaturas/${application.id}?aba=${str(task.tab)}`}>{task.status === "COMPLETED" ? "Visualizar entrega" : "Abrir esta atividade"}<ArrowRight size={15} /></Link>}
    </article>)}</section>}
    {detail.isPending && <p role="status">Consultando atividades…</p>}
    {row && <>
      {["REGISTER", "RECRUITMENT", "SELECTION"].includes(phase) && <>
        {row.recruitment_type === "INTERNAL" && !obj(row.candidate).blind && Boolean(row.candidate_id) && <RHInternalDownloads candidateId={str(row.candidate_id)} />}
        {!obj(row.candidate).blind && Boolean(row.candidate_id) && <CandidateResume candidateId={str(row.candidate_id)} />}
        <CandidateSummary candidate={obj(row.candidate) as Row} />
      </>}
      {phase === "FORM" && viewRegistration && Boolean(row.candidate_id) && (row.recruitment_type === "INTERNAL" ? <RHInternalDownloads candidateId={str(row.candidate_id)} /> : <RHSelectionDocuments candidate={obj(row.candidate) as Row} view="registration" />)}
      {phase === "FORM" && <section className="stage-activity-section rh-question-section" ref={questionsRef}>
        <div className="rh-question-heading"><div><p className="privacy-eyebrow">RESPOSTAS DO CANDIDATO</p><h3>Perguntas do RH</h3><p>Confira as respostas enviadas para esta oportunidade.</p></div><VacancyQuestions vacancyId={str(application.vacancy_id)} /></div>
        {form.isPending ? <p role="status">Consultando respostas…</p> : form.data && <>
          <div className={"rh-question-summary " + (form.data.status === "COMPLETED" ? "is-complete" : "")}><strong>{({ NOT_SENT: "Aguardando disponibilização", SENT: "Aguardando respostas", PENDING: "Em preenchimento", COMPLETED: "Respostas enviadas" } as Record<string, string>)[str(form.data.status)] ?? label(str(form.data.status))}</strong>{Boolean(form.data.submitted_at) && <span>Enviadas em {date(form.data.submitted_at)}</span>}</div>
          {form.data.restricted === true ? <p className="alert">Seu acesso permite consultar a situação. As respostas pessoais exigem permissão específica.</p> : <RHQuestionAnswers questions={rows(form.data.questions)} answers={Object.keys(obj(form.data.answers)).length ? obj(form.data.answers) : obj(row.answers)} />}
          {form.data.status !== "COMPLETED" && !Object.keys(obj(form.data.answers)).length && !form.data.restricted && <p className="muted">As respostas aparecerão aqui quando o candidato enviar. Depois, a ficha externa será liberada automaticamente.</p>}
        </>}
      </section>}
      {phase === "INTERVIEW" && <section className="stage-activity-section"><h3>Entrevistas desta candidatura</h3>
        {interviews.isPending ? <p role="status">Consultando entrevistas…</p> : interviews.data && !interviews.data.items.length && <p>Nenhuma entrevista registrada.</p>}
        {interviews.data?.items.map(item => <article key={item.id}><strong>{str(item.title)}</strong><p>{date(item.starts_at)} · {label(str(item.status))}</p>{Boolean(item.location) && <p>{str(item.location)}</p>}</article>)}
        <p className="muted">A situação da entrevista é registrada pelo RH.</p>
      </section>}
      {!["REGISTER", "RECRUITMENT", "SELECTION", "FORM", "INTERVIEW", "TEST"].includes(phase) && <p>Consulte os documentos, as entregas e os registros desta candidatura pelo botão abaixo.</p>}
      {phase === "ADMISSION" && !obj(row.candidate).blind && Boolean(row.candidate_id) && <CandidateDocumentFiles candidateId={str(row.candidate_id)} />}
      <Link className="button secondary" to={`/app/candidaturas/${application.id}?aba=${targetTab}`}>Abrir dados e arquivos completos<ArrowRight size={16} aria-hidden="true" /></Link>
      <details className="stage-activity-history"><summary>Histórico de passagem pelas etapas</summary>{rows(row.history).map(item => <article key={item.id}><strong>{str(item.stage_name)}</strong><p>Entrada: {date(item.entered_at)}{item.left_at ? ` · Saída: ${date(item.left_at)}` : " · Etapa em andamento"}</p>{Boolean(item.reason) && <p>{str(item.reason)}</p>}</article>)}</details>
    </>}
  </div>;
}
