import { useEffect, useId, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { Check, ChevronDown, ChevronUp, Clock3, LockKeyhole, X, Eye, Download } from "lucide-react";
import { api, post, put, documentBlob, download, str, type Row } from "../lib/api";
import { date } from "../lib/labels";
import { ErrorBox, Modal } from "./ui";
import { useSession } from "../lib/session";

type Item = { type_name: string; title: string; description: string; group: string; optional?: boolean; document: Row | null };
export type AdmissionChecklist = {
  items: Item[];
  eligible: boolean;
  can_upload: boolean;
  internal_account: boolean;
  has_profile: boolean;
  approved: boolean;
  can_approve: boolean;
};

export function AdmissionDocuments({ candidateId, showReleaseAction = true }: { candidateId?: string; showReleaseAction?: boolean }) {
  const client = useQueryClient();
  const session = useSession();
  const [expanded, setExpanded] = useState(true);
  const [showFiles, setShowFiles] = useState(false);
  const contentId = useId();
  const query = useQuery({ queryKey: ["documents", "admission-checklist", candidateId ?? "me"], queryFn: () => api<AdmissionChecklist>("/documents/admission-checklist" + (candidateId ? "?candidate_id=" + encodeURIComponent(candidateId) : "")), refetchInterval: 15000 });
  const [error, setError] = useState<unknown>();
  const [busy, setBusy] = useState("");
  const [selected, setSelected] = useState<{ item: Item; file: File } | null>(null);
  const [preview, setPreview] = useState<{ url: string; name: string } | null>(null);
  const [message, setMessage] = useState("");
  const [returnItem, setReturnItem] = useState<Item | null>(null);
  const [returnReason, setReturnReason] = useState("");
  useEffect(() => () => { if (preview) URL.revokeObjectURL(preview.url); }, [preview]);
  const items = query.data?.items ?? [];
  const sentCount = items.filter(item => item.document).length;
  const internal = query.data?.internal_account === true;
  const canReview = internal && Boolean(candidateId) && session.data?.permissions?.includes("document.review");
  const canUpload = query.data?.can_upload === true && (!internal || Boolean(candidateId));
  const reviewLabel = (item: Item) => !item.document ? item.optional ? "Opcional · Não enviado" : "Não enviado" : item.document.status === "APPROVED" ? "Aceito" : item.document.status === "REJECTED" ? "Não aceito · corrigir" : "Aguardando análise";
  const reviewClass = (item: Item) => !item.document ? item.optional ? "review-optional" : "review-missing" : item.document.status === "APPROVED" ? "review-approved" : item.document.status === "REJECTED" ? "review-rejected" : "review-pending";
  async function reviewDocument(item: Item, status: "APPROVED" | "REJECTED", comment = "") {
    if (!item.document || !canReview || busy) return;
    setBusy(item.type_name); setError(undefined); setMessage("");
    try {
      await put(`/documents/${item.document.id}/review`, { version: item.document.version, status, comment });
      setReturnItem(null); setReturnReason("");
      setMessage(status === "APPROVED" ? `${item.title}: documento aceito.` : `${item.title}: documento devolvido para correção. O candidato verá o motivo na área de Documentos.`);
      await Promise.all([client.invalidateQueries({ queryKey: ["documents"] }), client.invalidateQueries({ queryKey: ["notifications"] })]);
    } catch (err) { setError(err); } finally { setBusy(""); }
  }
  const reviewButtons = (item: Item, showPreview = true) => {
    if (!canReview) return null;
    if (item.document?.status === "APPROVED") return showPreview ? <div className="admission-review-actions">
      <button type="button" className="button secondary small" disabled={Boolean(busy)} aria-label={`Visualizar: ${item.title}`} onClick={async () => {
        setBusy(item.type_name); setError(undefined);
        try { const blob = await documentBlob(`/documents/${item.document!.id}/download`); setPreview({ url: URL.createObjectURL(blob), name: str(item.document!.filename) }); }
        catch (err) { setError(err); } finally { setBusy(""); }
      }}><Eye size={15} aria-hidden="true" />Visualizar</button>
      <button type="button" className="button secondary small" disabled={Boolean(busy)} aria-label={`Baixar: ${item.title}`} onClick={async () => {
        setBusy(item.type_name); setError(undefined);
        try { await download(`/documents/${item.document!.id}/download`, str(item.document!.filename)); }
        catch (err) { setError(err); } finally { setBusy(""); }
      }}><Download size={15} aria-hidden="true" />Baixar</button>
    </div> : null;
    return <div className="admission-review-controls">
    <div className="admission-review-actions">
    {showPreview && <button type="button" className="button secondary small" disabled={Boolean(busy) || !item.document} aria-label={`Visualizar: ${item.title}`} title={!item.document ? "Aguardando envio do arquivo" : "Visualizar documento"} onClick={async () => {
      if (!item.document) return;
      setBusy(item.type_name); setError(undefined);
      try { const blob = await documentBlob(`/documents/${item.document.id}/download`); setPreview({ url: URL.createObjectURL(blob), name: str(item.document.filename) }); }
      catch (err) { setError(err); } finally { setBusy(""); }
    }}><Eye size={15} aria-hidden="true" />Visualizar</button>}

    <button type="button" className="button small admission-accept" disabled={Boolean(busy) || !item.document || item.document.status === "APPROVED"} title={!item.document ? "Aguardando envio do arquivo" : "Aceitar documento"} onClick={() => void reviewDocument(item, "APPROVED")} aria-label={`Aceito: ${item.title}`}><Check size={15} aria-hidden="true" />Aceito</button>
    <button type="button" className="button secondary small admission-return" disabled={Boolean(busy) || !item.document || item.document.status === "REJECTED"} title={!item.document ? "Aguardando envio do arquivo" : "Devolver para correção"} onClick={() => { setReturnItem(item); setReturnReason(""); setError(undefined); }} aria-label={`Não aceito: ${item.title}`}><X size={15} aria-hidden="true" />Não aceito</button>
    </div>{!item.document && <small className="muted">Disponíveis após o envio do arquivo.</small>}
  </div>;
  };
  if (!candidateId && !canUpload) return null;
  return <section className="surface padded admission-documents">
    <div className="admission-heading">
      <div><h2>Documentos admissionais</h2><p>Relação do RH · FORM-PPO-RH-002.06</p></div>
      <button type="button" className="button secondary small" aria-expanded={expanded} aria-controls={contentId} disabled={!query.data} onClick={() => setExpanded(value => !value)}>
        {expanded ? <ChevronUp size={16} aria-hidden="true" /> : <ChevronDown size={16} aria-hidden="true" />}
        {expanded ? "Recolher lista" : "Expandir lista"}
      </button>
    </div>
    {internal && candidateId && <p>O RH pode inserir documentos e consultar os arquivos deste candidato, independentemente da etapa. O envio pelo candidato depende da liberação do RH.</p>}
    {!internal && query.data?.approved && (candidateId ? <p>Consulte os documentos enviados por este candidato. Use Visualizar para abrir o PDF ou Baixar para salvar uma cópia.</p> : <>
      <p>Envie os documentos aplicáveis ao seu caso. Cada item aceita um PDF de até 10 MB. Inclua todas as páginas e, quando necessário, os documentos de todos os dependentes no mesmo arquivo.</p>
      <p className="alert"><strong>Confira antes de enviar:</strong> o arquivo será preservado no histórico. Um novo envio fica disponível quando o RH solicitar correção.</p>
    </>)}
    <ErrorBox error={error ?? query.error} />
    {query.data && (internal ? <p className="alert success">Acesso do RH disponível. {query.data.approved ? "Envio pelo candidato liberado." : "Envio pelo candidato ainda não liberado."}</p> : query.data.approved
      ? <p className="alert success">Envio de documentos admissionais liberado pelo RH.</p>
      : <div className="alert"><p><LockKeyhole size={16} aria-hidden="true" /> <strong>Envio bloqueado.</strong> Consulte a relação abaixo. O envio será liberado quando o RH autorizar esta etapa.</p>
        {showReleaseAction && candidateId && query.data.can_approve && <button className="button" disabled={Boolean(busy)} onClick={async () => {
          setBusy("approval"); setError(undefined);
          try { await post(`/candidates/${candidateId}/approve-document-uploads`); await Promise.all(["documents", "application", "my-applications", "candidate-journey"].map(key => client.invalidateQueries({ queryKey: [key] }))); }
          catch (err) { setError(err); } finally { setBusy(""); }
        }}>{busy === "approval" ? "Liberando…" : "Aprovar e liberar envio"}</button>}
      </div>)}
    {internal && candidateId && showReleaseAction && query.data?.can_approve && !query.data.approved && <button className="button" disabled={Boolean(busy)} onClick={async () => {
      setBusy("approval"); setError(undefined);
      try { await post(`/candidates/${candidateId}/approve-document-uploads`); await Promise.all(["documents", "application", "my-applications", "candidate-journey"].map(key => client.invalidateQueries({ queryKey: [key] }))); }
      catch (err) { setError(err); } finally { setBusy(""); }
    }}>Liberar envio para o candidato</button>}
    {!candidateId && query.data?.can_upload === false && <p className="alert">{query.data.internal_account
      ? <>Você está acessando com uma conta de RH ou gestor. A lista abaixo é para consulta. Para testar o envio, saia desta conta e entre com uma conta de candidato.</>
      : query.data.has_profile ? <>Você poderá inserir os arquivos assim que o RH liberar esta etapa.</> : <>Complete seu perfil antes da liberação dos documentos. <Link to="/candidato/perfil">Preencher meu perfil</Link></>}</p>}
    {message && <p className="alert success" role="status">{message}</p>}
    {query.isPending ? <p role="status">Carregando lista de documentos…</p> : query.isError ? <button className="button secondary" onClick={() => void query.refetch()}>Recarregar lista</button> : query.data ? <>
      <p><strong>{sentCount} de {items.length} itens enviados</strong> · Alguns itens dependem da sua situação e da orientação do RH.</p>
      <div id={contentId} hidden={!expanded}>
      {internal && candidateId && <section className="admission-visual-checklist" aria-label="Checklist de documentos enviados">
        <div className="admission-checklist-summary"><span className="sent"><Check size={17} aria-hidden="true" />{items.filter(item => item.document?.status === "APPROVED").length} aceitos</span><span className="missing"><X size={17} aria-hidden="true" />{items.filter(item => item.document?.status === "REJECTED").length} para corrigir</span><span>{items.filter(item => item.document && !["APPROVED", "REJECTED"].includes(str(item.document.status))).length} em análise</span><span>{items.filter(item => !item.document && !item.optional).length} não enviados · {items.filter(item => item.optional).length} opcionais</span></div>
        {["Candidato", "Dependentes"].map(group => <div key={group} className="admission-checklist-group"><h3>{group}{group === "Dependentes" ? " · Opcionais" : ""}</h3>{group === "Dependentes" && <p className="muted">Envie apenas se desejar incluir dependentes. A ausência destes documentos não impede a conclusão do processo.</p>}<ul>{items.filter(item => item.group === group).map(item => <li key={item.type_name} className={(item.document ? "sent " : "missing ") + reviewClass(item)}>
          <div className="admission-checklist-item-heading"><span className="admission-checklist-icon" aria-hidden="true">{item.document?.status === "APPROVED" ? <Check size={19} /> : item.document && item.document.status !== "REJECTED" ? <Clock3 size={19} /> : <X size={19} />}</span><span className="admission-checklist-title">{item.title}{item.optional && <span className="admission-optional-label">Opcional</span>}</span><span className="admission-checklist-status">{reviewLabel(item)}</span></div>
          {Boolean(item.document?.comment) && <p className="admission-review-comment">Motivo informado pelo RH: {str(item.document?.comment)}</p>}
          {reviewButtons(item)}
        </li>)}</ul></div>)}
        <button type="button" className="button secondary" aria-expanded={showFiles} aria-controls={contentId + "-files"} onClick={() => setShowFiles(!showFiles)}>{showFiles ? "Recolher arquivos e ações" : "Visualizar arquivos e ações"}{showFiles ? <ChevronUp size={16} aria-hidden="true" /> : <ChevronDown size={16} aria-hidden="true" />}</button>
      </section>}
      <div id={contentId + "-files"} hidden={internal && Boolean(candidateId) && !showFiles}>
      {["Candidato", "Dependentes"].map(group => <section key={group} aria-label={group}>
        <h3>{group}{group === "Dependentes" ? " · Opcionais" : ""}</h3>{group === "Dependentes" && <p className="muted">Envie apenas se desejar incluir dependentes. A ausência destes documentos não impede a conclusão do processo.</p>}
        <ul className="admission-list">
          {items.filter(item => item.group === group).map(item => <li key={item.type_name} className={reviewClass(item)}>
            <div className="admission-description">
              <h4>{item.title}{item.optional && <span className="admission-optional-label">Opcional</span>}</h4>
              {item.description && <p className="muted">{item.description}</p>}
              {item.document ? <>
                <p>{str(item.document.filename)} · Enviado em {date(item.document.created_at)}</p>
                <span className="admission-document-review-status">{reviewLabel(item)}</span>
                {Boolean(item.document.comment) && <p>Retorno do RH: {str(item.document.comment)}</p>}
              </> : <span className="muted">{internal || query.data?.approved ? "Arquivo ainda não enviado" : "Aguardando liberação da etapa"}</span>}
            </div>
            <div className="admission-actions">
              {reviewButtons(item, false)}
              {item.document ? <>
                <span className="muted">{item.document.status === "REJECTED" ? "Correção solicitada pelo RH" : "Envio bloqueado para alterações"}</span>
                <button className="button secondary small" disabled={Boolean(busy)} onClick={async () => {
                  setBusy(item.type_name); setError(undefined);
                  try { const blob = await documentBlob(`/documents/${item.document!.id}/download`); setPreview({ url: URL.createObjectURL(blob), name: str(item.document!.filename) }); }
                  catch (err) { setError(err); } finally { setBusy(""); }
                }}>Visualizar</button>
                <button className="text-button" disabled={Boolean(busy)} onClick={async () => {
                  setBusy(item.type_name); setError(undefined);
                  try { await download(`/documents/${item.document!.id}/download`, str(item.document!.filename)); }
                  catch (err) { setError(err); } finally { setBusy(""); }
                }}>Baixar</button>
              </> : null}
              {(!item.document || item.document.status === "REJECTED") && <>
                {(!candidateId || internal && canUpload) && <>
                <input id={`admission-file-${item.type_name}`} hidden aria-label={`Enviar ${item.title}`} type="file" accept=".pdf,application/pdf" disabled={Boolean(busy) || !canUpload} onChange={e => {
                  const file = e.target.files?.[0]; e.target.value = "";
                  setError(undefined); setMessage("");
                  if (!canUpload) return;
                  if (!file) return;
                  if (!file.name.toLowerCase().endsWith(".pdf") || file.size > 10 * 1024 * 1024 || !file.size) { setError(new Error("Selecione um PDF válido de até 10 MB.")); return; }
                  setSelected({ item, file });
                }} />
                {!canUpload && <span className="muted admission-locked-label"><LockKeyhole size={14} aria-hidden="true" /> Envio bloqueado</span>}
                <button className="button small" disabled={Boolean(busy) || !canUpload} title={!canUpload ? "Disponível quando o RH liberar a etapa de documentação" : "Selecionar PDF"} onClick={() => { if (canUpload) document.getElementById(`admission-file-${item.type_name}`)?.click(); }}>{item.document ? "Enviar correção" : "Inserir arquivo"}</button>
                </>}
                {!item.document && <button className="button secondary small" disabled={!internal} title="Arquivo ainda não enviado" onClick={() => setMessage(`${item.title}: ainda não há arquivo anexado para visualizar.`)}>Visualizar</button>}
                {!item.document && candidateId && <button className="text-button" disabled={!internal} title="Arquivo ainda não enviado" onClick={() => setMessage(`${item.title}: ainda não há arquivo anexado para baixar.`)}>Baixar</button>}
              </>}
            </div>
          </li>)}
        </ul>
      </section>)}
      </div>
      </div>
    </> : null}
    <Modal open={Boolean(returnItem)} onOpenChange={open => { if (!open && !busy) setReturnItem(null); }} title="Devolver documento para correção">
      {returnItem && <form onSubmit={event => { event.preventDefault(); void reviewDocument(returnItem, "REJECTED", returnReason.trim()); }}>
        <h3>{returnItem.title}</h3><p>O documento ficará marcado em vermelho. O candidato será notificado e poderá consultar o motivo e enviar a correção na área de Documentos, conforme a liberação de envio.</p>
        <label className="field"><span>O que precisa ser corrigido?</span><textarea required minLength={5} maxLength={2000} rows={4} value={returnReason} onChange={event => setReturnReason(event.target.value)} disabled={Boolean(busy)} placeholder="Ex.: envie frente e verso do documento em um único PDF legível." /></label>
        <ErrorBox error={error} /><div className="actions"><button type="button" className="button secondary" disabled={Boolean(busy)} onClick={() => setReturnItem(null)}>Cancelar</button><button className="button" disabled={Boolean(busy) || returnReason.trim().length < 5}>{busy ? "Devolvendo…" : "Não aceitar e devolver"}</button></div>
      </form>}
    </Modal>
    <Modal open={Boolean(selected)} onOpenChange={open => { if (!open && !busy) setSelected(null); }} title="Conferir envio">
      {selected && <>
        <h3>{selected.item.title}</h3><p>{selected.file.name}</p>
        <p>Confira se este arquivo contém todas as páginas. O arquivo será preservado no histórico; outro envio depende de correção solicitada pelo RH.</p>
        <ErrorBox error={error} />
        <div className="actions">
          <button className="button secondary" disabled={Boolean(busy)} onClick={() => setSelected(null)}>Cancelar</button>
          <button className="button" disabled={Boolean(busy) || !canUpload} onClick={async () => {
            if (!canUpload) return;
            setBusy(selected.item.type_name); setError(undefined);
            const data = new FormData(); data.set("type_name", selected.item.type_name); data.set("file", selected.file);
            if (internal && candidateId) data.set("candidate_id", candidateId);
            try {
              await api("/documents", { method: "POST", body: data });
              setMessage(`${selected.item.title}: documento enviado para análise. O arquivo foi preservado no histórico.`);
              setSelected(null);
              await Promise.all(["documents", "application", "my-applications", "candidate-journey"].map(key => client.invalidateQueries({ queryKey: [key] })));
            } catch (err) { setError(err); await Promise.all(["documents", "application", "my-applications", "candidate-journey"].map(key => client.invalidateQueries({ queryKey: [key] }))); }
            finally { setBusy(""); }
          }}>{busy ? "Enviando…" : "Confirmar envio definitivo"}</button>
        </div>
      </>}
    </Modal>
    <Modal open={Boolean(preview)} onOpenChange={open => { if (!open) setPreview(null); }} title={preview?.name ?? "Visualizar documento"}>
      {preview && <><p>Se a visualização não estiver disponível no seu navegador, use a opção Baixar.</p><iframe className="document-preview" title={preview.name} src={preview.url} /><a className="button secondary" href={preview.url} download={preview.name}>Baixar arquivo</a></>}
    </Modal>
  </section>;
}
