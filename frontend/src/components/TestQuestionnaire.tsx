import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Plus, Trash2 } from "lucide-react";
import { obj, put, str, type Row } from "../lib/api";
import { useTestQuestionnaires } from "../lib/useTestQuestionnaires";
import { ErrorBox } from "./ui";

type Question = { key: string; text: string; required: boolean };
export function TestQuestionnaireEditor({ row, onSubmit }: { row: Row; onSubmit: (data: Record<string, unknown>) => Promise<void> }) {
  const current = obj(row.test_questionnaire);
  const [questions, setQuestions] = useState<Question[]>(() => Array.isArray(current.questions) && current.questions.length
    ? current.questions as Question[] : ["Conte sobre sua experiência relacionada à vaga.", "Quais conhecimentos você considera mais relevantes para esta função?", "Qual é sua disponibilidade para iniciar?"]
      .map(text => ({ key: crypto.randomUUID(), text, required: true })));
  const [error, setError] = useState<unknown>();
  const [busy, setBusy] = useState(false);
  return <form onSubmit={async event => {
    event.preventDefault();
    if (busy) return;
    const content = questions.map(q => ({ ...q, text: q.text.trim() }));
    if (content.some(q => q.text.length < 3)) { setError(new Error("Escreva cada pergunta com pelo menos 3 caracteres.")); return; }
    setBusy(true); setError(undefined);
    try { await onSubmit({ version: row.version, questions: content }); }
    catch (cause) { setError(cause); } finally { setBusy(false); }
  }}>
    <p className="muted">Personalize até 10 perguntas para este candidato. As respostas serão em texto e aparecerão aqui para o RH.</p>
    <ErrorBox error={error} />
    <fieldset disabled={busy} className="test-questionnaire-fields">
      {questions.map((question, index) => <div className="test-question-editor" key={question.key}>
        <label className="field"><span>Pergunta {index + 1}</span><textarea aria-label={`Pergunta ${index + 1}`} required minLength={3} maxLength={500} rows={2} value={question.text}
          onChange={event => setQuestions(items => items.map(q => q.key === question.key ? { ...q, text: event.target.value } : q))} /></label>
        <div className="test-question-options"><label className="check-field"><input type="checkbox" checked={question.required}
          onChange={event => setQuestions(items => items.map(q => q.key === question.key ? { ...q, required: event.target.checked } : q))} />Resposta obrigatória</label>
          <button className="icon-button" type="button" disabled={questions.length === 1} aria-label={`Remover pergunta ${index + 1}`}
            onClick={() => setQuestions(items => items.filter(q => q.key !== question.key))}><Trash2 size={16} /></button></div>
      </div>)}
      <button className="button secondary small" type="button" disabled={questions.length >= 10}
        onClick={() => setQuestions(items => [...items, { key: crypto.randomUUID(), text: "", required: true }])}><Plus size={16} />Adicionar pergunta</button>
      {current.submitted_at != null && <p className="alert">Ao alterar as perguntas, o candidato deverá responder à nova versão. As respostas anteriores ficam preservadas.</p>}
      <button className="button" type="submit">{busy ? "Salvando…" : "Salvar questionário"}</button>
    </fieldset>
  </form>;
}

export function QuestionnairePreview({ value }: { value: unknown }) {
  const data = obj(value);
  const questions = Array.isArray(data.questions) ? data.questions as Question[] : [];
  const answered = Array.isArray(data.answered_questions) ? data.answered_questions as Question[] : [];
  if (!questions.length) return <p className="muted">Nenhum questionário preparado.</p>;
  return <details className="test-questionnaire-preview"><summary>{questions.length} {questions.length === 1 ? "pergunta" : "perguntas"} · {data.submitted_at ? data.answered_revision === data.revision ? "Respondido" : "Aguardando novas respostas" : "Aguardando respostas"}</summary>
    <ol>{questions.map(question => <li key={question.key}>{question.text}{question.required && <small> · Obrigatória</small>}</li>)}</ol>
    {data.submitted_at != null && <div className="test-questionnaire-responses"><strong>Respostas do candidato{data.answered_revision !== data.revision ? " · versão anterior" : ""}</strong>
      {answered.map(question => <div key={question.key}><p><strong>{question.text}</strong></p><p className="preserve">{str(obj(data.answers)[question.key]) || "Não respondida"}</p></div>)}</div>}
  </details>;
}

function AnswerForm({ row }: { row: Row }) {
  const data = obj(row.questionnaire);
  const questions = data.questions as Question[];
  const [answers, setAnswers] = useState<Record<string, string>>(() => obj(data.answers) as Record<string, string>);
  const [error, setError] = useState<unknown>();
  const [busy, setBusy] = useState(false);
  const client = useQueryClient();
  return <section className="surface padded"><h2>Questionário · {str(row.vacancy_title)}</h2>
    <p className="muted">{data.submitted_at ? data.answered_revision === data.revision ? "Respostas enviadas. Você pode atualizá-las abaixo." : "O RH alterou as perguntas. Confira e envie suas respostas novamente." : "Responda às perguntas disponibilizadas pelo RH para esta candidatura."}</p>
    <ErrorBox error={error} />
    <form onSubmit={async event => {
      event.preventDefault(); if (busy) return;
      const filtered = Object.fromEntries(questions.map(q => [q.key, (answers[q.key] ?? "").trim()]));
      if (questions.some(q => q.required && !filtered[q.key])) { setError(new Error("Preencha todas as respostas obrigatórias.")); return; }
      setBusy(true); setError(undefined);
      try { await put("/applications/" + row.id + "/test-questionnaire/answers", { version: row.version, revision: data.revision, answers: filtered });
        await client.invalidateQueries({ queryKey: ["my-test-questionnaires"] }); }
      catch (cause) { setError(cause); } finally { setBusy(false); }
    }}><fieldset disabled={busy} className="test-questionnaire-fields">
      {questions.map((question, index) => <label className="field" key={question.key}><span>{index + 1}. {question.text}{question.required ? " (obrigatória)" : " (opcional)"}</span>
        <textarea aria-label={question.text} rows={3} required={question.required} maxLength={5000} value={answers[question.key] ?? ""}
          onChange={event => setAnswers(current => ({ ...current, [question.key]: event.target.value }))} /></label>)}
      <button className="button" type="submit">{busy ? "Enviando…" : "Enviar respostas"}</button>
    </fieldset></form>
  </section>;
}

export function CandidateTestQuestionnaires() {
  const query = useTestQuestionnaires();
  return <><ErrorBox error={query.error} />{query.isPending && <p role="status">Carregando questionários…</p>}
    {query.data?.items.map(row => <AnswerForm key={row.id + ":" + row.version} row={row} />)}</>;
}
