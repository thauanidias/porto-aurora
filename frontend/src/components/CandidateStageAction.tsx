import { useState } from "react";
import { Link } from "react-router-dom";
import { ArrowRight } from "lucide-react";
import { obj, post, str, type Row } from "../lib/api";
import { ErrorBox } from "./ui";

export function candidateStageDestination(application: Row) {
  if (application.documents_welcome_ready === true) return null;
  const access = obj(application.candidate_access);
  const permissions = obj(access.permissions);
  const phase = str(access.phase);
  if (phase === "FORM" && permissions.selection_registration === true && application.recruitment_type !== "INTERNAL")
    return { path: "/candidato/perfil#ficha-externa", label: "Preencher ficha externa", hint: "Perguntas concluídas. Acesse a ficha externa para preencher e assinar.", form: false };
  if (phase === "FORM" && permissions.process_form === true && application.process_form_status !== "COMPLETED")
    return { path: "", label: "Responder perguntas do RH", hint: "Responda às perguntas do RH para liberar a ficha externa.", form: true };
  const options: Record<string, { permission: string; path: string; label: string; hint: string }> = {
    REGISTER: { permission: "basic_profile", path: "/candidato/perfil", label: "Completar meu perfil", hint: "Clique na etapa para completar seus dados no perfil." },
    RECRUITMENT: { permission: "resume", path: "/candidato/perfil#curriculo", label: "Conferir meu currículo", hint: "Clique na etapa para conferir seu currículo e perfil profissional." },
    INTERVIEW: { permission: "interviews", path: "/candidato/entrevistas", label: "Ver minhas entrevistas", hint: "Clique na etapa para consultar horários, links e orientações da entrevista." },
    TEST: { permission: "tests", path: "/candidato/testes", label: "Acessar meus testes", hint: "Clique na etapa para acessar os testes liberados e seus prazos." },
    ADMISSION: { permission: "admission", path: "/candidato/documentos", label: "Enviar documentos", hint: "Clique na etapa para conferir e enviar os documentos solicitados pelo RH." },
  };
  const option = options[phase];
  return option && permissions[option.permission] === true ? { ...option, form: false } : null;
}

export function candidateStageHint(application: Row) {
  if (application.documents_welcome_ready === true) return "Documentos recebidos! Acompanhe as orientações do RH para seus próximos passos.";
  if (candidateStageDestination(application)) return candidateStageDestination(application)!.hint;
  if (application.process_form_status === "COMPLETED" && obj(application.candidate_access).phase === "FORM")
    return "Ficha enviada ao RH. Aguarde a análise e a liberação da próxima etapa.";
  return candidateStageDestination(application)?.hint ?? "Aguarde a análise do RH. As próximas atividades aparecerão quando forem liberadas.";
}

export function CandidateStageAction({ application, label, compact = false }: { application: Row; label?: string; compact?: boolean }) {
  const destination = candidateStageDestination(application);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>();
  if (!destination) return label ? <>{label}</> : null;
  const className = compact ? "text-button candidate-stage-link" : "button";
  const content = <>{label ?? destination.label}<ArrowRight size={compact ? 17 : 19} aria-hidden="true" /></>;
  return <>{destination.form ? <button type="button" className={className} disabled={busy} onClick={async () => {
    setBusy(true); setError(undefined);
    try {
      const result = await post<Row>(`/applications/${application.id}/my-process-form`, {});
      const target = new URL(str(result.link), window.location.origin);
      window.location.assign("/ficha-selecao" + target.hash);
    } catch (failure) { setError(failure); setBusy(false); }
  }}>{busy ? "Abrindo ficha…" : content}</button> : <Link className={className} to={destination.path}>{content}</Link>}<ErrorBox error={error} /></>;
}
