import { useEffect, type ReactNode } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { portal } from "../lib/portal";

export function PortalBoundary({ children }: { children: ReactNode }) {
  const { pathname, search, hash } = useLocation();
  const internal = portal.area === "RH" || portal.area === "GESTOR";
  const publicPage = /^\/(carreiras|privacidade|termo-consentimento|convite|ficha-selecao)(\/|$)/.test(pathname);
  useEffect(() => {
    if (internal && publicPage) window.location.replace(portal.publicUrl + pathname + search + hash);
  }, [internal, publicPage, pathname, search, hash]);
  if (internal && publicPage) return <main role="status">Abrindo portal de carreiras…</main>;
  if (portal.area === "LOCAL") return children;
  // Older notifications and shared detail components may still use the RH route.
  if (portal.area === "GESTOR" && /^\/app\/(vagas|candidatos|candidaturas|solicitacoes|mensagens)(\/|$)/.test(pathname)) {
    return <Navigate to={pathname.replace(/^\/app/, "/gestor") + search + hash} replace />;
  }
  const allowed = pathname === "/" || /^\/(confirmar|recuperar)(\/|$)/.test(pathname) || (
    portal.area === "CANDIDATO"
      ? !/^\/(app|gestor|entrar-rh|entrar-gestor|cadastro-gestor)(\/|$)/.test(pathname)
      : portal.area === "RH"
        ? /^\/(app|entrar-rh)(\/|$)/.test(pathname)
        : /^\/(gestor|entrar-gestor|cadastro-gestor)(\/|$)/.test(pathname)
  );
  return allowed ? children : <main className="narrow-page"><h1>Página não encontrada</h1></main>;
}
