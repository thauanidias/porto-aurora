import { Hand } from "lucide-react";
import { useSession } from "../lib/session";

export function RHWelcome() {
  const session = useSession();
  const parts = session.data?.user.name.trim().split(/\s+/).filter(Boolean) ?? [];
  const name = parts.length > 1 ? `${parts[0]} ${parts[parts.length - 1]}` : parts[0];
  return <section className="page-title rh-welcome" aria-labelledby="rh-welcome-title">
    <div className="page-title-copy">
      <span className="page-title-icon" aria-hidden="true"><Hand size={25} /></span>
      <h2 id="rh-welcome-title">{name ? `Olá, ${name}!` : "Olá!"}</h2>
      <p>Boas-vindas! Acompanhe suas vagas e os candidatos em cada etapa da seleção.</p>
    </div>
  </section>;
}
