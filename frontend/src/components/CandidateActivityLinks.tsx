import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ExternalLink, Link2, CheckCircle2, CircleCheck, LoaderCircle } from "lucide-react";
import { api, post, put, str, type Collection, type Row } from "../lib/api";
import { date } from "../lib/labels";
import { useSession } from "../lib/session";
import { useCandidateJourney } from "../lib/candidateJourney";
import { useActivityLinks, type ActivityKind } from "../lib/activityLinks";
import { StageGate } from "./CandidateJourney";
import { Empty, ErrorBox } from "./ui";

export function CandidateActivityLinks({ kind }: { kind: ActivityKind }) {
  const query = useActivityLinks(kind);
  const client = useQueryClient();
  const [busy, setBusy] = useState("");
  const [error, setError] = useState<unknown>();
  const journey = useCandidateJourney();
  return <>
    <ErrorBox error={error ?? query.error} />
    {query.data?.items.map(row => <StageGate key={row.id} section={kind === "INTERVIEW" ? "interviews" : "tests"}
      title={str(row.title)} allowed={row.stage_unlocked === true && !query.error}>
      <article className="surface padded activity-link-card">
        <p className="privacy-eyebrow">{kind === "INTERVIEW" ? "ENTREVISTA" : "TESTE"} · {str(row.vacancy_title)}</p>
        <h2>{str(row.title)}</h2>
        <p className="preserve">{str(row.description)}</p>
        {row.stage_unlocked === true && row.url && !query.error && journey.isSuccess && !journey.error && journey.data.sections[kind === "INTERVIEW" ? "interviews" : "tests"].enabled
          ? <a className="button" href={str(row.url)} target="_blank" rel="noopener noreferrer"><ExternalLink size={17} />{kind === "INTERVIEW" ? "Acessar entrevista" : "Acessar teste"}</a>
          : <button className="button" disabled>{kind === "INTERVIEW" ? "Acessar entrevista" : "Acessar teste"}</button>}
        {kind === "TEST" && (row.completed_at ? <div className="test-completion-done" role="status"><CheckCircle2 size={25} aria-hidden="true" /><div><strong>Teste concluído!</strong><p>Conclusão informada em {date(row.completed_at)}. Conclusão registrada para esta fase.</p></div></div> : row.stage_unlocked === true && <button className="test-completion-button" disabled={Boolean(busy)} onClick={async () => {
          setBusy(str(row.id)); setError(undefined);
          try { await post(`/candidate-activity-links/${row.id}/complete`, {}); await Promise.all(["candidate-activity-links", "stage-task-status", "candidate-actions"].map(key => client.invalidateQueries({ queryKey: [key] }))); }
          catch (failure) { setError(failure); } finally { setBusy(""); }
        }}>{busy === row.id ? <LoaderCircle className="test-completion-spinner" size={24} aria-hidden="true" /> : <CircleCheck size={24} aria-hidden="true" />}<span><strong>{busy === row.id ? "Registrando conclusão…" : "Concluí esta fase"}</strong><small>{busy === row.id ? "Aguarde um instante" : "Confirmar conclusão do teste por link"}</small></span></button>)}
      </article>
    </StageGate>)}
  </>;
}

export function RHActivityLinks({ candidateId, applicationId }: { candidateId: string; applicationId?: string }) {
  const session = useSession();
  const editable = session.data?.permissions.includes("candidate.move") === true;
  const query = useActivityLinks(undefined, candidateId, applicationId);
  const applications = useQuery({ queryKey: ["activity-link-applications", candidateId],
    queryFn: () => api<Collection>("/applications?candidate_id=" + encodeURIComponent(candidateId) + "&page_size=100"), enabled: editable });
  const [editing, setEditing] = useState<Row | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>();
  const [message, setMessage] = useState("");
  const client = useQueryClient();
  const available = applications.data?.items.filter(row => !applicationId || row.id === applicationId) ?? [];
  async function refresh() { await client.invalidateQueries({ queryKey: ["candidate-activity-links"] }); }
  return <section className="surface padded rh-activity-links">
    <h2><Link2 size={20} aria-hidden="true" /> Links de entrevistas e testes</h2>
    <p>Disponibilize links e orientações para este candidato. Entrevistas são liberadas na etapa de entrevistas; testes, na etapa de testes. Você pode preparar os links antecipadamente.</p>
    <ErrorBox error={error ?? query.error ?? applications.error} />
    {message && <p className="alert success" role="status">{message}</p>}
    {editable && <>
      {applications.isPending ? <p role="status">Carregando candidaturas…</p> : available.length > 0 ? <form key={editing ? editing.id + ":" + editing.version : "new"} className="activity-link-form" onSubmit={async event => {
        event.preventDefault();
        if (busy) return;
        const form = event.currentTarget;
        const data = new FormData(form);
        const content = { title: data.get("title"), description: data.get("description"), url: data.get("url") };
        setBusy(true); setError(undefined); setMessage("");
        try {
          if (editing) await put("/candidate-activity-links/" + editing.id, { ...content, active: editing.active, version: editing.version });
          else await post("/candidate-activity-links", { ...content, application_id: data.get("application_id"), kind: data.get("kind") });
          setEditing(null); form.reset();
          setMessage("Link salvo. O candidato receberá um aviso e poderá acessar quando a etapa estiver liberada.");
          await refresh();
        } catch (err) { setError(err); } finally { setBusy(false); }
      }}>
        <fieldset disabled={busy} className="stage-gate-fields">
          <div className="form-grid">
            <label className="field"><span>Candidatura / vaga</span><select name="application_id" required disabled={Boolean(editing)} defaultValue={str(editing?.application_id ?? applicationId ?? available[0]?.id)}>{available.map(row => <option key={row.id} value={row.id}>{str(row.vacancy_title)} · {str(row.stage_name)}</option>)}</select></label>
            <label className="field"><span>Tipo de atividade</span><select name="kind" disabled={Boolean(editing)} defaultValue={str(editing?.kind ?? "INTERVIEW")}><option value="INTERVIEW">Entrevista</option><option value="TEST">Teste</option></select></label>
          </div>
          <label className="field"><span>Título da atividade</span><input name="title" required minLength={3} maxLength={180} defaultValue={str(editing?.title)} placeholder="Ex.: Entrevista com o RH" /></label>
          <label className="field"><span>Link de acesso</span><input name="url" type="url" required maxLength={2048} defaultValue={str(editing?.url)} placeholder="https://…" /></label>
          <label className="field"><span>Descrição e orientações</span><textarea name="description" required minLength={3} maxLength={5000} rows={4} defaultValue={str(editing?.description)} placeholder="Informe objetivo, data, horário, prazo e instruções para participar." /></label>
          <div className="actions"><button className="button" disabled={busy}>{busy ? "Salvando…" : editing ? "Salvar alterações" : "Disponibilizar link"}</button>{editing && <button className="button secondary" type="button" onClick={() => setEditing(null)}>Cancelar edição</button>}</div>
        </fieldset>
      </form> : <p className="alert">Para disponibilizar um link, o candidato precisa ter uma candidatura em uma vaga à qual você tenha acesso.</p>}
    </>}
    <h3>Links cadastrados</h3>
    {query.isPending ? <p role="status">Carregando links…</p> : !query.error && !query.data?.items.length ? <Empty title="Nenhum link cadastrado">Os links de entrevista e teste aparecerão aqui.</Empty> : query.data?.items.map(row => <article key={row.id} className="activity-link-record">
      <div className="section-heading"><h3>{str(row.title)}</h3><span className="muted">{row.kind === "INTERVIEW" ? "Entrevista" : "Teste"} · {row.active ? row.stage_unlocked ? "Liberado" : "Aguardando etapa" : "Desativado"}</span></div>
      {Boolean(row.completed_at) && <p className="alert success"><CheckCircle2 size={17} /> Candidato informou a conclusão do teste em {date(row.completed_at)}. Fase concluída; avaliação realizada na plataforma do teste.</p>}
      <p className="muted">{str(row.vacancy_title)}</p><p className="preserve">{str(row.description)}</p>
      <a className="activity-link-url" href={str(row.url)} target="_blank" rel="noopener noreferrer">{str(row.url)} <ExternalLink size={14} /></a>
      {editable && Boolean(row.can_manage) && <div className="actions">
        <button type="button" className="button secondary small" disabled={busy} onClick={() => { setEditing(row); setMessage(""); }}>Editar link</button>
        <button type="button" className="button secondary small" disabled={busy} onClick={async () => {
          setBusy(true); setError(undefined); setMessage("");
          try { await put("/candidate-activity-links/" + row.id, { title: row.title, description: row.description, url: row.url, active: !row.active, version: row.version }); setEditing(null); setMessage(row.active ? "Link desativado para o candidato." : "Link reativado. O acesso respeita a etapa da candidatura."); await refresh(); }
          catch (err) { setError(err); } finally { setBusy(false); }
        }}>{row.active ? "Desativar link" : "Reativar link"}</button>
      </div>}
    </article>)}
  </section>;
}
