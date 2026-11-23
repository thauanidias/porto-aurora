import { useRef, useState } from "react";
import { Paperclip } from "lucide-react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api, put, str } from "../lib/api";
import schema from "../lib/internalRegistrationSchema.json";
import { SchemaForm, type Schema } from "./SchemaForm";
import { ErrorBox } from "./ui";

type Registration = { data: Record<string, unknown> | null; version: number; confirmed_at: string | null };
export function InternalRegistrationForm({ initial, onSubmit, preview = false }: {
  initial: Record<string, unknown>; onSubmit: (data: Record<string, unknown>) => Promise<void>; preview?: boolean;
}) {
  const [saved, setSaved] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);
  const [resumeName, setResumeName] = useState("");
  const [fileError, setFileError] = useState("");
  return <section className="surface padded selection-registration internal-profile-form">
    <p className="privacy-eyebrow">FORM-PPO-RH-002.01 · SELEÇÃO INTERNA</p>
    <div className="section-heading"><h2>Ficha de seleção interna</h2><button type="button" className="button secondary small" onClick={() => document.getElementById("assinatura-eletronica")?.scrollIntoView({ block: "center" })}>Assinar ficha</button></div><p>Informe sua matrícula em Dados pessoais e sua área/setor em Informações profissionais no Porto Aurora. Você pode salvar e continuar depois.</p>
    {preview && <p className="alert">Demonstração: utilize dados fictícios. As alterações ficam somente nesta prévia.</p>}
    <div className="internal-profile-resume">
      {preview ? <><input ref={fileInput} type="file" hidden accept=".pdf,.docx" aria-label="Selecionar currículo de exemplo" onChange={event => {
        const file = event.target.files?.[0]; event.target.value = ""; setFileError("");
        if (!file) return;
        if (!/\.(pdf|docx)$/i.test(file.name)) { setFileError("Selecione um currículo em PDF ou DOCX."); return; }
        setResumeName(file.name);
      }} /><button type="button" className="button" onClick={() => fileInput.current?.click()}><Paperclip size={18} />{resumeName ? "Substituir currículo" : "Anexar currículo"}</button><p className="muted">PDF ou DOCX. Nesta prévia, o arquivo não será enviado nem armazenado.</p>{resumeName && <p role="status">Currículo selecionado para simulação: <strong>{resumeName}</strong></p>}{fileError && <p role="alert">{fileError}</p>}</> : <><a className="button secondary" href="#curriculo"><Paperclip size={18} />Anexar currículo</a><p className="muted">Envie ou atualize seu currículo em PDF ou DOCX.</p></>}
    </div>
    <p className="muted">A recomendação e a assinatura do gestor são preenchidas pela gestão e não fazem parte dos campos editáveis do colaborador.</p>
    {saved && <p className="alert success" role="status">{preview ? "Perfil salvo somente nesta prévia." : "Perfil interno salvo. Você pode continuar o preenchimento depois."}</p>}
    <SchemaForm schema={schema as Schema} initial={initial} submitLabel={preview ? "Salvar perfil na prévia" : "Salvar ficha interna"} onSubmit={async data => { setSaved(false); await onSubmit(data); setSaved(true); }} />
  </section>;
}

export function InternalRegistration({ identity }: { identity: Record<string, unknown> }) {
  const client = useQueryClient();
  const query = useQuery({ queryKey: ["internal-registration"], queryFn: () => api<Registration>("/candidates/me/internal-registration"), staleTime: Infinity, refetchOnWindowFocus: false });
  return <><ErrorBox error={query.error} />{query.isPending ? <p role="status">Carregando perfil interno…</p> : query.isError ? <button className="button secondary" onClick={() => void query.refetch()}>Tentar novamente</button> : <InternalRegistrationForm initial={query.data.data ?? { personal: { name: str(identity.name), email: str(identity.email) } }} onSubmit={async data => {
    const result = await put<Registration>("/candidates/me/internal-registration", { data, version: query.data.version });
    client.setQueryData(["internal-registration"], result);
  }} />}</>;
}
