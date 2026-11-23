import { PartyPopper, CheckCircle2 } from "lucide-react";
import { obj, str, type Row } from "../lib/api";

export function NewEmployeeWelcome({ application }: { application: Row }) {
  if (application.documents_welcome_ready !== true) return null;
  const name = str(obj(application.candidate).name).trim().split(/\s+/)[0];
  return <section className="new-employee-welcome" aria-label="Boas-vindas ao novo colaborador" role="status">
    <span className="new-employee-welcome-icon"><PartyPopper size={30} aria-hidden="true" /></span>
    <div><p className="privacy-eyebrow">UMA NOVA JORNADA COMEÇA</p><h2>Bem-vindo ao Porto Aurora{name ? `, ${name}` : ""}!</h2>
      <p>Que alegria ter você nesta nova etapa! Desejamos uma jornada de aprendizado, boas conexões e muitas conquistas com a nossa equipe.</p>
      <span className="new-employee-welcome-received"><CheckCircle2 size={17} aria-hidden="true" />Documentos enviados</span>
      <p className="muted">Acompanhe as mensagens do RH para conferir as orientações de entrada e os próximos passos.</p>
    </div>
  </section>;
}
