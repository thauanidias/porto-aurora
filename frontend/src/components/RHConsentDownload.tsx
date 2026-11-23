import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Download } from "lucide-react";
import { api, download } from "../lib/api";
import { useSession } from "../lib/session";
import { ErrorBox } from "./ui";

export function RHConsentDownload({ candidateId }: { candidateId: string }) {
  const session = useSession();
  const allowed = session.data?.user.kind === "INTERNAL" && session.data.permissions.includes("candidate.view");
  const query = useQuery({ queryKey: ["consent-download", candidateId], queryFn: () => api<{ available: boolean; receipt_id: string | null; protocol: string | null }>(`/candidates/${candidateId}/consent-download`), enabled: Boolean(allowed), refetchInterval: 15000 });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>();
  if (!allowed) return null;
  return <div><button className="button secondary" disabled={busy || !query.data?.available} title={query.data?.available ? "Termo original em Word com assinatura e comprovante" : "Disponível após o candidato aceitar o termo de consentimento"} onClick={async () => {
    if (!query.data?.receipt_id) return;
    setBusy(true); setError(undefined);
    try { await download(`/privacy/consent-receipts/${query.data.receipt_id}/document`, `termo-consentimento-${query.data.protocol}.docx`); }
    catch (err) { setError(err); } finally { setBusy(false); }
  }}><Download size={16} aria-hidden="true" />{busy ? "Baixando…" : "Baixar termo de consentimento"}</button><ErrorBox error={error ?? query.error} /></div>;
}
