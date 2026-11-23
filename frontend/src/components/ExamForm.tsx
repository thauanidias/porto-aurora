import { useEffect, useRef, useState, type FormEvent } from "react";
import { api, post, put, obj, rows, str, type Row } from "../lib/api";
import { ErrorBox } from "./ui";

function answersFrom(form: HTMLFormElement, questions: Row[]) {
  const data = new FormData(form);
  const answers: Record<string, unknown> = {};
  for (const question of questions) {
    const key = str(question.key),
      value = data.get(key);
    answers[key] =
      question.kind === "MULTIPLE"
        ? data.getAll(key)
        : value == null || value === ""
          ? null
          : question.kind === "BOOLEAN"
            ? value === "true"
            : question.kind === "NUMBER"
              ? Number(value)
              : value;
  }
  return answers;
}
export function ExamForm({
  attempt,
  onDone,
}: {
  attempt: Row;
  onDone: () => Promise<unknown>;
}) {
  const ref = useRef<HTMLFormElement>(null);
  const version = useRef(attempt.version);
  const working = useRef(false);
  const finished = useRef(false);
  const [error, setError] = useState<unknown>();
  const [remaining, setRemaining] = useState(() =>
    Math.max(
      0,
      Math.ceil(
        (new Date(str(attempt.deadline)).valueOf() - Date.now()) / 1000,
      ),
    ),
  );
  const [saved, setSaved] = useState("");
  const questions = rows(attempt.questions);
  const initial = obj(attempt.answers);
  async function send(submit: boolean) {
    if (!ref.current || working.current || finished.current) return;
    working.current = true;
    const values = answersFrom(ref.current, questions);
    try {
      if (submit) {
        await post("/test-attempts/" + attempt.id + "/submit", {
          answers: values,
          version: version.current,
        });
        finished.current = true;
        await onDone();
      } else {
        const result = await put<{ version: number }>(
          "/test-attempts/" + attempt.id + "/answers",
          { answers: values, version: version.current },
        );
        version.current = result.version;
        setSaved(
          "Respostas salvas às " + new Date().toLocaleTimeString("pt-BR"),
        );
      }
      setError(undefined);
    } catch (e) {
      setError(e);
    } finally {
      working.current = false;
    }
  }
  const action = useRef(send);
  useEffect(() => {
    action.current = send;
  });
  useEffect(() => {
    let ticks = 0;
    const timer = setInterval(() => {
      const seconds = Math.max(
        0,
        Math.ceil(
          (new Date(str(attempt.deadline)).valueOf() - Date.now()) / 1000,
        ),
      );
      setRemaining(seconds);
      ticks++;
      if (seconds === 0) void action.current(true);
      else if (ticks % 10 === 0) void action.current(false);
    }, 1000);
    return () => clearInterval(timer);
  }, [attempt.deadline]);
  return (
    <>
      <div className="exam-clock" role="timer">
        Tempo restante: {Math.floor(remaining / 60)}:
        {String(remaining % 60).padStart(2, "0")}
      </div>
      <p className="muted" role="status">
        {saved || "Suas respostas são salvas a cada 10 segundos."}
      </p>
      <ErrorBox error={error} />
      <form
        ref={ref}
        onSubmit={(e: FormEvent) => {
          e.preventDefault();
          void send(true);
        }}
      >
        {questions.map((q, i) => (
          <fieldset className="exam-question" key={str(q.key)}>
            <legend>
              {i + 1}. {str(q.text)}
            </legend>
            {["SINGLE", "MULTIPLE"].includes(str(q.kind)) ? (
              (q.options as string[]).map((option) => (
                <label className="check-field" key={option}>
                  <input
                    type={q.kind === "SINGLE" ? "radio" : "checkbox"}
                    name={str(q.key)}
                    value={option}
                    defaultChecked={
                      initial[str(q.key)] === option ||
                      (Array.isArray(initial[str(q.key)]) &&
                        (initial[str(q.key)] as string[]).includes(option))
                    }
                  />
                  <span>{option}</span>
                </label>
              ))
            ) : q.kind === "BOOLEAN" ? (
              <select name={str(q.key)} defaultValue={str(initial[str(q.key)])}>
                <option value="">Selecione</option>
                <option value="true">Verdadeiro</option>
                <option value="false">Falso</option>
              </select>
            ) : q.kind === "NUMBER" ? (
              <input
                type="number"
                step="any"
                name={str(q.key)}
                defaultValue={str(initial[str(q.key)])}
              />
            ) : q.kind === "UPLOAD" ? (
              <TestFile name={str(q.key)} initial={str(initial[str(q.key)])} />
            ) : (
              <textarea
                name={str(q.key)}
                rows={5}
                defaultValue={str(initial[str(q.key)])}
              />
            )}
          </fieldset>
        ))}
        <div className="actions">
          <button className="button" disabled={remaining === 0}>
            Concluir e enviar respostas
          </button>
          <button
            type="button"
            className="button secondary"
            onClick={() => void send(false)}
            disabled={remaining === 0}
          >
            Salvar respostas
          </button>
        </div>
        {remaining === 0 && (
          <p role="status">
            O tempo terminou. Finalizando com as respostas registradas.
          </p>
        )}
      </form>
    </>
  );
}
function TestFile({ name, initial }: { name: string; initial: string }) {
  const [id, setId] = useState(initial);
  const [error, setError] = useState<unknown>();
  return (
    <>
      <input type="hidden" name={name} value={id} />
      <input
        type="file"
        accept=".pdf,.docx"
        onChange={async (e) => {
          const file = e.target.files?.[0];
          if (!file) return;
          const data = new FormData();
          data.set("file", file);
          data.set("type_name", "TEST_RESPONSE");
          try {
            const result = await api<Row>("/documents", {
              method: "POST",
              body: data,
            });
            setId(result.id);
          } catch (err) {
            setError(err);
          }
        }}
      />
      {id && <p>Arquivo recebido.</p>}
      <ErrorBox error={error} />
    </>
  );
}
