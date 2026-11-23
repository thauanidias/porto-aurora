import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, LoaderCircle } from "lucide-react";
import { post } from "../lib/api";
import { useSession } from "../lib/session";
import { ErrorBox } from "./ui";

export function CompleteExternalTestPhase({ applicationId }: { applicationId: string }) {
  const session = useSession();
  const client = useQueryClient();
  const [busy, setBusy] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<unknown>();
  if (!session.data?.permissions.includes("candidate.move")) return null;
  return <div className="interview-validation-control"><button className={"phase-completion-button" + (saved ? " is-complete" : "")} disabled={busy || saved} onClick={async () => {
    setBusy(true); setError(undefined);
    try {
      await post(`/applications/${applicationId}/complete-external-tests`, {});
      await Promise.all(["stage-task-status", "candidate-activity-links", "application", "vacancy-applications", "rh-applications", "candidate-processes"].map(key => client.invalidateQueries({ queryKey: [key] })));
      setSaved(true);
    } catch (failure) { setError(failure); } finally { setBusy(false); }
  }}>{busy ? <LoaderCircle className="test-completion-spinner" size={21} aria-hidden="true" /> : <CheckCircle2 size={21} aria-hidden="true" />}<span>{busy ? "Registrando…" : saved ? "Fase concluída" : "Confirmar fase concluída"}</span></button>
    {saved && <div className="interview-validation-success" role="status">Conclusão registrada. Use “Liberar próxima etapa” para continuar.</div>}<ErrorBox error={error} /></div>;
}
