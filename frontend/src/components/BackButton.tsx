import { useEffect, useRef } from "react";
import { ArrowLeft } from "lucide-react";
import { useLocation, useNavigate, useNavigationType } from "react-router-dom";

export function BackButton({ base }: { base: string }) {
  const location = useLocation();
  const navigate = useNavigate();
  const action = useNavigationType();
  const visited = useRef<{ base: string; keys: string[] }>({ base, keys: [] });
  useEffect(() => {
    if (visited.current.base !== base) visited.current = { base, keys: [] };
    const keys = visited.current.keys;
    const index = keys.indexOf(location.key);
    if (index >= 0) keys.splice(index + 1);
    else if (action === "REPLACE" && keys.length) keys[keys.length - 1] = location.key;
    else keys.push(location.key);
  }, [base, location.key, action]);

  const home = base === "/gestor" ? "/gestor/vagas" : base;
  if (location.pathname === home || location.pathname === base) return null;
  return <button
    type="button"
    className="workspace-back"
    aria-label="Voltar à tela anterior"
    title="Voltar à tela anterior"
    onClick={() => {
      if (visited.current.keys.length > 1) {
        navigate(-1);
        return;
      }
      const parts = location.pathname.slice(base.length).split("/").filter(Boolean);
      const parent = parts.length > 1 && ["vagas", "candidatos"].includes(parts[0])
        ? base + "/" + parts[0] : home;
      navigate(parent, { replace: true });
    }}
  ><ArrowLeft size={19} aria-hidden="true" /><span>Voltar</span></button>;
}
