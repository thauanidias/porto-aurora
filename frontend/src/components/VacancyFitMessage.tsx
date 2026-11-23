import { useState } from "react";
import { Link } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { post, str, type Row } from "../lib/api";
import { useSession } from "../lib/session";
import { CandidateCompatibility, compatibilityCategory, compatibilityReport } from "./CandidateCompatibility";
import { ErrorBox } from "./ui";

export function VacancyFitMessage({ application, compact = false }: { application: Row; compact?: boolean }) {
  const session = useSession();
  const client = useQueryClient();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>();
  const report = compatibilityReport(application);
  const canAnalyze = session.data?.permissions?.includes("score.manage");
  return <section className={"vacancy-fit-message fit-" + compatibilityCategory(application)} aria-label="Compatibilidade do perfil com esta vaga">
    <div className="section-heading"><div><p className="privacy-eyebrow">PERFIL × REQUISITOS DA VAGA</p><h2>Compatibilidade com {str(application.vacancy_title) || "esta vaga"}</h2></div></div>
    <CandidateCompatibility row={application} details={!compact} />
    <p className="muted">O percentual considera os critérios profissionais da vaga. A decisão de apto ou não apto continua com o RH.</p>
    <ErrorBox error={error} />
    <div className="actions">
      <Link className="text-button" to={`/app/candidaturas/${application.id}?aba=score`}>Ver requisitos e resultado</Link>
      {canAnalyze && report.status === "NOT_CONFIGURED" ? <Link className="text-button" to={`/app/vagas/${application.vacancy_id}?tab=scoring`}>Configurar critérios da vaga</Link> : canAnalyze && report.status !== "SEALED" && <button type="button" className="button secondary small" disabled={busy} onClick={async () => {
        if (busy) return;
        setBusy(true); setError(undefined);
        try {
          await post(`/applications/${application.id}/curriculum-analysis`);
          await Promise.all(["application", "candidate-processes", "vacancy-applications", "resume-screening", "rh-applications"].map(key => client.invalidateQueries({ queryKey: [key] })));
        } catch (err) { setError(err); } finally { setBusy(false); }
      }}>{busy ? "Analisando currículo…" : "Atualizar compatibilidade"}</button>}
    </div>
  </section>;
}
