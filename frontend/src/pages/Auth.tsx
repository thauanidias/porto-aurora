import { PasswordInput } from "../components/PasswordInput";
import { portal } from "../lib/portal";
import { Brand } from "../components/Brand";
import { TestMailbox } from "../components/TestMailbox";
import { registrationReturnPath, safeReturnPath } from "../lib/returnPath";
import { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, ArrowRight, BriefcaseBusiness, Check, FileText, Mail, ShieldCheck, UserRound } from "lucide-react";
import { post, setToken } from "../lib/api";
import { ErrorBox } from "../components/ui";

const schema = z.object({
  email: z.string().email("Informe um e-mail válido."),
  password: z.string().min(1, "Informe sua senha."),
});
type Values = z.infer<typeof schema>;

function inboxUrl(email: string): string | undefined {
  const domain = email.trim().toLowerCase().split("@")[1];
  if (["gmail.com", "googlemail.com"].includes(domain))
    return "https://mail.google.com/mail/u/0/#inbox";
  if (
    [
      "outlook.com",
      "hotmail.com",
      "live.com",
      "msn.com",
      "portoaurora.example",
    ].includes(domain)
  )
    return "https://outlook.office.com/mail/";
  if (["yahoo.com", "yahoo.com.br"].includes(domain))
    return "https://mail.yahoo.com/";
  if (["icloud.com", "me.com", "mac.com"].includes(domain))
    return "https://www.icloud.com/mail/";
  return undefined;
}

export function LoginPage({ internal = false, manager = false, employee = false }: { internal?: boolean; manager?: boolean; employee?: boolean }) {
  const [error, setError] = useState<unknown>();
  const navigate = useNavigate();
  const client = useQueryClient();
  const [params] = useSearchParams();
  const internalAccess = internal || manager;
  const home = internalAccess || employee ? "/oportunidades-internas" : "/carreiras";
  const { register, handleSubmit, formState } = useForm<Values>({
    resolver: zodResolver(schema),
  });
  return (
    <div className={`auth-layout${!internalAccess && !employee ? " candidate-login" : ""}`}>
      <aside className="auth-aside">
        <Link className="brand" to={home}>
          <Brand inverse />
        </Link>
        <div>
          <p className="eyebrow">{employee ? "OPORTUNIDADES INTERNAS" : internalAccess ? manager ? "GESTORES" : "RECURSOS HUMANOS" : "PESSOAS QUE MOVEM O TERMINAL"}</p>
          <h1>
            {employee ? "Seu próximo passo." : internalAccess ? "Conecte talentos." : "O próximo passo"}
            <br />
            {employee ? "Dentro do nosso time." : internalAccess ? "Fortaleça sua equipe." : "começa aqui."}
          </h1>
          <p>
            {employee ? "Explore as vagas internas e continue construindo sua carreira no Porto Aurora." : internalAccess ? "Da solicitação de vagas à contratação, acompanhe cada etapa em um só lugar." : "Acompanhe suas oportunidades e faça parte do Porto Aurora."}
          </p>
        </div>
        <span>Porto Aurora</span>
      </aside>
      <main className="auth-main">
        <div className="auth-card">
          <Link className="back-link" to={home}>
            {internalAccess || employee ? "← Voltar ao portal interno" : "← Voltar às oportunidades"}
          </Link>
          <h1>{employee ? "Entrada do colaborador" : internalAccess ? manager ? "Entrada do gestor" : "Entrada do RH" : "Área do candidato"}</h1>
          <p className="muted">{internalAccess ? "Entre com seu e-mail e senha do Porto Aurora Talentos." : employee ? "Entre com seu e-mail corporativo e a senha cadastrada no portal." : "Entre para preencher seu currículo e acompanhar suas inscrições."}</p>
          <ErrorBox error={error} />
          <form
            onSubmit={handleSubmit(async (values) => {
              setError(undefined);
              try {
                const result = await post<{
                  access_token: string;
                  user: { kind: string };
                }>("/auth/login", { ...values, source: "LOCAL", area: employee ? "CANDIDATO" : manager ? "GESTOR" : internal ? "RH" : "CANDIDATO" });
                setToken(result.access_token);
                await client.invalidateQueries({ queryKey: ["session"] });
                const next = safeReturnPath(params.get("next"));
                const base = manager ? "/gestor" : internal ? "/app" : "/candidato";
                const allowedNext = next && (internalAccess
                  ? next === base || next.startsWith(base + "/")
                  : !/^\/(app|gestor)(\/|$)/.test(next));
                navigate(allowedNext ? next : employee ? "/oportunidades-internas" : internalAccess ? base : "/candidato/perfil");
              } catch (e) {
                setError(e);
              }
            })}
          >
            <label className="field">
              <span>{employee ? "E-mail pessoal ou corporativo" : "E-mail"}</span>
              <input
                type="email"
                autoComplete="username"
                autoCapitalize="none"
                spellCheck={false}
                placeholder="seuemail@exemplo.com"
                {...register("email")}
              />
              {formState.errors.email && (
                <small role="alert">{formState.errors.email.message}</small>
              )}
            </label>
            <label className="field">
              <span>Senha</span>
              <PasswordInput
                type="password"
                autoComplete="current-password"
                placeholder="Digite sua senha"
                {...register("password")}
              />
            </label>
            <button className="button full" disabled={formState.isSubmitting}>
              {formState.isSubmitting ? "Entrando…" : "Entrar"} <ArrowRight size={17} />
            </button>
          </form>
          {!internal && <Link className="text-button" to={manager ? "/recuperar?area=gestor" : "/recuperar"}>
            Esqueci minha senha
          </Link>}
          <div className="auth-divider" />
          {employee && <p>Primeiro acesso? <Link to={"/cadastro-colaborador" + (safeReturnPath(params.get("next")) ? "?next=" + encodeURIComponent(params.get("next")!) : "")}>Cadastre seu e-mail corporativo</Link></p>}
          {!internalAccess && !employee && <p>
            Ainda não tem conta? <Link to={"/cadastro" + (safeReturnPath(params.get("next")) ? "?next=" + encodeURIComponent(params.get("next")!) : "")}>Cadastre-se</Link>
          </p>}
          {manager && <section className="internal-access">
            <p>É gestor e ainda não tem acesso? <Link to="/cadastro-gestor">Solicitar acesso</Link></p>
          </section>}
          <div className="security-note">
            <ShieldCheck size={16} />
            Seus dados têm acesso controlado.
          </div>
        </div>
      </main>
    </div>
  );
}
export function RegisterPage() {
  const [returnTo] = useState(registrationReturnPath);
  const [error, setError] = useState<unknown>();
  const [busy, setBusy] = useState(false);
  const [pending, setPending] = useState<{
    email: string;
    message: string;
    deliveryEnabled: boolean;
    testSetupUrl?: string;
  }>();
  const [resent, setResent] = useState(false);
  const navigate = useNavigate();
  const client = useQueryClient();
  return (
    <div className="candidate-register-page">
      <header className="register-header"><Link className="brand" to="/carreiras" aria-label="Porto Aurora Talentos — Portal de carreiras">
        <Brand />
      </Link><Link className="register-back" to="/carreiras"><ArrowLeft size={16} aria-hidden="true" />Voltar às oportunidades</Link></header>
      <main className="register-layout">
        <section className="register-intro" aria-label="Conheça o Porto Aurora Talentos"><span className="register-eyebrow">CONSTRUA SUA TRAJETÓRIA</span><h2>Seu talento.<br /><span>Novas possibilidades.</span></h2><p>Encontre oportunidades e acompanhe cada passo da sua candidatura no Porto Aurora.</p>
          <div className="register-profile-art" aria-hidden="true"><div className="register-art-icon"><BriefcaseBusiness size={30} strokeWidth={1.5} /></div><div className="register-art-profile"><span><UserRound size={24} /></span><div><strong>Sua próxima oportunidade</strong><small>Começa com o seu perfil</small></div><Check size={19} /></div><div className="register-art-resume"><FileText size={20} /><span>Seu currículo, sua história</span><span className="register-art-dot" /></div></div>
          <div className="register-trust"><ShieldCheck size={19} aria-hidden="true" /><p>Seus dados são utilizados conforme nosso <Link to="/privacidade">aviso de privacidade</Link>.</p></div>
        </section>
        <section className="register-card" aria-label="Cadastro de candidato">
      <ol className="register-progress" aria-label="Etapas para começar"><li className={!pending ? "current" : "complete"} aria-current={!pending ? "step" : undefined}><span>{pending ? <Check size={13} aria-hidden="true" /> : "1"}</span>Conta</li><li className={pending ? "current" : ""} aria-current={pending ? "step" : undefined}><span>2</span>E-mail</li><li><span>3</span>Perfil</li></ol>
      <Link className="register-back register-card-back" to={returnTo || "/carreiras"} aria-label="Voltar às oportunidades"><ArrowLeft size={18} aria-hidden="true" />Voltar</Link>
      <span className="register-card-eyebrow">BEM-VINDO AO PORTO AURORA TALENTOS</span>
      <h1>Crie sua conta</h1>
      <p className="register-description">Informe seu nome e e-mail. Depois, confirme seu endereço, crie sua senha e complete seu perfil.</p>
      <ErrorBox error={error} />
      {pending ? (
        <section className="surface padded register-confirmation">
          <h2>Confirme seu e-mail</h2>
          <TestMailbox />
          <p role="status">{pending.message}</p>
          {pending.deliveryEnabled && (
            <>
              <p>
                Enviamos as instruções para <strong>{pending.email}</strong>.
                Abra a mensagem para confirmar seu e-mail e criar sua senha.
                Verifique também a caixa de spam. O link é válido por 30 minutos.
              </p>
              {inboxUrl(pending.email) && (
                <p>
                  <a
                    className="button"
                    href={inboxUrl(pending.email)}
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    Abrir meu e-mail ↗
                  </a>
                </p>
              )}
            </>
          )}
          {pending.testSetupUrl && (
            <p>
              <Link className="button" to={pending.testSetupUrl}>
                Abrir link de teste para criar senha
              </Link>
              <small>
                Ambiente de testes: este link não confirma que você tem acesso
                ao e-mail informado.
              </small>
            </p>
          )}
          <button
            type="button"
            className="button secondary"
            disabled={busy || resent || !pending.deliveryEnabled}
            onClick={async () => {
              setBusy(true);
              setError(undefined);
              try {
                await post("/auth/request-link", {
                  email: pending.email,
                  purpose: "VERIFY",
                  return_to: returnTo,
                });
                setResent(true);
              } catch (e) {
                setError(e);
              } finally {
                setBusy(false);
              }
            }}
          >
            Reenviar e-mail de confirmação
          </button>
          {resent && (
            <p role="status">
              Solicitação de reenvio registrada. Confira seu e-mail.
            </p>
          )}
          <p>
            <Link to="/entrar">Ir para o acesso</Link>
          </p>
        </section>
      ) : (
        <form
          onSubmit={async (e) => {
            e.preventDefault();
            setBusy(true);
            const values = Object.fromEntries(new FormData(e.currentTarget));
            try {
              const result = await post<{
                verification_required: boolean;
                message: string;
                email_delivery_enabled: boolean;
                test_setup_url?: string;
                access_token?: string;
              }>("/auth/register", {
                name: values.name,
                email: values.email,
                consent: false,
                defer_consent_to_profile: true,
                return_to: returnTo,
              });
              if (result.access_token) {
                setToken(result.access_token);
                await client.invalidateQueries({ queryKey: ["session"] });
                sessionStorage.removeItem("tgpm-registration-return");
                navigate("/candidato/perfil?cadastro=1" + (returnTo ? "&next=" + encodeURIComponent(returnTo) : ""));
              } else
                setPending({
                  email: String(values.email),
                  message: result.message,
                  deliveryEnabled: result.email_delivery_enabled,
                  testSetupUrl: result.test_setup_url,
                });
            } catch (e) {
              setError(e);
            } finally {
              setBusy(false);
            }
          }}
        >
          <label className="field">
            <span>Nome completo</span>
            <div className="register-input"><UserRound size={18} aria-hidden="true" />
            <input
              name="name"
                            required
              minLength={3}
              autoComplete="name"
              placeholder="Digite seu nome completo"
            />
            </div>
          </label>
          <label className="field">
            <span>E-mail</span>
            <div className="register-input"><Mail size={18} aria-hidden="true" />
            <input
              name="email"
                            type="email"
              required
              autoComplete="email"
              placeholder="seunome@exemplo.com"
            />
            </div>
          </label>
          <p className="register-email-hint">Use um e-mail que você acessa com frequência.</p>
          <button
            className="button full"
            disabled={busy}
          >
            {busy ? "Criando conta…" : "Criar conta"}
            <ArrowRight size={17} aria-hidden="true" />
          </button>
        </form>
      )}
      <p className="register-login">
        Já tem conta? <Link to={returnTo ? "/entrar?next=" + encodeURIComponent("/candidato/perfil?next=" + encodeURIComponent(returnTo)) : "/entrar"}>Entrar</Link>
      </p>
        </section>
      </main>
      <footer className="register-footer">Porto Aurora Talentos <span>Porto Aurora</span></footer>
    </div>
  );
}
export function RecoverPage({
  verification = false,
}: {
  verification?: boolean;
}) {
  const [params] = useSearchParams();
  const loginPath = portal.area === "GESTOR" || (portal.area === "LOCAL" && params.get("area") === "gestor") ? "/entrar-gestor" : portal.area === "RH" || (portal.area === "LOCAL" && params.get("area") === "rh") ? "/entrar-rh" : "/entrar";
  const [error, setError] = useState<unknown>();
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  return (
    <main className="narrow-page">
      <Link to={loginPath}>← Voltar</Link>
      <h1>{verification ? "Confirmar e-mail" : "Redefinir senha"}</h1>
      <TestMailbox />
      <p>
        {verification
          ? "Informe o e-mail cadastrado para receber um novo link de confirmação."
          : "Informe o e-mail usado no cadastro. Você receberá um link para criar uma nova senha, válido por 30 minutos."}
      </p>
      <ErrorBox error={error} />
      {message ? (
        <div className="alert success" role="status">
          <p>{message}</p>
          <p>Confira também a caixa de spam.</p>
          <Link to={loginPath}>Voltar para entrar</Link>
        </div>
      ) : (
        <form
          onSubmit={async (e) => {
            e.preventDefault();
            if (busy) return;
            setBusy(true);
            setError(undefined);
            const values = new FormData(e.currentTarget);
            try {
              const r = await post<{ message: string }>("/auth/request-link", {
                email: values.get("email"),
                purpose: verification ? "VERIFY" : "RESET",
              });
              setMessage(r.message);
            } catch (e) {
              setError(e);
            } finally {
              setBusy(false);
            }
          }}
        >
          <label className="field">
            <span>E-mail</span>
            <input type="email" name="email" autoComplete="email" required />
          </label>
          <button className="button" disabled={busy}>
            {busy ? "Enviando…" : verification ? "Enviar instruções" : "Enviar link para redefinir senha"}
          </button>
        </form>
      )}
    </main>
  );
}
export function ConfirmPage() {
  const [error, setError] = useState<unknown>();
  const [busy, setBusy] = useState(false);
  const navigate = useNavigate();
  const client = useQueryClient();
  const [quick] = useState(() =>
    new URLSearchParams(window.location.hash.slice(1)).get("quick"),
  );
  const [token] = useState(
    () => new URLSearchParams(window.location.hash.slice(1)).get("token") ?? "",
  );
  const [purpose] = useState(
    () => new URLSearchParams(window.location.hash.slice(1)).get("purpose"),
  );
  const requiresPassword = purpose === "SETUP" || purpose === "RESET";
  const [returnTo] = useState(() => safeReturnPath(new URLSearchParams(window.location.hash.slice(1)).get("next")));
  return (
    <main className="narrow-page">
      <h1>{purpose === "SETUP" ? "Confirme seu e-mail e crie sua senha" : purpose === "RESET" ? "Crie sua nova senha" : "Confirmar acesso"}</h1>
      {requiresPassword && <p>Use uma senha de 6 caracteres. Você pode combinar letras, números e símbolos. Confirme abaixo.</p>}
      <ErrorBox error={error} />
      {!token && !quick && <div className="alert" role="alert"><p>Este endereço não contém um link válido de confirmação. Abra o botão do e-mail de cadastro ou solicite um novo link.</p><Link to="/verificar-email">Solicitar novo link de confirmação</Link></div>}
      <form
        onSubmit={async (e) => {
          e.preventDefault();
          if (busy || (!token && !quick)) return;
          setError(undefined);
          const data = new FormData(e.currentTarget);
          if (
            requiresPassword &&
            data.get("password") !== data.get("password_confirmation")
          ) {
            setError(new Error("As senhas não coincidem."));
            return;
          }
          setBusy(true);
          try {
            const result = await post<{ access_token: string; user: {kind: string} }>(
              quick ? "/auth/consume-quick" : "/auth/consume-link",
              quick
                ? { token: quick }
                : { token, password: data.get("password") || null },
            );
            setToken(result.access_token);
            history.replaceState(null, "", "/confirmar");
            await client.invalidateQueries({ queryKey: ["session"] });
            sessionStorage.removeItem("tgpm-registration-return");
            navigate(result.user.kind === "INTERNAL" ? (portal.area === "RH" ? "/app" : portal.area === "GESTOR" ? "/gestor" : returnTo ?? "/gestor") : purpose === "SETUP"
              ? "/candidato/perfil?cadastro=1" + (returnTo ? "&next=" + encodeURIComponent(returnTo) : "")
              : returnTo ?? "/candidato");
          } catch (e) {
            setError(e);
          } finally {
            setBusy(false);
          }
        }}
      >
        {requiresPassword && !quick && (
          <label className="field">
            <span>{purpose === "SETUP" ? "Crie sua senha" : "Nova senha"}</span>
            <PasswordInput
              name="password"
              type="password"
              minLength={6}
              maxLength={6}
              title="Use exatamente 6 caracteres: letras, números ou símbolos"
              required={requiresPassword}
              autoComplete="new-password"
            />
          </label>
        )}
        {requiresPassword && !quick && (
          <label className="field">
            <span>Confirme a senha</span>
            <PasswordInput
              name="password_confirmation"
              type="password"
              minLength={6}
              maxLength={6}
              title="Use exatamente 6 caracteres: letras, números ou símbolos"
              required
              autoComplete="new-password"
            />
          </label>
        )}
        <button className="button" disabled={busy || (!token && !quick)}>
          {busy ? "Salvando e entrando…" : purpose === "RESET" ? "Salvar nova senha e entrar" : "Confirmar e acessar"}
        </button>
      </form>
      {Boolean(error) && <p><Link to="/verificar-email">Solicitar outro link de confirmação</Link></p>}
      <p><Link to="/entrar">Já confirmou seu cadastro? Entrar na conta</Link></p>
    </main>
  );
}
