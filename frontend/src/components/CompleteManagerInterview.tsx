import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2 } from "lucide-react";
import { api, post, str, type Row, type Collection } from "../lib/api";
import { date } from "../lib/labels";
import { useSession } from "../lib/session";
import { ErrorBox, Modal } from "./ui";

export function CompleteManagerInterview({ applicationId }: { applicationId: string }) {
  const session = useSession();
  const client = useQueryClient();
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>();
  const [saved, setSaved] = useState(false);
  const query = useQuery({ queryKey: ["complete-manager-interview", applicationId], queryFn: () => api<Collection>(`/interviews?application_id=${applicationId}`), enabled: open });
  if (!session.data?.permissions.includes("interview.manage") || !session.data?.permissions.includes("candidate.move")) return null;
  const scheduled = query.data?.items.filter(item => ["SCHEDULED", "COMPLETED"].includes(str(item.status))) ?? [];
  return <><div className="interview-validation-control"><button type="button" className="button secondary" onClick={() => { setOpen(true); setError(undefined); setSaved(false); void query.refetch(); }}><CheckCircle2 size={17} />Validar entrevista com gestor</button>
    {saved && <div className="interview-validation-success" role="status"><CheckCircle2 size={19} aria-hidden="true" /><div><strong>Entrevista validada e aprovada</strong><p>Use “Liberar próxima etapa” para continuar. Outros agendamentos pendentes precisam ser concluídos.</p></div></div>}</div>
    <Modal open={open} onOpenChange={value => { if (!busy) setOpen(value); }} title="Validar entrevista com gestor"><p>Confirme que a entrevista foi realizada e que o resultado é favorável ao avanço do candidato. A validação registra a aprovação do RH para esta etapa.</p><ErrorBox error={error ?? query.error} />
      {query.isFetching ? <p role="status">Consultando entrevistas…</p> : scheduled.map(interview => <section className="surface padded" key={interview.id}><strong>{str(interview.title)}</strong><p>{date(interview.starts_at)}</p><button className="button" disabled={busy} onClick={async () => {
        setBusy(true); setError(undefined);
        try {
          if (interview.status !== "COMPLETED") await post(`/interviews/${interview.id}/status`, { version: interview.version, status: "COMPLETED", reason: "Entrevista com gestor realizada e conclusão confirmada pelo RH." });
          const application = await api<Row>(`/applications/${applicationId}`);
          await post(`/applications/${applicationId}/stage-reviews`, { version: application.version, status: "APPROVED", reason: "Entrevista com gestor validada pelo RH com parecer favorável ao avanço do candidato." });
          await Promise.all(["stage-task-status", "process-interviews", "complete-manager-interview", "manager-interview-agenda", "application", "vacancy", "vacancy-applications", "resume-screening", "candidate-processes", "rh-applications"].map(key => client.invalidateQueries({ queryKey: [key] })));
          setOpen(false); setSaved(true);
        } catch (failure) { setError(failure); } finally { setBusy(false); }
      }}>{busy ? "Registrando…" : "Validar e aprovar entrevista"}</button></section>)}
      {!query.isFetching && query.isSuccess && !scheduled.length && <p>Nenhuma entrevista disponível para validar. Agende a entrevista primeiro.</p>}
    </Modal></>;
}
