import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api, put } from "../lib/api";
import { SchemaForm, type Schema } from "./SchemaForm";
import { ErrorBox } from "./ui";

export type ResumePersonalRecord = {data: Record<string, unknown>; version: number};
export function ResumePersonalFields({suggestions, onValuesChange}: {
  suggestions?: Record<string, unknown>;
  onValuesChange: (data: Record<string, unknown>) => void;
}) {
  const client = useQueryClient();
  const query = useQuery({queryKey: ["resume-personal"], queryFn: () => api<ResumePersonalRecord>("/candidates/me/resume-personal"), staleTime: Infinity, refetchOnWindowFocus: false});
  const schema = useQuery({queryKey: ["resume-personal-schema"], queryFn: () => api<Schema>("/candidates/me/resume-personal/schema")});
  return <section className="surface padded" id="dados-do-curriculo">
    <h2>Dados pessoais do currículo</h2>
    <p>Confira CPF, nascimento, endereço e contato, quando constarem no documento. O e-mail abaixo não altera seu acesso ao sistema. Estes dados têm acesso restrito e não entram no cálculo de compatibilidade.</p>
    <ErrorBox error={query.error ?? schema.error} />
    {query.isPending || schema.isPending ? <p role="status">Carregando dados pessoais…</p> : query.data && schema.data && <SchemaForm schema={schema.data} initial={query.data.data}
      suggestions={suggestions} onValuesChange={onValuesChange} submitLabel="Confirmar e salvar dados pessoais"
      onSubmit={async data => {
        const saved = await put<ResumePersonalRecord>("/candidates/me/resume-personal", {data, version: query.data.version});
        client.setQueryData(["resume-personal"], saved);
      }} />}
  </section>;
}
