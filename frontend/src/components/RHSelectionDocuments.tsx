import { useQuery } from "@tanstack/react-query";
import { api, download, rows, str, obj, type Row } from "../lib/api";
import { RegistrationSnapshot } from "./CandidateRegistrationDocuments";
import type { Schema } from "./SchemaForm";
import { date } from "../lib/labels";
import { ErrorBox } from "./ui";
import { useState } from "react";

export function RHSelectionDocuments({ candidate, view = "both" }: { candidate: Row; view?: "registration" | "consent" | "both" }) {
  const query = useQuery({ queryKey: ["rh-selection-documents", candidate.id], queryFn: () => api<Row>("/candidates/" + candidate.id + "/selection-documents"), refetchInterval: 5000, refetchOnWindowFocus: "always" });
  const [error, setError] = useState<unknown>();
  const [busy, setBusy] = useState("");
  const receipts = rows(query.data?.receipts);
  const registration = obj(query.data?.registration);
  const signed = Boolean(registration.confirmed_at && obj(registration.signature_record).protocol && obj(obj(registration.data).declaration).signature_image);
  return <><ErrorBox error={query.error ?? error} />{view !== "consent" && <section className="surface padded selection-registration rh-external-registration">
    <div className="registration-heading"><div><p className="privacy-eyebrow">FORM-PPO-RH-002.02 · CONFIDENCIAL</p><h2>Ficha de inscrição para seleção externa</h2></div><button className="button" disabled={!signed || Boolean(busy)} onClick={async () => {
      setBusy("external"); setError(undefined); try { await download(`/candidates/${candidate.id}/selection-registration.xlsx`, `FORM-PPO-RH-002.02-${candidate.id}.xlsx`); } catch (err) { setError(err); } finally { setBusy(""); }
    }}>{busy === "external" ? "Baixando…" : "Baixar ficha original (Excel)"}</button></div>
    {registration.restricted ? <p className="alert">A ficha completa exige permissão de acesso aos dados confidenciais do candidato.</p> : registration.data ? <>
      <p className={signed ? "alert success" : "alert"}>{signed ? "Ficha concluída e assinada pelo candidato." : "Rascunho: o candidato ainda precisa concluir e assinar a ficha."} {registration.saved_at ? `Última atualização: ${date(registration.saved_at)}.` : ""}</p>
      {signed && <p className="muted">Protocolo: {str(obj(registration.signature_record).protocol)}. O Excel inclui o modelo original, todos os dados informados e o comprovante da assinatura.</p>}
      {query.data?.schema && <RegistrationSnapshot data={obj(registration.data)} schema={query.data.schema as Schema} root={query.data.schema as Schema} />}
    </> : <p className="muted">O candidato ainda não preencheu a ficha. O download será liberado após a conclusão e assinatura.</p>}
  </section>}{view !== "registration" && <section className="surface padded"><h2>Termo de consentimento de dados</h2><p>Consulte e baixe o termo de consentimento aceito pelo candidato.</p>
    {query.isPending && <p role="status">Carregando termo de consentimento…</p>}
    {query.data && <>
      {!receipts.length && <div className="registration-document-row"><p className="muted">O candidato ainda não registrou o aceite do termo. O download ficará disponível após o aceite.</p><button className="button secondary small" disabled>Baixar termo de consentimento</button></div>}
      {receipts.map(receipt => <article className="registration-document-row" key={receipt.id}><div><strong>{str(receipt.document_code)} · {str(receipt.protocol)}</strong><p>Aceito em {date(receipt.created_at)}</p></div><button className="button secondary small" disabled={Boolean(busy)} onClick={async () => {
        setBusy(receipt.id); setError(undefined); try { await download("/privacy/consent-receipts/" + receipt.id + "/document", "termo-" + str(receipt.protocol) + ".docx"); } catch (err) { setError(err); } finally { setBusy(""); }
      }}>{busy === receipt.id ? "Baixando…" : "Baixar termo de consentimento"}</button></article>)}
    </>}
  </section>}</>;
}
