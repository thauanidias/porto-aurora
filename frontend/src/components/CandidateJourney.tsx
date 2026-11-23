import { Link } from "react-router-dom";
import { LockKeyhole, CheckCircle2, ArrowRight, BriefcaseBusiness, UserRound, ClipboardList, CalendarDays, GraduationCap, FileCheck2 } from "lucide-react";
import type { ReactNode } from "react";
import { useCandidateJourney, phaseLabels, phaseRanks, type JourneySection } from "../lib/candidateJourney";
import { ErrorBox } from "./ui";
import { useSession } from "../lib/session";

export function StageGate({ section, title, children, id, allowed }: { section: JourneySection; title: string; children: ReactNode; id?: string; allowed?: boolean }) {
  const session = useSession();
  const internal = session.data?.user?.kind === "INTERNAL";
  const journey = useCandidateJourney(!internal);
  const enabled = internal || journey.isSuccess && journey.data.sections[section].enabled && !journey.error && allowed !== false;
  if (!enabled) return null;
  return <section id={id} className={"stage-gate" + (!enabled ? " is-locked" : "")} aria-label={title}>
    {!enabled && <div className="stage-gate-status locked" role="status">
      <LockKeyhole size={16} aria-hidden="true" />
      <strong>Bloqueado: {title}</strong>
      <span>{journey.isPending ? "Consultando sua etapa…" : "Disponível quando o RH liberar a etapa correspondente."}</span>
    </div>}
    {!internal && <ErrorBox error={journey.error} />}
    <fieldset disabled={!enabled} className="stage-gate-fields" aria-label={enabled ? title + " liberado" : title + " bloqueado"}>{children}</fieldset>
  </section>;
}

export function CandidateJourneyBanner() {
  const query = useCandidateJourney();
  const journey = query.data;
  const rank = phaseRanks[journey?.phase ?? "REGISTER"] ?? 0;
  const awaitingAdmission = rank >= 5 && !journey?.sections.admission.enabled;
  const phases = ["REGISTER", "RECRUITMENT", "SELECTION", "INTERVIEW", "TEST"];
  const current = journey?.processes.find(process => process.active && process.rank === rank);
  const available = query.isSuccess && !query.error;
  const icons = [UserRound, BriefcaseBusiness, ClipboardList, CalendarDays, GraduationCap];
  const PhaseIcon = rank >= 5 ? FileCheck2 : icons[rank] ?? UserRound;
  const descriptions = [
    "Complete seus dados básicos e escolha uma vaga para iniciar o recrutamento.",
    "Envie seu currículo e complete seu perfil profissional para a análise do RH.",
    journey?.phase === "FORM" ? "Preencha as perguntas e a ficha liberadas no acompanhamento da candidatura." : "Seu currículo está em análise. Aguarde a aprovação e o avanço pelo RH para acessar mensagens, ficha e perguntas.",
    "Confira os links, os horários e as orientações das entrevistas disponibilizadas pelo RH.",
    "Responda às perguntas das vagas, acesse os testes liberados e confira as instruções e os prazos.",
    "Confira a lista de documentos e envie os arquivos solicitados pelo RH.",
  ];
  const actionLabels = ["Escolher uma vaga", "Completar meu perfil", "Acompanhar candidatura", "Ver minhas entrevistas", "Ver meus testes", "Enviar documentos"];
  const nextPath = awaitingAdmission ? current ? "/candidato/candidaturas/" + current.id : "/candidato" : rank === 0 ? "/candidato/vagas" : rank === 1 ? "/candidato/perfil#curriculo"
    : rank === 2 ? "/candidato"
    : rank === 3 ? "/candidato/entrevistas" : rank === 4 ? "/candidato/testes" : "/candidato/documentos";
  return <section className="surface candidate-journey" aria-label="Sua jornada no processo seletivo" aria-live="polite">
    <div className="candidate-journey-topline"><p className="privacy-eyebrow">SUA JORNADA</p><span className="candidate-journey-position">{!available ? "Consultando etapa" : rank >= 5 ? "5 etapas liberadas" : "Etapa " + (rank + 1) + " de 5"}</span></div>
    <div className="candidate-journey-heading">
      <span className="candidate-journey-phase-icon" aria-hidden="true"><PhaseIcon size={25} strokeWidth={1.7} /></span>
      <div className="candidate-journey-summary">
        <h2>{!available ? query.isPending ? "Consultando sua jornada…" : "Sua etapa está indisponível" : awaitingAdmission ? "Aguardando liberação da admissão" : phaseLabels[journey?.phase ?? "REGISTER"]}</h2>
        {current && <p className="candidate-journey-vacancy"><BriefcaseBusiness size={14} aria-hidden="true" />{current.vacancy_title}</p>}
        <p className="candidate-journey-description">{!available ? "Aguarde a consulta para conferir as atividades disponíveis." : awaitingAdmission ? "O RH informará a decisão e a liberação dos documentos. Acompanhe sua candidatura." : descriptions[rank]}</p>
      </div>
      {available && <Link className="button candidate-journey-action" to={nextPath}>{awaitingAdmission ? "Acompanhar candidatura" : actionLabels[rank]}<ArrowRight size={17} aria-hidden="true" /></Link>}
    </div>
    <ErrorBox error={query.error} />
    <ol className="candidate-journey-timeline">{phases.map((phase, index) => <li key={phase} className={index > rank ? "locked" : index === rank ? "current" : "completed"} aria-current={index === rank ? "step" : undefined}>
      <span className="candidate-journey-step-icon" aria-hidden="true">{index > rank ? <LockKeyhole size={16} /> : index < rank ? <CheckCircle2 size={18} /> : index + 1}</span>
      <div className="candidate-journey-step-copy"><strong>{phaseLabels[phase]}</strong><small>{!available ? "Consultando…" : index > rank ? "Aguardando RH" : index === rank ? "Você está aqui" : "Liberado"}</small></div>
    </li>)}</ol>
    <p className="candidate-journey-hint"><LockKeyhole size={14} aria-hidden="true" />As próximas etapas serão liberadas pelo RH conforme seu avanço no processo.</p>
  </section>;
}
