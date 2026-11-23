import { useState } from "react";
import { Link } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api, obj, put, rows, str, type Collection, type Row } from "../lib/api";
import { StageGate } from "./CandidateJourney";
import { SchemaForm, type Schema } from "./SchemaForm";
import { ErrorBox } from "./ui";

export function ApplicationQuestions({ application }: { application: Row }) {
  const client = useQueryClient();
  const [saved, setSaved] = useState(false);
  const allowed = obj(obj(application.candidate_access).permissions).questions === true;
  const questions = rows(application.selection_questions);
  const schema: Schema = { type: "object", properties: {
    answers: { type: "object", title: "Perguntas da vaga", required: questions.filter(q => q.required).map(q => str(q.key)), properties: Object.fromEntries(questions.map(q => [str(q.key), {
      title: str(q.label), ...(q.kind === "BOOLEAN" ? { type: "boolean" }
        : q.kind === "NUMBER" ? { type: "number" }
        : q.kind === "SINGLE" ? { type: "string", enum: q.options as string[] }
        : q.kind === "MULTIPLE" ? { type: "array", items: { type: "string", enum: q.options as string[] } }
        : { type: "string" }),
    }])) },
  } };
  return <article className="surface padded candidate-question-card">
    <h3>{str(application.vacancy_title)}</h3>
    <p className="muted">{str(application.stage_name)} · {allowed ? "Perguntas liberadas para esta candidatura." : "Aguarde o RH liberar a etapa de testes desta candidatura."}</p>
    <StageGate section="questions" title="Respostas às perguntas da vaga" allowed={allowed}>
      {saved && <p className="alert success" role="status">Respostas enviadas ao RH.</p>}
      <SchemaForm key={str(application.version)} schema={schema} initial={{ answers: obj(application.answers) }} submitLabel="Enviar respostas" onSubmit={async data => {
        const updated = await put<Row>("/applications/" + application.id + "/questions", { ...data, version: application.version });
        setSaved(true);
        client.setQueryData<Collection>(["candidate-questions"], current => current && { ...current, items: current.items.map(item => item.id === updated.id ? updated : item) });
        await client.invalidateQueries({ queryKey: ["candidate-questions"] });
        await client.invalidateQueries({ queryKey: ["application", application.id] });
        await client.invalidateQueries({ queryKey: ["my-applications"] });
      }} />
    </StageGate>
    <Link to={"/candidato/candidaturas/" + application.id}>Acompanhar candidatura</Link>
  </article>;
}

export function CandidateQuestions() {
  const query = useQuery({
    queryKey: ["candidate-questions"],
    queryFn: async () => {
      const collection = await api<Collection>("/applications?page_size=100");
      const items = [...collection.items];
      let page = 2;
      while (items.length < collection.total) {
        const next = await api<Collection>("/applications?page_size=100&page_number=" + page++);
        if (!next.items.length) break;
        items.push(...next.items);
      }
      return { ...collection, items };
    },
    refetchInterval: 15000,
  });
  const applications = query.data?.items.filter(application => rows(application.selection_questions).length) ?? [];
  return <section id="perguntas" className="candidate-questions" aria-label="Perguntas das vagas">
    <h2>Perguntas das vagas</h2>
    <p>Responda às perguntas de cada candidatura quando o RH liberar sua etapa de testes.</p>
    <ErrorBox error={query.error} />
    {query.isPending && <p role="status">Carregando perguntas…</p>}
    {query.isSuccess && !applications.length && <p className="surface padded muted">Suas candidaturas ainda não têm perguntas adicionais.</p>}
    {applications.map(application => <ApplicationQuestions key={application.id} application={application} />)}
  </section>;
}
