import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, Trash2, ListChecks } from "lucide-react";
import { api, obj, put, rows, str, type Row } from "../lib/api";
import { useSession } from "../lib/session";
import { ErrorBox, Modal } from "./ui";

type Question = { key: string; label: string; kind: string; required: boolean; options: string[] };
export function VacancyQuestions({ vacancyId }: { vacancyId: string }) {
  const session = useSession();
  const [open, setOpen] = useState(false);
  const [saved, setSaved] = useState(false);
  const client = useQueryClient();
  const query = useQuery({ queryKey: ["vacancy-questions-config", vacancyId], queryFn: () => api<Row>(`/vacancies/${vacancyId}`), enabled: open, refetchOnWindowFocus: false });
  if (!session.data?.permissions.includes("vacancy.edit") || !vacancyId) return null;
  return <><button className="button secondary" onClick={() => { setSaved(false); setOpen(true); void query.refetch(); }}><ListChecks size={17} />Configurar perguntas</button>{saved && <small role="status">Perguntas salvas para esta vaga.</small>}
    <Modal open={open} onOpenChange={setOpen} title="Perguntas do RH para esta vaga"><ErrorBox error={query.error} />{query.isFetching ? <p role="status">Carregando perguntas…</p> : query.data && <QuestionEditor key={str(query.data.version)} vacancy={query.data} onSave={async questions => {
      await put(`/vacancies/${vacancyId}/questions`, { version: query.data!.version, questions });
      await Promise.all(["vacancy", "vacancy-questions-config", "process-form", "stage-task-status"].map(key => client.invalidateQueries({ queryKey: [key] })));
      setOpen(false); setSaved(true);
    }} />}</Modal></>;
}

function QuestionEditor({ vacancy, onSave }: { vacancy: Row; onSave: (questions: Question[]) => Promise<void> }) {
  const [questions, setQuestions] = useState<Question[]>(() => rows(obj(vacancy.details).questions).map(item => ({ key: str(item.key), label: str(item.label), kind: str(item.kind), required: item.required === true, options: Array.isArray(item.options) ? item.options.map(String) : [] })));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>();
  const update = (index: number, changes: Partial<Question>) => setQuestions(current => current.map((question, position) => position === index ? { ...question, ...changes } : question));
  return <form className="vacancy-question-editor" onSubmit={async event => { event.preventDefault(); setBusy(true); setError(undefined); try { await onSave(questions.map(question => ({ ...question, label: question.label.trim(), options: ["SINGLE", "MULTIPLE"].includes(question.kind) ? question.options.map(option => option.trim()).filter(Boolean) : [] }))); } catch (failure) { setError(failure); } finally { setBusy(false); } }}>
    <p>Crie até 20 perguntas curtas para esta vaga. Não é necessário repetir nome, contato, formação ou experiência já informados no perfil.</p><p className="muted">As alterações atualizam fichas ainda não iniciadas. Fichas já preenchidas mantêm as perguntas e as respostas da versão recebida.</p><ErrorBox error={error} />
    {questions.map((question, index) => <fieldset key={question.key} className="surface padded"><legend>Pergunta {index + 1}</legend><label className="field"><span>Pergunta</span><input aria-label={`Pergunta ${index + 1}`} required minLength={3} maxLength={500} value={question.label} onChange={event => update(index, { label: event.target.value })} placeholder="Ex.: Você tem disponibilidade para o turno da manhã?" /></label><label className="field"><span>Tipo de resposta</span><select aria-label={`Tipo da pergunta ${index + 1}`} value={question.kind} onChange={event => update(index, { kind: event.target.value })}><option value="TEXT">Resposta escrita</option><option value="BOOLEAN">Sim ou não</option><option value="NUMBER">Número</option><option value="SINGLE">Uma alternativa</option><option value="MULTIPLE">Várias alternativas</option></select></label>
      {["SINGLE", "MULTIPLE"].includes(question.kind) && <label className="field"><span>Alternativas — uma por linha</span><textarea required rows={4} value={question.options.join("\n")} onChange={event => update(index, { options: event.target.value.split("\n") })} placeholder={"Manhã\nTarde\nNoite"} /></label>}
      <div className="actions"><label className="check-field"><input type="checkbox" checked={question.required} onChange={event => update(index, { required: event.target.checked })} />Resposta obrigatória</label><button type="button" className="button secondary small" disabled={index === 0} onClick={() => setQuestions(current => { const next = [...current]; [next[index - 1], next[index]] = [next[index], next[index - 1]]; return next; })}>Mover para cima</button><button className="button secondary small" type="button" aria-label={`Excluir pergunta ${index + 1}`} onClick={() => setQuestions(current => current.filter((_, position) => position !== index))}><Trash2 size={15} />Excluir</button></div></fieldset>)}
    {!questions.length && <p>Nenhuma pergunta configurada. Adicione a primeira abaixo.</p>}
    <div className="actions"><button type="button" className="button secondary" disabled={questions.length >= 20 || busy} onClick={() => setQuestions(current => [...current, { key: "q_" + Date.now().toString(36) + "_" + Math.random().toString(36).slice(2, 10), label: "", kind: "TEXT", required: true, options: [] }])}><Plus size={17} />Adicionar pergunta</button><button className="button" disabled={busy}>{busy ? "Salvando…" : "Salvar perguntas"}</button></div>
  </form>;
}
