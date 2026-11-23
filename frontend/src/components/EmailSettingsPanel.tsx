import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Mail, Save, TestTubeDiagonal } from "lucide-react";
import { api, post, put } from "../lib/api";
import { date } from "../lib/labels";
import { PasswordInput } from "./PasswordInput";
import { ErrorBox } from "./ui";

type Form = { enabled: boolean; host: string; port: number; auth_mode: "basic" | "oauth2"; sender: string; username: string;
  tenant_id: string; client_id: string; starttls: boolean; validate_tls: boolean; notifications_enabled: boolean; public_url: string; test_recipient: string };
type Settings = Form & { version: number | null; configured: boolean; test_mode: boolean; secret_configured: boolean;
  password_configured: boolean; refresh_token_configured: boolean; access_token_configured: boolean; last_test_at: string | null };
const defaults: Form = { enabled: false, host: "smtp.office365.com", port: 587, auth_mode: "oauth2", sender: "", username: "", tenant_id: "", client_id: "", starttls: true, validate_tls: true, notifications_enabled: true, public_url: "", test_recipient: "" };
const blankSecrets = { password: "", client_secret: "", refresh_token: "", access_token: "" };

export function EmailSettingsPanel() {
  const client = useQueryClient();
  const query = useQuery({ queryKey: ["smtp-settings"], queryFn: () => api<Settings>("/smtp-settings") });
  const [changes, setChanges] = useState<Partial<Form>>({});
  const [secrets, setSecrets] = useState(blankSecrets);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>();
  const [notice, setNotice] = useState("");
  const form = { ...defaults, ...Object.fromEntries(Object.keys(defaults).map(key => [key, query.data?.[key as keyof Form] ?? defaults[key as keyof Form]])), ...changes } as Form;
  const dirty = Object.keys(changes).length > 0 || Object.values(secrets).some(Boolean);
  function update<K extends keyof Form>(key: K, value: Form[K]) { setChanges(current => ({ ...current, [key]: value })); setNotice(""); }
  const field = (key: keyof Form, title: string, type = "text", placeholder = "") => <label className="field"><span>{title}</span><input type={type} value={String(form[key])} onChange={event => update(key, key === "port" ? Number(event.target.value) : event.target.value)} placeholder={placeholder} min={key === "port" ? 1 : undefined} max={key === "port" ? 65535 : undefined} autoComplete="off" /></label>;
  const toggle = (key: "enabled" | "starttls" | "validate_tls" | "notifications_enabled", title: string) => <label className="email-setting-toggle"><input type="checkbox" checked={form[key]} onChange={event => update(key, event.target.checked)} /><span>{title}</span></label>;
  const secret = (key: keyof typeof blankSecrets, title: string, configured: boolean) => <label className="field"><span>{title}</span><PasswordInput value={secrets[key]} aria-label={title} autoComplete="new-password" maxLength={20000} onChange={event => { setSecrets(current => ({ ...current, [key]: event.target.value })); setNotice(""); }} placeholder={configured ? "Já configurado; deixe vazio para manter" : "Preencha para configurar"} /><small>{configured ? "Credencial salva. Preencha somente para trocar." : "Armazenado de forma criptografada e não exibido novamente."}</small></label>;
  return <section className="surface padded email-settings-panel">
    <header className="email-settings-heading"><div><h2><Mail size={21} aria-hidden="true" /> E-mail</h2><p>Use SMTP autenticado por senha ou OAuth2. Para Microsoft 365, configure OAuth2.</p></div><div className="email-settings-badges"><span className={query.data?.enabled ? "enabled" : "disabled"}>{query.data?.enabled ? "Ativo" : "Inativo"}</span><span className={query.data?.configured ? "configured" : "disabled"}>{query.data?.configured ? "Configurado" : "Configuração pendente"}</span></div></header>
    <ErrorBox error={error ?? query.error} />{notice && <p className="alert success" role="status">{notice}</p>}
    {query.isPending ? <p role="status">Carregando configuração de e-mail…</p> : query.isError ? <button className="button secondary" onClick={() => void query.refetch()}>Tentar novamente</button> : <form onSubmit={async event => {
      event.preventDefault(); setBusy(true); setError(undefined); setNotice("");
      try { const result = await put<Settings>("/smtp-settings", { ...form, ...secrets, version: query.data.version }); client.setQueryData(["smtp-settings"], result); setChanges({}); setSecrets(blankSecrets); await Promise.all([client.invalidateQueries({ queryKey: ["settings"] }), client.invalidateQueries({ queryKey: ["public-features"] })]); setNotice("Configuração salva. Use Testar e-mail para verificar o envio."); }
      catch (err) { setError(err); } finally { setBusy(false); }
    }}>
      {query.data.test_mode && <p className="alert">A caixa de teste local ainda está em uso. Ao salvar esta configuração, o canal passará a usar os dados informados abaixo.</p>}
      <fieldset disabled={busy} className="email-settings-fields"><div className="email-settings-grid">
        {toggle("enabled", "Ativar canal de e-mail")}
        <label className="field"><span>Autenticação</span><select value={form.auth_mode} onChange={event => update("auth_mode", event.target.value as Form["auth_mode"])}><option value="oauth2">OAuth2</option><option value="basic">Senha SMTP</option></select></label>
        {field("host", "SMTP host", "text", "smtp.office365.com")}{field("port", "SMTP porta", "number")}
        {field("sender", "Remetente", "email", "tgpm.talentos@portoaurora.example")}{field("username", "Usuário SMTP", "text", "tgpm.talentos@portoaurora.example")}
        {form.auth_mode === "basic" ? secret("password", "Senha SMTP (preencha somente para trocar)", query.data.password_configured) : <>
          {field("client_id", "Client ID")}{field("tenant_id", "Tenant ID Microsoft 365")}
          {secret("client_secret", "Client secret (preencha somente para trocar)", query.data.secret_configured)}{secret("refresh_token", "Refresh token (preencha somente para trocar)", query.data.refresh_token_configured)}
          {secret("access_token", "Access token opcional", query.data.access_token_configured)}
        </>}
        {toggle("starttls", "STARTTLS obrigatório")}{toggle("validate_tls", "Validar certificado TLS")}
        {field("test_recipient", "Destinatário de teste", "email")}
        {field("public_url", "Endereço público do portal", "url", "https://talentos.portoaurora.example")}
        {toggle("notifications_enabled", "Enviar notificações da plataforma por e-mail")}
      </div></fieldset>
      <p className="muted email-settings-help">Campos secretos vazios mantêm as credenciais já salvas. Na porta 465, a conexão usa TLS direto. <a href="https://learn.microsoft.com/en-us/exchange/client-developer/legacy-protocols/how-to-authenticate-an-imap-pop-smtp-application-by-using-oauth" target="_blank" rel="noreferrer">Configurar autorização no Microsoft 365</a></p>
      <div className="smtp-actions"><button className="button" disabled={busy}><Save size={17} />{busy ? "Processando…" : "Salvar configuração"}</button><button type="button" className="button secondary" disabled={busy || dirty || !query.data.enabled || !form.test_recipient} onClick={async () => {
        setBusy(true); setError(undefined); setNotice("");
        try { const result = await post<{ message: string; recipient: string }>("/smtp-settings/test", { recipient: form.test_recipient }); setNotice(result.message + " Destinatário: " + result.recipient); await client.invalidateQueries({ queryKey: ["smtp-settings"] }); }
        catch (err) { setError(err); } finally { setBusy(false); }
      }}><TestTubeDiagonal size={17} />Testar e-mail</button></div>
      {dirty && <p className="muted" role="status">Salve as alterações antes de testar o envio.</p>}{query.data.last_test_at && <p className="muted">Último teste aceito pelo servidor: {date(query.data.last_test_at)}</p>}
    </form>}
  </section>;
}
