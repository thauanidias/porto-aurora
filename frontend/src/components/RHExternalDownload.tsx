import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Download } from "lucide-react";
import { api, download } from "../lib/api";
import { useSession } from "../lib/session";
import { ErrorBox } from "./ui";

export function RHExternalDownload({ candidateId }: { candidateId: string }) {
  const session = useSession();
  const allowed = session.data?.user.kind === "INTERNAL" && session.data.permissions.some(permission => ["candidate.sensitive.view", "candidate.registration.view"].includes(permission));
  const query = useQuery({ queryKey: ["external-registration-download", candidateId], queryFn: () => api<{ available: boolean }>(`/candidates/${candidateId}/selection-registration-download`), enabled: Boolean(allowed), refetchInterval: 15000 });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>();
  if (!allowed) return null;
  return <div><button className="button secondary" disabled={busy || !query.data?.available} title={query.data?.available ? "Modelo original em Excel com assinatura e comprovante" : "Disponível após o candidato concluir e assinar a ficha"} onClick={async () => {
    setBusy(true); setError(undefined); try { await download(`/candidates/${candidateId}/selection-registration.xlsx`, `FORM-PPO-RH-002.02-${candidateId}.xlsx`); } catch (err) { setError(err); } finally { setBusy(false); }
  }}><Download size={16} aria-hidden="true" />{busy ? "Baixando…" : "Baixar ficha original (Excel)"}</button><ErrorBox error={error ?? query.error} /></div>;
}
