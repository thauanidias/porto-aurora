import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Download, Eye, FileText } from "lucide-react";
import { api, documentBlob, download, str, type Collection } from "../lib/api";
import { date, label } from "../lib/labels";
import { Badge, Empty, ErrorBox, Modal } from "./ui";

export function CandidateDocumentFiles({ candidateId }: { candidateId: string }) {
  const [page, setPage] = useState(1);
  const query = useQuery({ queryKey: ["candidate-document-files", candidateId, page], queryFn: () => api<Collection>("/documents?" + new URLSearchParams({ candidate_id: candidateId, include_photo: "true", page_number: String(page), page_size: "100" })), refetchInterval: 15000 });
  const [busy, setBusy] = useState("");
  const [error, setError] = useState<unknown>();
  const [preview, setPreview] = useState<{ url: string; name: string; mime: string }>();
  useEffect(() => () => { if (preview) URL.revokeObjectURL(preview.url); }, [preview]);
  return <section className="surface padded candidate-document-files">
    <div className="section-heading"><div><h2>Todos os arquivos enviados</h2><p className="muted">Currículo, certificados, respostas de testes, foto e documentos admissionais.</p></div>{query.data && <span className="muted">{query.data.total} {query.data.total === 1 ? "arquivo" : "arquivos"}</span>}</div>
    <ErrorBox error={error ?? query.error} />
    {query.isPending ? <p role="status">Carregando arquivos…</p> : query.isError ? <button className="button secondary" onClick={() => void query.refetch()}>Tentar novamente</button> : !query.data?.items.length ? <Empty title="Nenhum arquivo enviado">Os documentos aparecerão aqui assim que forem anexados ao perfil.</Empty> : <ul className="candidate-document-file-list">{query.data.items.map(file => {
      const available = ["CLEAN", "NOT_CONFIGURED"].includes(str(file.scan_status));
      const canPreview = file.mime === "application/pdf" || str(file.mime).startsWith("image/");
      return <li key={file.id}><FileText size={24} aria-hidden="true" /><div className="candidate-document-file-info"><h3>{str(file.type_label) || ({ CURRICULO: "Currículo", FOTO_PERFIL: "Foto de perfil", TEST_RESPONSE: "Resposta de teste" } as Record<string, string>)[str(file.type_name)] || label(str(file.type_name))}</h3><p>{str(file.filename)}</p><small>Enviado em {date(file.created_at)} · Versão {str(file.revision)} · {Math.max(1, Math.round(Number(file.size) / 1024))} KB</small><div><Badge value={file.status} />{!available && <span className="muted">Download indisponível: arquivo aguardando validação.</span>}</div></div><div className="candidate-document-file-actions">
        {canPreview && <button className="button secondary small" disabled={Boolean(busy) || !available} aria-label={"Visualizar " + str(file.filename)} onClick={async () => { setBusy(file.id); setError(undefined); try { const blob = await documentBlob(`/documents/${file.id}/download`); setPreview({ url: URL.createObjectURL(blob), name: str(file.filename), mime: str(file.mime) }); } catch (err) { setError(err); } finally { setBusy(""); } }}><Eye size={15} aria-hidden="true" />Visualizar</button>}
        <button className="button small" disabled={Boolean(busy) || !available} aria-label={"Baixar " + str(file.filename)} onClick={async () => { setBusy(file.id); setError(undefined); try { await download(`/documents/${file.id}/download`, str(file.filename)); } catch (err) { setError(err); } finally { setBusy(""); } }}><Download size={15} aria-hidden="true" />{busy === file.id ? "Carregando…" : "Baixar"}</button>
      </div></li>;
    })}</ul>}
    {(query.data?.total ?? 0) > 100 && <div className="pagination"><button className="button secondary small" disabled={page === 1} onClick={() => setPage(page - 1)}>Anterior</button><span>Página {page}</span><button className="button secondary small" disabled={page * 100 >= (query.data?.total ?? 0)} onClick={() => setPage(page + 1)}>Próxima</button></div>}
    <Modal open={Boolean(preview)} onOpenChange={open => { if (!open) setPreview(undefined); }} title={preview?.name ?? "Visualizar documento"}>{preview && (preview.mime.startsWith("image/") ? <img className="candidate-document-image" src={preview.url} alt={preview.name} /> : <iframe className="document-preview" src={preview.url} title={preview.name} />)}</Modal>
  </section>;
}
