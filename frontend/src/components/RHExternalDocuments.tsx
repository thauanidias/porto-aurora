import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { Download, Link2 } from "lucide-react";
import { api, download, post, rows, str, type Collection, type Row } from "../lib/api";
import { useSession } from "../lib/session";
import { ErrorBox, Modal } from "./ui";

export function RHExternalDocuments({ candidateId }: { candidateId: string }) {
  const session = useSession();
  const client = useQueryClient();
  const canEdit = Boolean(session.data?.permissions.includes("document.review"));
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState("");
  const [sourceId, setSourceId] = useState("");
  const [reason, setReason] = useState("");
  const [confirmed, setConfirmed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>();
  const [notice, setNotice] = useState("");
  const endpoint = `/candidates/${candidateId}/external-document-sources`;
  const query = useQuery({ queryKey: ["external-document-sources", candidateId], queryFn: () => api<Row>(endpoint) });
  const options = useQuery({ queryKey: ["external-source-options", search], queryFn: () => api<Collection>("/candidates?" + new URLSearchParams({ q: search.trim(), page_size: "25" })), enabled: open && search.trim().length >= 2 });
  return <div className="rh-external-documents">
    <div className="section-heading"><div><h3>Documentos do cadastro externo</h3><p className="muted">Vincule os arquivos já enviados pela mesma pessoa na seleção externa.</p></div>{canEdit && <button className="button secondary small" onClick={() => { setOpen(true); setError(undefined); setSourceId(""); setSearch(""); setReason(""); setConfirmed(false); }}><Link2 size={16} />Associar cadastro externo</button>}</div>
    {!open && <ErrorBox error={error ?? query.error} />}{notice && <p className="alert success" role="status">{notice}</p>}
    {query.isPending && <p role="status">Consultando associações…</p>}
    {query.isSuccess && !rows(query.data.items).length && <p className="muted">Nenhum cadastro externo associado a este colaborador.</p>}
    {rows(query.data?.items).map(source => <section className="external-source-card" key={source.id}><div className="section-heading"><div><h4>{str(source.source_name)}</h4><p className="muted">Origem: {str(source.source_email)}</p><Link to={"/app/candidatos/" + str(source.source_id)} target="_blank" rel="noreferrer">Conferir cadastro de origem</Link></div>{canEdit && <button className="text-button" disabled={busy} onClick={async () => { setBusy(true); setError(undefined); try { await api(endpoint + "/" + source.id, { method: "DELETE" }); await client.invalidateQueries({ queryKey: ["external-document-sources", candidateId] }); setNotice("Associação removida. Os arquivos originais foram preservados."); } catch (err) { setError(err); } finally { setBusy(false); } }}>Desassociar</button>}</div>
      {rows(source.documents).map(document => <div className="registration-document-row" key={document.id}><div><strong>{str(document.type_label) || str(document.type_name)}</strong><p className="muted">{str(document.filename)}</p></div><button className="button secondary small" disabled={busy || !["CLEAN", "NOT_CONFIGURED"].includes(str(document.scan_status))} onClick={async () => { setBusy(true); setError(undefined); try { await download(`/documents/${document.id}/download`, str(document.filename)); } catch (err) { setError(err); } finally { setBusy(false); } }}><Download size={15} />Baixar</button></div>)}
      {!rows(source.documents).length && <p className="muted">Os arquivos desta associação não estão disponíveis.</p>}
    </section>)}
    <Modal open={open} onOpenChange={setOpen} title="Associar documentos do cadastro externo"><form onSubmit={async event => {
      event.preventDefault(); setBusy(true); setError(undefined); setNotice("");
      try { const result = await post<{ document_count: number }>(endpoint, { source_candidate_id: sourceId, identity_confirmed: confirmed, reason }); await client.invalidateQueries({ queryKey: ["external-document-sources", candidateId] }); setOpen(false); setNotice(`${result.document_count} arquivo(s) associado(s). Os documentos permanecem no cadastro externo de origem.`); }
      catch (err) { setError(err); } finally { setBusy(false); }
    }}><p>Localize o cadastro externo e confira se pertence ao colaborador. As contas e as candidaturas anteriores serão preservadas.</p><ErrorBox error={error ?? options.error} />
      <label className="field"><span>Buscar cadastro pelo nome</span><input type="search" value={search} onChange={event => { setSearch(event.target.value); setSourceId(""); setConfirmed(false); }} placeholder="Digite pelo menos dois caracteres" /></label>
      {options.isFetching && <p role="status">Buscando cadastros…</p>}
      {options.isSuccess && <label className="field"><span>Cadastro externo de origem</span><select required value={sourceId} onChange={event => { setSourceId(event.target.value); setConfirmed(false); }}><option value="">Selecione o cadastro</option>{options.data.items.filter(person => person.id !== candidateId && !person.blind).map(person => <option key={person.id} value={person.id}>{str(person.name)} · {str(person.email)}</option>)}</select></label>}
      {sourceId && <p><Link to={"/app/candidatos/" + sourceId} target="_blank" rel="noreferrer">Abrir perfil de origem para conferir os documentos</Link></p>}
      <label className="field"><span>Como a identidade foi conferida?</span><textarea required minLength={10} maxLength={1000} rows={3} value={reason} onChange={event => setReason(event.target.value)} placeholder="Registre a conferência realizada pelo RH" /></label>
      <label className="check-field"><input type="checkbox" required checked={confirmed} onChange={event => setConfirmed(event.target.checked)} /><span>Conferi a identidade e confirmo que os dois cadastros pertencem à mesma pessoa.</span></label>
      <p className="muted">Serão associados os arquivos disponíveis neste momento, sem fotos de perfil e respostas de testes. Novos envios no cadastro externo exigem atualizar a associação.</p>
      <button className="button" disabled={busy || !sourceId || !confirmed || reason.trim().length < 10}>{busy ? "Associando…" : "Confirmar associação"}</button>
    </form></Modal>
  </div>;
}
