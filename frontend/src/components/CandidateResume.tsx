import { lazy, Suspense, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api, documentBlob, download, str, type Collection } from "../lib/api";
import { date } from "../lib/labels";
import { ErrorBox, Modal } from "./ui";
import { Download, Eye, FileText } from "lucide-react";

const ResumePreview = lazy(() => import("./ResumePreview"));

export function CandidateResume({ candidateId }: { candidateId: string }) {
  const query = useQuery({ queryKey: ["rh-candidate-resume", candidateId], queryFn: () => api<Collection>("/documents?candidate_id=" + encodeURIComponent(candidateId) + "&type_name=CURRICULO&page_size=1") });
  const [preview, setPreview] = useState<Uint8Array>();
  const [error, setError] = useState<unknown>();
  const [busy, setBusy] = useState(false);
  const document = query.data?.items[0];
  async function open(view: boolean) {
    if (!document || busy) return;
    setBusy(true); setError(undefined);
    try {
      if (view) { const blob = await documentBlob("/documents/" + document.id + "/download"); setPreview(new Uint8Array(await blob.arrayBuffer())); }
      else await download("/documents/" + document.id + "/download", str(document.filename));
    } catch (err) { setError(err); } finally { setBusy(false); }
  }
  return <section className="surface padded rh-candidate-resume"><div className="rh-resume-heading"><span className="rh-resume-icon"><FileText size={28} aria-hidden="true" /></span><div><h2>Currículo do candidato</h2><p className="muted">Documento enviado para análise do processo seletivo.</p></div></div>
    <ErrorBox error={query.error ?? error} />
    {query.isPending && <p role="status">Carregando currículo…</p>}
    {query.isSuccess && !document && <p className="muted">O candidato ainda não anexou um currículo. Consulte os dados e as experiências abaixo.</p>}
    {document && <div className="rh-resume-content"><div className="rh-resume-file"><strong>{str(document.filename)}</strong><p className="muted"><span className="rh-resume-format">{document.mime === "application/pdf" ? "PDF" : "DOCX"}</span> Enviado em {date(document.created_at)}{Number(document.size) > 0 ? " · " + Math.max(1, Math.round(Number(document.size) / 1024)) + " KB" : ""}</p></div><div className="actions">
      {document.mime === "application/pdf" && <button className="button" disabled={busy} onClick={() => void open(true)}><Eye size={16} aria-hidden="true" />Visualizar currículo</button>}
      <button className="button secondary" disabled={busy} onClick={() => void open(false)}><Download size={16} aria-hidden="true" />{busy ? "Carregando…" : "Baixar currículo"}</button>
    </div></div>}
    <Modal open={Boolean(preview)} onOpenChange={value => { if (!value) setPreview(undefined); }} title="Currículo do candidato">{preview && <Suspense fallback={<p role="status">Carregando currículo…</p>}><ResumePreview data={preview} /></Suspense>}</Modal>
  </section>;
}
