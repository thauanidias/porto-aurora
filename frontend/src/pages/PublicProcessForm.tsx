import { useState } from "react";
import { ArrowLeft } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { post, obj, rows, str, type Row } from "../lib/api";
import { PublicHeader } from "./Careers";
import { SchemaForm, type Schema } from "../components/SchemaForm";
import { ErrorBox } from "../components/ui";
import { withFormChoices } from "../lib/formChoices";

export function PublicProcessForm() {
  const [token] = useState(() => new URLSearchParams(location.hash.slice(1)).get("token") ?? "");
  const [registrationReleased, setRegistrationReleased] = useState(false);
  const [completed, setCompleted] = useState(false);
  const [draft, setDraft] = useState(false);
  const query = useQuery({ queryKey: ["public-process-form", token], queryFn: () => post<Row>("/public/process-forms/lookup", { token }), enabled: Boolean(token), retry: false });
  const questions = rows(query.data?.questions);
  const properties = Object.fromEntries(questions.map(question => [str(question.key), {
    title: str(question.label), type: question.kind === "BOOLEAN" ? "boolean" : question.kind === "NUMBER" ? "number" : question.kind === "MULTIPLE" ? "array" : "string",
    ...(question.kind === "SINGLE" ? { enum: question.options as string[] } : {}),
    ...(question.kind === "MULTIPLE" ? { items: { type: "string", enum: question.options as string[] } } : {}),
    ...(question.kind === "TEXT" ? { maxLength: 10000 } : {}),
    ...(question.kind === "BOOLEAN" ? { booleanChoice: true, default: null } : {}),
    ...(question.kind === "SINGLE" ? { default: "" } : {}),
  } satisfies Schema]));
  const schema: Schema = { type: "object", properties: {
    answers: { type: "object", title: "Perguntas desta vaga", properties, required: questions.filter(q => q.required === true).map(q => str(q.key)) },
    consent: { type: "boolean", title: "Li o aviso de privacidade e concordo com o tratamento dos dados para este processo" },
    submit: { type: "boolean", title: "Concluir envio (desmarque para salvar como pendente)", default: true },
  }, required: ["consent"] };
  return <><PublicHeader /><main className="narrow-page process-public-form">
    <p className="privacy-eyebrow">RECRUTAMENTO E SELEÇÃO Porto Aurora</p><h1>Perguntas do RH</h1>
    {!token && <p className="alert">Abra o link exclusivo da sua candidatura para responder às perguntas do RH.</p>}<ErrorBox error={query.error} />
    {query.isPending && token && <p role="status">Validando seu link…</p>}
    {completed ? <section className="surface padded"><h2>Respostas recebidas!</h2><p>Suas respostas foram vinculadas à oportunidade. {registrationReleased ? "A ficha externa já está liberada. Preencha e assine para concluir esta etapa." : "Aguarde o retorno do RH."}</p><div className="actions"><a className="button secondary" href="/candidato"><ArrowLeft size={18} aria-hidden="true" />Voltar ao acompanhamento</a>{registrationReleased && <a className="button" href="/candidato/perfil#ficha-externa">Preencher ficha externa</a>}</div></section> : query.data && <>
      <h2>{str(query.data.vacancy_title)}</h2><p>Responda somente às perguntas preparadas pelo RH para esta vaga. Seus dados pessoais e profissionais continuam no perfil e na ficha de inscrição.</p>
      <details className="surface padded"><summary>Aviso de privacidade</summary><p className="process-notice">{str(query.data.notice)}</p></details>
      {draft && <p className="alert success" role="status">Ficha salva como pendente. Revise os dados e conclua o envio nesta página.</p>}
      <section className="surface padded">{questions.length ? <SchemaForm schema={withFormChoices(schema)} searchableSelects submitLabel="Enviar respostas ao RH" initial={{ submit: true, consent: false }} onSubmit={async data => {
        if (data.submit !== false) {
          const missing = questions.find(question => question.required === true && (obj(data.answers)[str(question.key)] == null || obj(data.answers)[str(question.key)] === "" || Array.isArray(obj(data.answers)[str(question.key)]) && !(obj(data.answers)[str(question.key)] as unknown[]).length));
          if (missing) throw new Error("Responda: " + str(missing.label));
        }
        const result = await post<Row>("/public/process-forms/submit", { ...data, token });
        if (result.status === "COMPLETED") { setRegistrationReleased(result.registration_released === true); setCompleted(true); } else setDraft(true);
      }} /> : <p>O RH ainda não definiu perguntas para esta vaga. Acompanhe sua candidatura.</p>}</section>
    </>}
  </main></>;
}
