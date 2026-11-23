import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api, post, type Row, str } from "../lib/api";
import { ErrorBox } from "./ui";

export function RejectionEmail({ applicationId }: { applicationId: string }) {
  const [subject, setSubject] = useState<string>();
  const [body, setBody] = useState<string>();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>();
  const query = useQuery({ queryKey: ["rejection-email", applicationId], queryFn: () => api<Row>(`/applications/${applicationId}/rejection-email`), refetchInterval: 15000 });
  const status = str(query.data?.status);
  const requested = Boolean(status && status !== "NOT_REQUESTED");
  const statuses: Record<string, string> = { SENT: "E-mail enviado", PENDING: "E-mail na fila de envio", RETRY: "Nova tentativa de envio agendada", DEAD: "Falha no envio. Consulte Entregas de mensagens.", DISABLED: "Envio desabilitado. Consulte Entregas de mensagens." };
  return <section className="surface padded">
    <h2>Retorno ao candidato não selecionado</h2>
    <p>Revise a mensagem e solicite o envio automático por e-mail. O retorno é registrado uma única vez por candidatura.</p>
    <ErrorBox error={error ?? query.error} />
    {query.isPending ? <p role="status">Carregando mensagem…</p> : query.data && <>
      {requested && <p role="status" className="alert">{statuses[status] ?? status}</p>}
      {query.data.test_mode === true && <p className="alert">Ambiente de teste: as mensagens são encaminhadas para a caixa de testes.</p>}
      {!query.data.delivery_enabled && !requested && <p className="alert">O envio de e-mails precisa estar habilitado nas configurações para enviar este retorno.</p>}
      <label className="field"><span>Assunto do e-mail</span><input maxLength={180} disabled={busy || requested} value={subject ?? str(query.data.subject)} onChange={e => setSubject(e.target.value)} /></label>
      <label className="field"><span>Mensagem ao candidato</span><textarea rows={9} maxLength={10000} disabled={busy || requested} value={body ?? str(query.data.body)} onChange={e => setBody(e.target.value)} /></label>
      {!requested && <button className="button" disabled={busy || !query.data.delivery_enabled || !(subject ?? str(query.data.subject)).trim() || (body ?? str(query.data.body)).trim().length < 10} onClick={async () => {
        if (busy) return;
        setBusy(true); setError(undefined);
        try {
          await post(`/applications/${applicationId}/rejection-email`, { subject: (subject ?? str(query.data?.subject)).trim(), body: (body ?? str(query.data?.body)).trim() });
          await query.refetch();
        } catch (err) { setError(err); } finally { setBusy(false); }
      }}>{busy ? "Registrando envio…" : "Enviar retorno por e-mail"}</button>}
    </>}
  </section>;
}
