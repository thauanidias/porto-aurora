import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { LockKeyholeOpen } from "lucide-react";
import { api, post } from "../lib/api";
import { useSession } from "../lib/session";
import { ErrorBox } from "./ui";
import type { AdmissionChecklist } from "./AdmissionDocuments";

export function ReleaseAdmissionDocuments({ candidateId }: { candidateId: string }) {
  const session = useSession();
  const client = useQueryClient();
  const canReview = session.data?.user.kind === "INTERNAL" && session.data.permissions.includes("document.review");
  const checklist = useQuery({
    queryKey: ["documents", "admission-checklist", candidateId],
    queryFn: () => api<AdmissionChecklist>("/documents/admission-checklist?candidate_id=" + encodeURIComponent(candidateId)),
    enabled: Boolean(canReview),
    refetchInterval: 15000,
  });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>();
  const [released, setReleased] = useState(false);
  if (!canReview || checklist.data?.approved === true) return null;
  const canRelease = checklist.data?.can_approve === true && !checklist.data.approved && !checklist.isError;
  return <div className="admission-release">
    <button
      className="button"
      disabled={busy || !canRelease}
      onClick={async () => {
        if (busy || !canRelease) return;
        setBusy(true); setError(undefined); setReleased(false);
        try {
          await post(`/candidates/${encodeURIComponent(candidateId)}/approve-document-uploads`);
          setReleased(true);
          await Promise.all([
            client.invalidateQueries({ queryKey: ["documents"] }),
            client.invalidateQueries({ queryKey: ["candidate", candidateId] }),
          ]);
        } catch (err) { setError(err); }
        finally { setBusy(false); }
      }}
    >
      <LockKeyholeOpen size={17} aria-hidden="true" />
      {busy ? "Liberando documentos…" : checklist.data?.approved ? "Documentos admissionais liberados" : "Liberar documentos admissionais"}
    </button>
    {canRelease && <small className="muted">O RH pode liberar o envio de documentos para este candidato.</small>}
    {released && <small role="status">Envio liberado. O candidato foi notificado.</small>}
    <ErrorBox error={error ?? checklist.error} />
    {checklist.isError && <button className="text-button" onClick={() => void checklist.refetch()}>Verificar liberação novamente</button>}
  </div>;
}
