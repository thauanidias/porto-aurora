import { BackButton } from "./BackButton";
import { CandidateConsentPrompt } from "./CandidateConsentPrompt";
import { Brand } from "./Brand";
import { RHGuideContext, RHProcessGuide } from "./RHProcessGuide";
import { canUseRHGuide } from "../lib/rhProcessGuide";
import { useCandidateActions } from "../lib/candidateActions";
import { useEffect, useState } from "react";
import { NavLink, Link, Outlet, useLocation, useNavigate } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Bell,
  ArrowUpRight,
  Check,
  BriefcaseBusiness,
  CalendarDays,
  CircleHelp,
  ChartNoAxesCombined,
  ChevronLeft,
  ChevronRight,
  ChevronDown,
  ClipboardList,
  FileCheck2,
  FileText,
  GraduationCap,
  LogOut,
  Menu,
  MessageSquare,
  Moon,
  Search,
  Settings,
  ShieldCheck,
  Sun,
  Users,
  X,
} from "lucide-react";
import { api, post, setToken, str, type Collection } from "../lib/api";
import { isManager, useSession } from "../lib/session";
import { safeReturnPath } from "../lib/returnPath";
import { ErrorBox, Modal } from "./ui";
import { useCandidateJourney } from "../lib/candidateJourney";
import { LockKeyhole } from "lucide-react";

const internalNav = [
  ["trabalho", "Tarefas", ClipboardList, ""],
  ["vagas", "Vagas", BriefcaseBusiness, "vacancy.view"],
  ["solicitacoes", "Solicitações de vagas", FileText, "request.create|request.approve"],
  ["gestores", "Gestores", Users, "user.manage"],
  ["candidatos", "Candidatos", Users, "candidate.view"],
  ["candidaturas", "Candidaturas externas", ClipboardList, "candidate.view"],
  ["candidaturas-internas", "Candidaturas internas", BriefcaseBusiness, "candidate.view"],
  ["mensagens", "Mensagens", MessageSquare, "request.create|message.send"],
  ["banco", "Banco de talentos", Users, "talent.manage"],
  ["entrevistas", "Entrevistas", CalendarDays, "candidate.view"],
  ["avaliacoes", "Feedback dos candidatos", FileCheck2, "candidate.evaluate"],
  ["testes", "Testes", GraduationCap, "test.manage"],
  ["documentos", "Documentos", FileCheck2, "candidate.view"],
  ["configuracao-plataforma", "Configuração da plataforma", Settings, "config.manage|user.manage|privacy.manage|audit.view|candidate.view"],
  ["importacao", "Relatório por vagas", ChartNoAxesCombined, "report.view"],
] as const;
const candidateNav = [
  ["vagas", "Vagas disponíveis", Search],
  ["perfil", "Meu perfil", Users],
  ["", "Minhas candidaturas", BriefcaseBusiness],
  ["entrevistas", "Entrevistas", CalendarDays],
  ["testes", "Meus testes", GraduationCap],
  ["documentos", "Documentos", LockKeyhole],
  ["mensagens", "Mensagens", MessageSquare],
  ["privacidade", "Privacidade", ShieldCheck],
  ["sessoes", "Minhas sessões", Settings],
  ["pesquisas", "Sua experiência", FileText],
] as const;
export function Layout({ candidate = false }: { candidate?: boolean }) {
  const journey = useCandidateJourney(candidate);
  const candidateActions = useCandidateActions(candidate);
  const session = useSession();
  const unreadMessages = useQuery({ queryKey: ["message-unread", session.data?.user.id], queryFn: () => api<{ unread: number }>("/messages/unread-count"), enabled: Boolean(session.data && (candidate || session.data.permissions.includes("candidate.view"))), refetchInterval: 2000, refetchIntervalInBackground: true, refetchOnWindowFocus: "always" });
  const guideAllowed = !candidate && canUseRHGuide(session.data);
  const [guideState, setGuideState] = useState<{ user?: string; open: boolean }>({ open: false });
  const [guideStep, setGuideStep] = useState<number>();
  const guideUser = session.data?.user.id;
  const guideOpen = guideState.user === guideUser ? guideState.open : Boolean(guideAllowed && guideUser && localStorage.getItem("rh-process-guide-v1:" + guideUser) !== "seen");
  const changeGuide = (open: boolean) => {
    setGuideState({ user: guideUser, open });
    if (!open && guideAllowed && guideUser) localStorage.setItem("rh-process-guide-v1:" + guideUser, "seen");
  };
  const openGuide = (step?: number) => { setGuideStep(step); changeGuide(true); setMobile(false); };
  const navigate = useNavigate();
  const currentLocation = useLocation();
  const client = useQueryClient();
  const [collapsed, setCollapsed] = useState(
    localStorage.getItem("sidebar") === "collapsed",
  );
  const [mobile, setMobile] = useState(false);
  useEffect(() => {
    if (!mobile) return;
    const previousFocus = document.activeElement as HTMLElement | null;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const drawer = document.getElementById("workspace-navigation");
    const focusable = () => [...(drawer?.querySelectorAll<HTMLElement>('a[href], button:not([disabled]), summary') ?? [])].filter(element => element.getClientRects().length > 0);
    focusable()[0]?.focus();
    const keyboard = (event: KeyboardEvent) => {
      if (event.key === "Escape") { setMobile(false); return; }
      if (event.key !== "Tab") return;
      const elements = focusable();
      const first = elements[0], last = elements.at(-1);
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
    };
    const viewport = matchMedia("(min-width: 1025px)");
    const resize = () => { if (viewport.matches) setMobile(false); };
    document.addEventListener("keydown", keyboard);
    viewport.addEventListener("change", resize);
    return () => {
      document.body.style.overflow = previousOverflow;
      document.removeEventListener("keydown", keyboard);
      viewport.removeEventListener("change", resize);
      previousFocus?.focus();
    };
  }, [mobile]);
  const [dark, setDark] = useState(localStorage.getItem("theme") === "dark");
  const [notifications, setNotifications] = useState(false);
  const [actionError, setActionError] = useState<unknown>();
  const [pendingAction, setPendingAction] = useState("");
  const [search, setSearch] = useState(false);
  const [q, setQ] = useState("");
  const results = useQuery({
    queryKey: ["global-search", q],
    queryFn: () => api<Collection>("/search?q=" + encodeURIComponent(q)),
    enabled: search && q.length >= 2 && !candidate,
  });
  const notices = useQuery({
    queryKey: ["notifications"],
    queryFn: () => api<Collection & { unread: number }>("/notifications"),
    refetchInterval: 30000,
  });
  useEffect(() => {
    document.documentElement.dataset.theme = dark ? "dark" : "light";
    localStorage.setItem("theme", dark ? "dark" : "light");
  }, [dark]);
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === "k") {
        e.preventDefault();
        setSearch((v) => !v);
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, []);
  const manager = !candidate && isManager(session.data);
  useEffect(() => {
    document.body.classList.toggle("rh-workspace-document", !candidate && !manager);
    return () => document.body.classList.remove("rh-workspace-document");
  }, [candidate, manager]);
  const base = candidate ? "/candidato" : manager ? "/gestor" : "/app";
  const employee = candidate && Boolean(session.data?.permissions.includes("internal.view"));
  const nav = candidate
    ? employee ? [...candidateNav].sort((a, b) => Number(b[0] === "perfil") - Number(a[0] === "perfil")) : candidateNav
    : internalNav.filter(item => !manager || ["vagas", "candidatos", "solicitacoes", "entrevistas", "mensagens"].includes(item[0])).filter(
        (item) =>
          !item[3] ||
          item[3]
            .split("|")
            .some((permission) =>
              session.data?.permissions.includes(permission),
            ),
      );
  const mainPaths = ["vagas", "candidatos", "candidaturas", "candidaturas-internas", "entrevistas", "testes", "documentos", "mensagens", "trabalho", "solicitacoes", "gestores"];
  const mainNav = candidate || manager ? nav : nav.filter(item => mainPaths.includes(item[0])).sort((a, b) => mainPaths.indexOf(a[0]) - mainPaths.indexOf(b[0]));
  const otherNav = candidate || manager ? [] : nav.filter(item => !mainPaths.includes(item[0]));
  return (
    <div
      className={
        "app-layout " +
        (!candidate && !manager ? "rh-workspace " : "") +
        (collapsed ? "sidebar-collapsed " : "") +
        (mobile ? "mobile-open" : "")
      }
    >
      <a className="skip-link" href="#main-content">
        Pular para o conteúdo
      </a>
      <aside className="sidebar" id="workspace-navigation" aria-label="Menu principal">
        <button type="button" className="icon-button sidebar-close" aria-label="Fechar menu" onClick={() => setMobile(false)}><X size={20} /></button>
        <Link
          className="brand"
          to="/carreiras"
          aria-label="Porto Aurora Talentos — Portal de carreiras"
        >
          <Brand />
          <BriefcaseBusiness
            className="collapsed-brand-icon"
            size={24}
            aria-hidden="true"
          />
        </Link>
        <div className="workspace-label">
          {candidate ? session.data?.permissions.includes("internal.view") ? "ÁREA DO COLABORADOR" : "ÁREA DO CANDIDATO" : manager ? "ÁREA DO GESTOR" : "RECRUTAMENTO & SELEÇÃO"}
        </div>
        <nav aria-label="Menu principal">
          {mainNav.filter(([path]) => {
            if (!candidate) return true;
            const section = ({ entrevistas: "interviews", testes: "tests", documentos: "admission", mensagens: "messages" } as const)[path as "entrevistas" | "testes" | "documentos" | "mensagens"];
            return !section || journey.data?.sections[section]?.enabled === true;
          }).map(([path, name, Icon]) => (
            <div className="sidebar-nav-entry" key={path}>
            {!candidate && !manager && ["vagas", "solicitacoes", "entrevistas", "mensagens"].includes(path) && <div className="sidebar-section-label">{path === "vagas" ? "Visão geral e talentos" : path === "solicitacoes" ? "Gestores" : path === "entrevistas" ? "Processo seletivo" : "Comunicação e rotina"}</div>}
            <NavLink
              data-message-entry={path === "mensagens" ? "true" : undefined}
              to={base + (path ? "/" + path : "")}
              className={({ isActive }) => isActive || (path === "gestores" && currentLocation.pathname === "/app/solicitacoes-acesso-gestores") ? "active" : ""}
              end={!path}
              title={candidate && ["entrevistas", "testes"].includes(path) && !journey.data?.sections[path === "testes" ? "tests" : "interviews"].enabled ? name + " · Aguardando liberação da etapa pelo RH" : name}
              onClick={() => setMobile(false)}
            >
              <Icon size={19} />
              {candidate && ["entrevistas", "testes", "documentos", "mensagens"].includes(path) && !journey.data?.sections[path === "mensagens" ? "messages" : path === "documentos" ? "admission" : path === "testes" ? "tests" : "interviews"]?.enabled && <LockKeyhole size={13} aria-label="Etapa bloqueada" />}
              <span>{employee && path === "perfil" ? "Ficha interna e perfil" : candidate && path === "vagas" && session.data?.permissions.includes("internal.view") ? "Vagas internas" : manager ? ({ vagas: "Minhas vagas", candidatos: "Candidatos", solicitacoes: "Solicitações de vaga" } as Record<string, string>)[path] ?? name : name}</span>
              {path === "mensagens" && !manager && <span className="message-unread-count" aria-live="polite" aria-label={unreadMessages.data ? `${unreadMessages.data.unread} mensagens não lidas` : unreadMessages.isError ? "Contagem indisponível" : "Consultando mensagens não lidas"} title="Mensagens não lidas">{unreadMessages.data ? unreadMessages.data.unread > 99 ? "99+" : unreadMessages.data.unread : unreadMessages.isError ? "—" : "…"}</span>}
              {candidate && Boolean(candidateActions.data?.find(action => action.path === path)?.count) && <span className="candidate-action-count" aria-label="Ações disponíveis" title="Há uma ação disponível nesta área">{candidateActions.data?.find(action => action.path === path)?.count}</span>}
            </NavLink>
            </div>
          ))}
          {otherNav.length > 0 && <details className="rh-nav-more" open={otherNav.some(item => currentLocation.pathname.startsWith(base + "/" + item[0]))}>
            <summary aria-label="Outras áreas" title="Outras áreas"><Settings size={19} aria-hidden="true" /><span>Outras áreas</span><ChevronDown className="nav-chevron" size={14} aria-hidden="true" /></summary>
            {otherNav.map(([path, name, Icon]) => <NavLink key={path} to={base + "/" + path} title={name} onClick={() => setMobile(false)}><Icon size={19} /><span>{name}</span></NavLink>)}
          </details>}
          {session.data?.permissions.includes("internal.view") && (
            <NavLink to="/oportunidades-internas">
              <BriefcaseBusiness size={19} />
              <span>Oportunidades internas</span>
            </NavLink>
          )}
        </nav>
        <div className="sidebar-bottom">
          {guideAllowed && <button className="rh-guide-menu" title="Como funciona o sistema" aria-label="Como funciona o sistema" onClick={() => openGuide()}><CircleHelp size={19} aria-hidden="true" /><span>Como funciona o sistema</span></button>}
          <Link to={!candidate || session.data?.permissions.includes("internal.view") ? "/oportunidades-internas" : "/carreiras"}>
            <BriefcaseBusiness size={18} />
            <span>{!candidate || session.data?.permissions.includes("internal.view") ? "Portal interno" : "Portal de carreiras"}</span>
          </Link>
          <button
            aria-label={collapsed ? "Expandir menu" : "Recolher menu"}
            onClick={() => {
              setCollapsed(!collapsed);
              localStorage.setItem(
                "sidebar",
                !collapsed ? "collapsed" : "expanded",
              );
            }}
          >
            <ChevronLeft size={18} />
            <span>Recolher menu</span>
          </button>
        </div>
      </aside>
      {mobile && (
        <button
          className="sidebar-backdrop"
          aria-label="Fechar navegação"
          onClick={() => setMobile(false)}
        />
      )}
      <div className="workspace">
        <header className="topbar">
          <button
            className="icon-button mobile-menu"
            aria-label="Abrir navegação"
            aria-controls="workspace-navigation"
            aria-expanded={mobile}
            onClick={() => setMobile(true)}
          >
            <Menu size={21} />
          </button>
          <BackButton base={base} />
          <nav className="topbar-context" aria-label="Localização no sistema">
            <Link className="topbar-brand" to={base + (candidate ? "" : "/vagas")}>Porto Aurora Talentos</Link>
            <ChevronRight size={14} aria-hidden="true" />
            <span className="topbar-area">{candidate ? "Minha carreira" : manager ? "Gestão da equipe" : "Recursos humanos"}</span>
            <ChevronRight size={14} aria-hidden="true" />
            <strong aria-current="page">{(candidate ? candidateNav : internalNav).find(([path]) => path ? currentLocation.pathname === `${base}/${path}` || currentLocation.pathname.startsWith(`${base}/${path}/`) : currentLocation.pathname === base)?.[1] ?? (manager ? "Minha equipe" : "Visão geral")}</strong>
          </nav>
          <div className="topbar-actions">
            <button className="search-trigger" onClick={() => setSearch(true)}>
              <Search size={17} />
              <span>Buscar</span>
              <kbd>Ctrl K</kbd>
            </button>
            <button
              className="icon-button"
              aria-label={dark ? "Ativar tema claro" : "Ativar tema escuro"}
              onClick={() => setDark(!dark)}
            >
              {dark ? <Sun size={18} /> : <Moon size={18} />}
            </button>
            <button
              className="icon-button notification-trigger"
              aria-label="Notificações"
              onClick={() => setNotifications(true)}
            >
              <Bell size={19} />
              {Boolean(notices.data?.unread) && (
                <span className="notification-count">
                  {notices.data?.unread}
                </span>
              )}
            </button>
            <div className="user-chip">
              <span className="avatar">
                {session.data?.user.name.slice(0, 1)}
              </span>
              <span>{session.data?.user.name.split(" ")[0]}</span>
            </div>
            <button
              className="icon-button"
              aria-label="Sair"
              disabled={pendingAction === "logout"}
              onClick={async () => {
                setPendingAction("logout");
                setActionError(undefined);
                try {
                  await post("/auth/logout");
                  setToken("");
                  client.clear();
                  navigate(candidate ? "/entrar" : manager ? "/entrar-gestor" : "/entrar-rh");
                } catch (error) {
                  setActionError(error);
                } finally {
                  setPendingAction("");
                }
              }}
            >
              <LogOut size={18} />
            </button>
          </div>
        </header>
        <main id="main-content" className="main-content">
          <ErrorBox error={actionError} />
          {guideAllowed && currentLocation.pathname !== "/app/vagas" && <RHGuideContext onOpen={openGuide} />}
          {candidate ? <CandidateConsentPrompt key={session.data?.user.id}><Outlet /></CandidateConsentPrompt> : <Outlet />}
        </main>
        <footer className="app-footer">
          Porto Aurora Talentos<span>Porto Aurora</span>
        </footer>
      </div>
      {guideAllowed && session.data && <RHProcessGuide key={`${guideUser}:${guideStep}:${guideOpen}`} open={guideOpen} onOpenChange={changeGuide} initialStep={guideStep} session={session.data} />}
      <Modal
        open={notifications}
        onOpenChange={setNotifications}
        title="Notificações"
      >
        <div className="notification-list">
          <ErrorBox error={actionError ?? notices.error} />
          {notices.data?.items.length ? (
            notices.data.items.map((n) => (
              <article key={n.id}>
                <h3>{str(n.title)}</h3>
                <p>{str(n.body)}</p>
                <div className="notification-actions">
                {safeReturnPath(str(n.link)) && <Link className="button small" to={safeReturnPath(str(n.link))!} onClick={() => setNotifications(false)}>Abrir <ArrowUpRight size={16} aria-hidden="true" /></Link>}
                {n.status === "READ" ? <span className="notification-read-status" role="status"><Check size={16} aria-hidden="true" /> Lida</span> : <button
                  className="button secondary small notification-mark-read"
                  aria-busy={pendingAction === n.id}
                  disabled={pendingAction === n.id}
                  onClick={async () => {
                    setPendingAction(n.id);
                    setActionError(undefined);
                    try {
                      await api("/notifications/" + n.id, {
                        method: "PUT",
                        body: JSON.stringify({ status: "READ" }),
                      });
                      await client.invalidateQueries({queryKey: ["notifications"]});
                    } catch (error) {
                      setActionError(error);
                    } finally {
                      setPendingAction("");
                    }
                  }}
                >
                  <Check size={16} aria-hidden="true" />
                  {pendingAction === n.id ? "Marcando…" : "Marcar como lida"}
                </button>}
                </div>
              </article>
            ))
          ) : (
            <p>Nenhuma notificação.</p>
          )}
        </div>
      </Modal>
      <Modal open={search} onOpenChange={setSearch} title="Ir para">
        <label className="search-field">
          <Search size={18} />
          <input
            autoFocus
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Busque páginas, vagas ou candidatos"
          />
        </label>
        <nav className="command-results">
          {nav
            .filter(([, name]) =>
              name.toLocaleLowerCase().includes(q.toLocaleLowerCase()),
            )
            .map(([path, name, Icon]) => (
              <Link
                key={path}
                to={base + (path ? "/" + path : "")}
                onClick={() => setSearch(false)}
              >
                <Icon size={18} />
                {name}
              </Link>
            ))}
          {results.data?.items.map((row) => (
            <Link
              key={row.id}
              to={str(row.link)}
              onClick={() => setSearch(false)}
            >
              <Search size={18} />
              {str(row.type)} · {str(row.name)}
            </Link>
          ))}
        </nav>
      </Modal>
    </div>
  );
}
