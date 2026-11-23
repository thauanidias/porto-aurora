import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { MessageSquareHeart, Star, ArrowRight, CheckCircle2 } from "lucide-react";
import { api, post, str, type Collection } from "../lib/api";
import { date } from "../lib/labels";
import { Modal, ErrorBox, Empty } from "./ui";

export function CandidateFeedbackButton() {
  const [open, setOpen] = useState(false);
  const [sent, setSent] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>();
  const applications = useQuery({ queryKey: ["feedback-applications"], queryFn: () => api<Collection>("/applications?page_size=100"), enabled: open });
  return <><div className="candidate-feedback-send">
    {sent && <div className="candidate-feedback-confirmation" role="status"><CheckCircle2 size={24} aria-hidden="true" /><div><strong>Feedback enviado!</strong><p>Obrigado! Seu feedback foi enviado ao RH.</p></div></div>}
    <button className={"button" + (sent ? " secondary" : "")} onClick={() => { setOpen(true); setError(undefined); }}><MessageSquareHeart size={18} />{sent ? "Enviar outro feedback" : "Enviar feedback"}</button>
  </div>
    <Modal open={open} onOpenChange={value => { if (!busy) setOpen(value); }} title="Como foi sua experiência?"><p>Conte o que funcionou bem e o que podemos melhorar. Sua opinião será recebida pela equipe de RH.</p><ErrorBox error={error ?? applications.error} />
      {applications.isPending ? <p role="status">Carregando suas candidaturas…</p> : applications.data?.items.length ? <form onSubmit={async event => {
        event.preventDefault(); if (busy) return;
        const form = new FormData(event.currentTarget);
        setBusy(true); setError(undefined);
        try { await post("/candidate-feedback", { application_id: form.get("application_id"), message: String(form.get("message")).trim(), rating: form.get("rating") ? Number(form.get("rating")) : null }); setSent(true); setOpen(false); }
        catch (failure) { setError(failure); } finally { setBusy(false); }
      }}><fieldset disabled={busy} className="stage-gate-fields"><label className="field"><span>Sobre qual candidatura?</span><select name="application_id" required>{applications.data.items.map(row => <option key={row.id} value={row.id}>{str(row.vacancy_title)}</option>)}</select></label><label className="field"><span>Como você avalia sua experiência? (opcional)</span><select name="rating" defaultValue=""><option value="">Prefiro não dar uma nota</option><option value="1">1 · Muito ruim</option><option value="2">2 · Ruim</option><option value="3">3 · Regular</option><option value="4">4 · Boa</option><option value="5">5 · Excelente</option></select></label><label className="field"><span>Seu feedback</span><textarea name="message" required minLength={5} maxLength={5000} rows={5} placeholder="Compartilhe sua experiência com o processo seletivo…" /></label><div className="actions"><button type="button" className="button secondary" onClick={() => setOpen(false)}>Cancelar</button><button className="button" disabled={busy}>{busy ? "Enviando…" : "Enviar feedback ao RH"}</button></div></fieldset></form> : applications.isSuccess && <p>Você poderá enviar seu feedback após se candidatar a uma vaga.</p>}
    </Modal></>;
}

export function CandidateFeedbackInbox() {
  const [page, setPage] = useState(1);
  const query = useQuery({ queryKey: ["candidate-feedback", page], queryFn: () => api<Collection>(`/candidate-feedback?page_number=${page}`), refetchInterval: 15000 });
  return <section className="surface padded feedback-inbox"><header className="rediscovery-heading"><span className="rediscovery-heading-icon"><MessageSquareHeart size={24} aria-hidden="true" /></span><div><h2>O que os candidatos estão dizendo</h2><p>Relatos sobre a experiência em nossos processos seletivos.</p></div>{query.isSuccess && <span className="rediscovery-total">{query.data.total} {query.data.total === 1 ? "feedback recebido" : "feedbacks recebidos"}</span>}</header><ErrorBox error={query.error} />{query.isPending && <p role="status">Carregando feedbacks…</p>}{query.isSuccess && !query.data.total && <Empty title="Nenhum feedback recebido">Os relatos enviados pelos candidatos aparecerão aqui.</Empty>}
    <div className="candidate-feedback-list">{query.data?.items.map(row => <article className="candidate-feedback-card" key={row.id}>
      <header className="feedback-person-heading"><span className="feedback-person-avatar" aria-hidden="true">{str(row.candidate_name).trim().split(/\s+/).filter(Boolean).map(part => part[0]).slice(0,2).join("")}</span><div><strong>{str(row.candidate_name)}</strong><p>{str(row.vacancy_title)}</p></div><time>{date(row.created_at)}</time></header>
      {row.rating != null && <div className="feedback-rating" aria-label={`Experiência: ${row.rating} de 5`}><span aria-hidden="true">{[1,2,3,4,5].map(star => <Star key={star} size={17} fill={Number(row.rating) >= star ? "currentColor" : "none"} />)}</span><strong>{str(row.rating)}/5</strong><small>Experiência no processo</small></div>}
      <blockquote className="feedback-comment">{row.restricted ? "Relato protegido durante a seleção sem identificação." : str(row.message)}</blockquote>
      <footer><Link className="button secondary small" to={`/app/candidaturas/${row.application_id}`}>Ver candidatura<ArrowRight size={15} /></Link></footer>
    </article>)}</div>
    {query.data && query.data.total > 25 && <div className="pagination"><button className="button secondary" disabled={page === 1} onClick={() => setPage(value => value - 1)}>Anterior</button><span>Página {page}</span><button className="button secondary" disabled={page * 25 >= query.data.total} onClick={() => setPage(value => value + 1)}>Próxima</button></div>}
  </section>;
}
