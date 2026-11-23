import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { Brand } from "../components/Brand";
import { PasswordInput } from "../components/PasswordInput";
import { TestMailbox } from "../components/TestMailbox";
import { ErrorBox } from "../components/ui";
import { post } from "../lib/api";
import { safeReturnPath } from "../lib/returnPath";

export function EmployeeRegisterPage() {
  const [params] = useSearchParams();
  const next = safeReturnPath(params.get("next"));
  const login = "/entrar-colaborador" + (next ? "?next=" + encodeURIComponent(next) : "");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [registrationId, setRegistrationId] = useState("");
  const [proof, setProof] = useState("");
  const [code, setCode] = useState("");
  const [done, setDone] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>();
  const [notice, setNotice] = useState("");
  const [resendAfter, setResendAfter] = useState(0);
  useEffect(() => {
    if (resendAfter <= 0) return;
    const timer = window.setTimeout(() => setResendAfter(value => value - 1), 1000);
    return () => window.clearTimeout(timer);
  }, [resendAfter]);
  return <main className="narrow-page">
    <Link className="brand" to="/oportunidades-internas"><Brand /></Link>
    <p><Link className="back-link" to="/oportunidades-internas">← Voltar ao portal interno</Link></p>
    <h1>Cadastro de colaborador</h1>
    <p>Cadastre seu nome, e-mail pessoal ou corporativo e senha. Informe sua matrícula e área de trabalho na ficha interna do perfil. Confirme o código enviado ao seu e-mail para liberar o acesso.</p>
    {done ? <section className="surface padded" role="status"><h2>Cadastro concluído</h2><p>Seu e-mail foi confirmado. Agora você pode acessar as vagas internas com seu e-mail pessoal ou corporativo e sua senha.</p><Link className="button" to={login}>Entrar como colaborador</Link></section> : !registrationId ? <form className="surface padded" onSubmit={async event => {
      event.preventDefault(); setBusy(true); setError(undefined);
      try {
        const result = await post<{ registration_id: string; resend_after: number }>("/auth/register-employee", { name, email });
        setRegistrationId(result.registration_id); setResendAfter(result.resend_after);
      } catch (err) { setError(err); } finally { setBusy(false); }
    }}>
      <ErrorBox error={error} />
      <label className="field"><span>Nome completo</span><input required minLength={3} maxLength={180} autoComplete="name" value={name} onChange={e => setName(e.target.value)} /></label>
      <label className="field"><span>E-mail pessoal ou corporativo</span><input aria-label="E-mail pessoal ou corporativo" type="email" required maxLength={320} autoComplete="email" placeholder="seuemail@exemplo.com" value={email} onChange={e => {
        const value = e.target.value;
        setEmail(value);
      }} /><small>O código de confirmação será enviado para este endereço.</small></label>
      <label className="field"><span>Senha</span><PasswordInput aria-label="Senha" required minLength={6} maxLength={6} title="Use exatamente 6 caracteres: letras, números ou símbolos" autoComplete="new-password" value={password} onChange={e => setPassword(e.target.value)} /><small>Use 6 caracteres. Você pode combinar letras, números e símbolos.</small></label>
      <button className="button" disabled={busy}>{busy ? "Enviando…" : "Enviar código de verificação"}</button>
    </form> : <form className="surface padded" onSubmit={async event => {
      event.preventDefault(); setBusy(true); setError(undefined); setNotice("");
      try {
        let token = proof;
        if (!token) {
          const verified = await post<{ completion_token: string }>("/auth/employee-email-code/confirm", { registration_id: registrationId, code });
          token = verified.completion_token; setProof(token);
        }
        await post("/auth/employee-registration/complete", { completion_token: token, password });
        setPassword(""); setProof(""); setCode(""); setDone(true);
      } catch (err) { setError(err); } finally { setBusy(false); }
    }}>
      <h2>Confirme seu e-mail pessoal ou corporativo</h2><p>Enviamos um código de seis dígitos para <strong>{email}</strong>. Ele é válido por dez minutos. Confira também a pasta de spam.</p>
      <TestMailbox /><ErrorBox error={error} />{notice && <p role="status">{notice}</p>}
      {!proof && <label className="field"><span>Código de verificação</span><input required inputMode="numeric" autoComplete="one-time-code" pattern="[0-9]{6}" minLength={6} maxLength={6} value={code} onChange={e => setCode(e.target.value.replace(/\D/g, "").slice(0, 6))} placeholder="000000" autoFocus /></label>}
      <button className="button" disabled={busy || (!proof && code.length !== 6)}>{busy ? "Concluindo…" : "Confirmar código e concluir cadastro"}</button>
      {!proof && <p><button type="button" className="text-button" disabled={busy || resendAfter > 0} onClick={async () => {
        setBusy(true); setError(undefined); setNotice("");
        try { const result = await post<{ resend_after: number }>("/auth/employee-email-code/resend", { registration_id: registrationId }); setResendAfter(result.resend_after); setCode(""); setNotice("Novo código enviado. Use o código mais recente."); }
        catch (err) { setError(err); } finally { setBusy(false); }
      }}>{resendAfter > 0 ? `Reenviar código em ${resendAfter}s` : "Reenviar código"}</button></p>}
      <p><button type="button" className="text-button" disabled={busy} onClick={() => { setRegistrationId(""); setProof(""); setCode(""); setError(undefined); }}>Voltar aos dados do cadastro</button></p>
    </form>}
    {!done && <p>Já possui cadastro? <Link to={login}>Entrar como colaborador</Link></p>}
  </main>;
}
