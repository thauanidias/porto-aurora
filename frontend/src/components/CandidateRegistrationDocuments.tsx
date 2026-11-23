import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { FileCheck2, FileText, LockKeyhole } from "lucide-react";
import { useCandidateJourney } from "../lib/candidateJourney";
import { api, download, obj, str, type Collection, type Row } from "../lib/api";
import { date } from "../lib/labels";
import type { Schema } from "./SchemaForm";
import { ErrorBox, Modal } from "./ui";

type Registration = {
  data: Record<string, unknown> | null;
  saved_at: string | null;
  confirmed_at: string | null;
};

function resolveSchema(schema: Schema, root: Schema): Schema {
  if (schema.$ref) return resolveSchema(root.$defs?.[schema.$ref.split("/").at(-1) ?? ""] ?? {}, root);
  if (schema.anyOf) return resolveSchema(schema.anyOf.find(item => item.type !== "null") ?? {}, root);
  return schema;
}

function displayValue(value: unknown, schema: Schema, key: string): string {
  if (value == null || value === "") return "Não informado";
  if (typeof value === "boolean") return value ? "Sim" : "Não";
  if (schema.format === "date") return str(value).split("-").reverse().join("/");
  if (key === "last_salary" && typeof value === "number") return value.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
  return str(value);
}

export function RegistrationSnapshot({ data, schema, root }: { data: Record<string, unknown>; schema: Schema; root: Schema }) {
  const properties = resolveSchema(schema, root).properties ?? {};
  return <div className="registration-snapshot">
    {Object.entries(properties).map(([key, raw]) => {
      const resolved = resolveSchema(raw, root);
      const title = raw.title ?? resolved.title ?? key;
      const value = data[key];
      if (resolved.format === "signature") return <div className="registration-snapshot-field" key={key}><strong>{title}</strong>{typeof value === "string" && value.startsWith("data:image/png;base64,") ? <img className="registration-signature-image" src={value} alt="Assinatura eletrônica do candidato" /> : <p className="muted">Assinatura não registrada.</p>}</div>;
      if (resolved.type === "object") return <section className="registration-snapshot-section" key={key}>
        <h3>{title}</h3>
        {raw.description && <p className="muted registration-declaration">{raw.description}</p>}
        <RegistrationSnapshot data={obj(value)} schema={resolved} root={root} />
      </section>;
      if (resolved.type === "array") {
        const items = Array.isArray(value) ? value : [];
        return <section className="registration-snapshot-section" key={key}>
          <h3>{title}</h3>
          {items.length ? items.map((item, index) => <div className="registration-dependent" key={index}>
            <h4>Dependente {index + 1}</h4>
            <RegistrationSnapshot data={obj(item)} schema={resolved.items ?? {}} root={root} />
          </div>) : <p className="muted">Nenhum dependente informado.</p>}
        </section>;
      }
      return <dl className="registration-snapshot-field" key={key}>
        <dt>{title}</dt><dd>{displayValue(value, resolved, key)}</dd>
      </dl>;
    })}
  </div>;
}

export function CandidateRegistrationDocuments() {
  const journey = useCandidateJourney();
  const registrationLocked = !journey.data?.sections.selection_registration.enabled;
  const [view, setView] = useState<"consent" | "registration" | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>();
  const consent = useQuery({
    queryKey: ["consent-receipts", "registration-document"],
    queryFn: async () => {
      let page = 1;
      let result: Collection;
      do {
        result = await api<Collection>("/privacy/my-consent-receipts?page_number=" + page);
        const receipt = result.items.find(item => item.context === "CADASTRO");
        if (receipt) return receipt;
        page++;
      } while (result.items.length > 0 && (page - 1) * result.page_size < result.total);
      return null;
    },
    refetchOnMount: "always",
  });
  const registration = useQuery({
    queryKey: ["selection-registration"],
    queryFn: () => api<Registration>("/candidates/me/selection-registration"),
    refetchOnMount: "always",
  });
  const receipt = useQuery({
    queryKey: ["consent-receipt-document", consent.data?.id],
    queryFn: () => api<Row>("/privacy/consent-receipts/" + consent.data?.id),
    enabled: view === "consent" && Boolean(consent.data),
  });
  const schema = useQuery({
    queryKey: ["selection-registration-schema"],
    queryFn: () => api<Schema>("/candidates/me/selection-registration/schema"),
    enabled: view === "registration",
  });
  return <section className="surface padded candidate-registration-documents">
    <h2>Termo de consentimento e ficha de inscrição</h2>
    <p className="muted">Consulte o termo aceito e os dados salvos na sua ficha de inscrição.</p>
    <ErrorBox error={error} />
    <article className="registration-document-row">
      <div className="registration-document-info">
        <FileCheck2 size={24} aria-hidden="true" />
        <div><h3>Termo de consentimento de dados</h3>
          {consent.isPending ? <p role="status">Carregando termo…</p> : consent.data ? <p>FORM-PPO-RH-002.09 · Aceito em {date(consent.data.created_at)}</p> : !consent.isError && <p>Você ainda não registrou o aceite do termo.</p>}
          {consent.data && <small>Protocolo: {str(consent.data.protocol)}</small>}
          <ErrorBox error={consent.error} />
        </div>
      </div>
      <div className="registration-document-actions">
        {consent.data ? <>
          <button className="button secondary small" onClick={() => setView("consent")}>Visualizar termo</button>
          <button className="text-button" disabled={busy} onClick={async () => {
            if (!consent.data) return;
            setBusy(true); setError(undefined);
            try { await download(`/privacy/consent-receipts/${consent.data.id}/document`, `${str(consent.data.document_code)}-${str(consent.data.protocol)}.docx`); }
            catch (err) { setError(err); } finally { setBusy(false); }
          }}>{busy ? "Baixando…" : "Baixar termo aceito"}</button>
        </> : consent.isError ? <button className="text-button" onClick={() => void consent.refetch()}>Tentar novamente</button> : !consent.isPending && <Link className="button secondary small" to="/candidato/perfil">Ler e aceitar em Meu perfil</Link>}
      </div>
    </article>
    {registrationLocked ? <article className="registration-document-row"><div className="registration-document-info"><LockKeyhole size={24} aria-hidden="true" /><div><h3>Ficha de inscrição preenchida</h3><p>Disponível após aprovação na triagem curricular.</p></div></div><span className="muted"><LockKeyhole size={14} aria-hidden="true" /> Bloqueado</span></article> : <article className="registration-document-row">
      <div className="registration-document-info">
        <FileText size={24} aria-hidden="true" />
        <div><h3>Ficha de inscrição preenchida</h3>
          {registration.isPending ? <p role="status">Carregando ficha…</p> : registration.data?.data ? <p>FORM-PPO-RH-002.02 · Salva em {date(registration.data.saved_at)}</p> : !registration.isError && <p>Você ainda não salvou sua ficha de inscrição.</p>}
          {registration.data?.data && <small>{registration.data.confirmed_at ? "Declarações confirmadas." : "Declarações finais ainda não confirmadas."}</small>}
          <ErrorBox error={registration.error} />
        </div>
      </div>
      <div className="registration-document-actions">
        {registration.data?.data && <button className="button secondary small" onClick={() => setView("registration")}>Visualizar ficha preenchida</button>}
        {registration.isError ? <button className="text-button" onClick={() => void registration.refetch()}>Tentar novamente</button> : !registration.isPending && <Link className="text-button" to="/candidato/perfil">{registration.data?.data ? "Atualizar em Meu perfil" : "Preencher em Meu perfil"}</Link>}
      </div>
    </article>
    }
    <Modal open={view !== null} onOpenChange={open => { if (!open) setView(null); }} title={view === "consent" ? "Termo de consentimento aceito" : "Ficha de inscrição preenchida"}>
      {view === "consent" && <>
        <ErrorBox error={receipt.error} />
        {receipt.isPending && <p role="status">Carregando documento…</p>}
        {receipt.isError && <button className="text-button" onClick={() => void receipt.refetch()}>Tentar novamente</button>}
        {receipt.data && <div className="registration-consent-snapshot">
          <p><strong>{str(receipt.data.name)}</strong> · {str(receipt.data.email)}</p>
          <p>Protocolo: {str(receipt.data.protocol)} · Aceito em {date(receipt.data.created_at)}</p>
          {Array.isArray(obj(receipt.data.document_snapshot).paragraphs) && (obj(receipt.data.document_snapshot).paragraphs as unknown[]).map((paragraph, index) => <p key={index}>{str(paragraph)}</p>)}
        </div>}
      </>}
      {view === "registration" && <>
        <ErrorBox error={schema.error} />
        {schema.isPending && <p role="status">Carregando ficha…</p>}
        {schema.isError && <button className="text-button" onClick={() => void schema.refetch()}>Tentar novamente</button>}
        {schema.data && registration.data?.data && <RegistrationSnapshot data={registration.data.data} schema={schema.data} root={schema.data} />}
      </>}
    </Modal>
  </section>;
}
