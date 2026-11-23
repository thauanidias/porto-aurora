import { str, type Row } from "../lib/api";

function answerText(value: unknown): string {
  if (value == null || value === "" || Array.isArray(value) && !value.length) return "Não respondida";
  if (typeof value === "boolean") return value ? "Sim" : "Não";
  if (Array.isArray(value)) return value.map(answerText).join(" · ");
  return typeof value === "object" ? JSON.stringify(value) : String(value);
}

export function RHQuestionAnswers({ questions, answers }: { questions: Row[]; answers: Record<string, unknown> }) {
  const entries = questions.length ? questions.map(question => ({ key: str(question.key), title: str(question.label), value: answers[str(question.key)] }))
    : Object.entries(answers).map(([key, value]) => ({ key, title: key.replace(/[_-]+/g, " "), value }));
  if (!Object.keys(answers).length) return null;
  return <ol className="rh-answer-list" aria-label="Respostas às perguntas da vaga">{entries.map((entry, index) => <li key={entry.key}>
    <span className="rh-answer-number" aria-hidden="true">{index + 1}</span><div><h4>{entry.title}</h4><p>{answerText(entry.value)}</p></div>
  </li>)}</ol>;
}
