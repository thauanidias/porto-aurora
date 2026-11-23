import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { Settings, ShieldCheck, Users, FileSearch, ArrowLeft, ArrowRight, LockKeyhole } from "lucide-react";
import { useSession } from "../lib/session";
import { PageTitle } from "../components/ui";

const areas = [
  { path: "sistema", title: "Sistema e processos", description: "E-mails, integrações, etapas, modelos de vagas, documentos, comunicação e automações.", permission: "config.manage", icon: Settings },
  { path: "acessos", title: "Usuários e permissões", description: "Contas internas, funções e permissões de acesso à plataforma.", permission: "user.manage", icon: Users },
  { path: "privacidade", title: "Privacidade e dados", description: "Solicitações dos titulares e controles de proteção de dados.", permission: "privacy.manage", icon: ShieldCheck },
  { path: "auditoria", title: "Auditoria da plataforma", description: "Histórico de ações e alterações para acompanhamento administrativo.", permission: "audit.view", icon: FileSearch },
];

export function PlatformConfiguration() {
  const session = useSession();
  return <><PageTitle title="Configuração da plataforma" subtitle="Todos os ajustes administrativos do Porto Aurora Talentos em um só lugar." />
    <div className="platform-configuration-grid">{areas.map(area => {
      const allowed = Boolean(session.data?.permissions.includes(area.permission));
      const content = <><span className="rediscovery-heading-icon"><area.icon size={25} aria-hidden="true" /></span><div><h2>{area.title}</h2><p>{area.description}</p><span className="platform-configuration-open">{allowed ? <>Abrir configurações<ArrowRight size={16} /></> : <><LockKeyhole size={16} />Acesso administrativo necessário</>}</span></div></>;
      return allowed ? <Link className="surface platform-configuration-card" key={area.path} to={"/app/configuracao-plataforma/" + area.path}>{content}</Link> : <article className="surface platform-configuration-card is-restricted" key={area.path}>{content}</article>;
    })}</div>
    {!session.isPending && !areas.some(area => session.data?.permissions.includes(area.permission)) && <p className="muted platform-configuration-access-note">Seu perfil atual permite consultar esta central. A alteração de configurações depende da liberação das permissões administrativas por um responsável.</p>}

  </>;
}

export function ConfigurationSection({ children }: { children: ReactNode }) {
  return <><Link className="back-link" to="/app/configuracao-plataforma"><ArrowLeft size={16} />Voltar à configuração da plataforma</Link>{children}</>;
}
