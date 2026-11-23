import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api, post, str, type Row, type Collection } from "../lib/api";
import { useSession } from "../lib/session";
import { date, label } from "../lib/labels";
import { ErrorBox } from "./ui";
import { OperationModal, type Operation } from "../pages/Resources";

export function ProcessInterviews({ application }: { application: Row }) {
  const session = useSession();
  const canManage = Boolean(session.data?.permissions.includes("interview.manage"));
  const [operation, setOperation] = useState<Operation | null>(null);
  const query = useQuery({ queryKey: ["process-interviews", application.id], queryFn: () => api<Collection>(`/interviews?application_id=${application.id}`), refetchInterval: 15000 });
  return <section className="surface padded process-workflow"><h2>Agendamentos e realização de entrevistas</h2><ErrorBox error={query.error} />
    {canManage && <button className="button secondary" onClick={() => setOperation({ title: "Agendar entrevista", form: "interview", initial: { vacancy_id: application.vacancy_id, application_ids: [application.id] }, run: data => post("/interviews", data) })}>Agendar entrevista</button>}
    {query.isPending ? <p role="status">Carregando entrevistas…</p> : !query.data?.items.length && <p className="muted">Nenhuma entrevista agendada para esta candidatura.</p>}
    {query.data?.items.map(interview => <article key={interview.id} className="process-interview-row"><div><strong>{str(interview.title)}</strong><p>{date(interview.starts_at)} · {str(interview.location)}</p><span>{label(str(interview.status))}</span></div>
      {canManage && interview.status === "SCHEDULED" && <button className="button secondary small" onClick={() => setOperation({ title: "Registrar realização da entrevista", schema: { type: "object", properties: { status: { type: "string", enum: ["COMPLETED", "CANCELED", "NO_SHOW"], title: "Situação" }, reason: { type: "string", minLength: 5, title: "Observações e justificativa" } }, required: ["status", "reason"] }, run: data => post(`/interviews/${interview.id}/status`, { ...data, version: interview.version }) })}>Registrar situação</button>}
    </article>)}
    <OperationModal operation={operation} onClose={() => setOperation(null)} />
  </section>;
}
