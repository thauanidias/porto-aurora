import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Download, FileText } from "lucide-react";
import { api, download, obj, str, type Row } from "../lib/api";
import { date } from "../lib/labels";
import { useSession } from "../lib/session";
import { ErrorBox } from "./ui";
import { RHExternalDocuments } from "./RHExternalDocuments";

export function RHInternalDownloads({ candidateId }: { candidateId: string }) {
  const session = useSession();
  const allowed = session.data?.user.kind === "INTERNAL" && session.data.permissions.some(permission => ["candidate.sensitive.view", "candidate.registration.view"].includes(permission));
  const query = useQuery({ queryKey: ["rh-internal-downloads", candidateId], queryFn: () => api<Row>(`/candidates/${candidateId}/internal-profile-downloads`), enabled: Boolean(allowed), refetchInterval: 15000 });
  const [busy, setBusy] = useState("");
  const [error, setError] = useState<unknown>();
  if (!allowed || (query.isSuccess && !query.data.is_internal)) return null;
  const resume = obj(query.data?.resume);
  const canDownload = Boolean(resume.id) && ["CLEAN", "NOT_CONFIGURED"].includes(str(resume.scan_status));
  async function save(kind: string) {
    setBusy(kind); setError(undefined);
    const extension = kind === "excel" ? "xlsx" : "pdf";
    try { await download(kind !== "resume" ? `/candidates/${candidateId}/internal-registration.${extension}` : `/documents/${str(resume.id)}/download`, kind !== "resume" ? `FORM-PPO-RH-002.01-${candidateId}.${extension}` : str(resume.filename)); }
    catch (err) { setError(err); } finally { setBusy(""); }
  }
  return <section className="surface padded"><h2>Ficha interna e currículo</h2><p>Baixe a ficha preenchida pelo colaborador, com a assinatura salva, e o currículo anexado.</p><ErrorBox error={error ?? query.error} />
    {query.isPending ? <p role="status">Carregando arquivos do colaborador…</p> : query.isError ? <button className="button secondary" onClick={() => void query.refetch()}>Tentar novamente</button> : <>
      <div className="registration-document-row"><div><h3><FileText size={17} /> Ficha de seleção interna · FORM-PPO-RH-002.01</h3><p className="muted">{query.data.available ? `Versão ${str(query.data.version)} · Salva em ${date(query.data.saved_at)} · ${query.data.confirmed_at ? "Declarações confirmadas" : "Rascunho"}` : "O colaborador ainda não salvou a ficha interna."}</p></div><div className="actions"><button className="button small" disabled={!query.data.available || Boolean(busy)} onClick={() => void save("excel")}><Download size={16} />{busy === "excel" ? "Baixando…" : "Baixar modelo original (Excel)"}</button><button className="button secondary small" disabled={!query.data.available || Boolean(busy)} onClick={() => void save("form")}><Download size={16} />{busy === "form" ? "Baixando…" : "Baixar ficha interna (PDF)"}</button></div></div>
      <div className="registration-document-row"><div><h3>Currículo</h3><p className="muted">{resume.id ? str(resume.filename) : "O colaborador ainda não anexou um currículo."}</p>{Boolean(resume.id) && !canDownload && <p className="muted">O arquivo está aguardando validação para download.</p>}</div><button className="button secondary small" disabled={!canDownload || Boolean(busy)} onClick={() => void save("resume")}><Download size={16} />{busy === "resume" ? "Baixando…" : "Baixar currículo"}</button></div>
      <RHExternalDocuments candidateId={candidateId} />
    </>}
  </section>;
}

