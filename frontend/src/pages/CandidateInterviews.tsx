import { useQuery } from "@tanstack/react-query";
import { api, type Collection } from "../lib/api";
import { date } from "../lib/labels";
import { Empty, ErrorBox, PageTitle } from "../components/ui";
import { StageGate } from "../components/CandidateJourney";
import { CandidateActivityLinks } from "../components/CandidateActivityLinks";
import { useActivityLinks } from "../lib/activityLinks";

export function CandidateInterviews() {
  const links = useActivityLinks("INTERVIEW");
  const query = useQuery({
    queryKey: ["my-interviews"],
    queryFn: () => api<Collection>("/interviews/me"),
    refetchInterval: 15000,
  });
  return (
    <>
      <PageTitle title="Minhas entrevistas" subtitle="Quando você avançar para a etapa de entrevista em Minhas candidaturas, o RH informará aqui a data, o horário e o entrevistador." />
      <ErrorBox error={query.error} />
      <CandidateActivityLinks kind="INTERVIEW" />
      <StageGate section="interviews" title="Entrevistas">
      {query.isPending && <p role="status">Carregando entrevistas…</p>}
      {query.data?.items.map((row) => (
        <section className="surface padded" key={row.id}>
          <p><strong>Data e hora:</strong> {date(row.starts_at)}</p>
          <p><strong>Entrevistador:</strong> {Array.isArray(row.interviewers) && row.interviewers.length ? row.interviewers.join(", ") : "A confirmar pelo RH"}</p>
          {row.stage_unlocked === false && <p className="alert">Agendamento registrado. Aguarde a liberação da etapa desta candidatura.</p>}
        </section>
      ))}
      {!query.isPending && !query.error && !query.data?.items.length && !links.data?.items.length && (
        <Empty title="Aguardando agendamento do RH">
          Após seu avanço no processo seletivo, a data, o horário e o entrevistador aparecerão aqui assim que o RH agendar sua entrevista.
        </Empty>
      )}
      </StageGate>
    </>
  );
}
