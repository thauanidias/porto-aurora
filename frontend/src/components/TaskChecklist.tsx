import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { CalendarDays, Check, CheckCheck, Circle, Search } from "lucide-react";
import { api, put, str, type Collection, type Row } from "../lib/api";
import { date, label } from "../lib/labels";
import { Empty, ErrorBox } from "./ui";

export function TaskChecklist({ onOpen }: { onOpen: (row: Row) => void }) {
  const [status, setStatus] = useState("");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [busy, setBusy] = useState("");
  const [now] = useState(() => Date.now());
  const [error, setError] = useState<unknown>();
  const client = useQueryClient();
  const query = useQuery({ queryKey: ["task-checklist", status, search, page], queryFn: () => api<Collection>(`/tasks?status=${status}&q=${encodeURIComponent(search)}&page_number=${page}`) });
  const open = useQuery({ queryKey: ["task-checklist", "count-open"], queryFn: () => api<Collection>("/tasks?status=OPEN") });
  const done = useQuery({ queryKey: ["task-checklist", "count-done"], queryFn: () => api<Collection>("/tasks?status=DONE") });
  const toggle = async (task: Row) => {
    if (busy) return;
    setBusy(task.id); setError(undefined);
    try {
      await put(`/tasks/${task.id}`, { status: task.status === "DONE" ? "OPEN" : "DONE", version: task.version });
      await client.invalidateQueries({ queryKey: ["task-checklist"] });
    } catch (err) { setError(err); } finally { setBusy(""); }
  };
  return <div className="task-checklist">
    <div className="task-summary"><div><Circle size={22} /><span>Pendentes<strong>{open.data?.total ?? "—"}</strong></span></div><div className="task-summary-done"><CheckCheck size={24} /><span>Concluídas<strong>{done.data?.total ?? "—"}</strong></span></div></div>
    <section className="surface task-panel">
      <header><h2>Checklist de tarefas</h2><p>Marque as tarefas finalizadas e acompanhe o que falta fazer.</p></header>
      <div className="task-tools"><label className="message-search"><Search size={18} aria-hidden="true" /><input type="search" aria-label="Buscar tarefas" placeholder="Buscar pelo título da tarefa" value={search} onChange={event => { setSearch(event.target.value); setPage(1); }} /></label><label className="task-filter">Situação<select value={status} onChange={event => { setStatus(event.target.value); setPage(1); }}><option value="">Todas</option><option value="OPEN">Pendentes</option><option value="DONE">Concluídas</option><option value="CANCELED">Canceladas</option></select></label></div>
      <ErrorBox error={error ?? query.error} />
      {query.isPending ? <p className="loading" role="status">Carregando tarefas…</p> : query.isError ? <button className="button secondary" onClick={() => void query.refetch()}>Tentar novamente</button> : !query.data?.items.length ? <Empty title="Nenhuma tarefa encontrada">Ajuste a busca ou crie uma nova tarefa.</Empty> : <ul className="task-items">{query.data.items.map(task => {
        const completed = task.status === "DONE";
        const canceled = task.status === "CANCELED";
        const overdue = task.status === "OPEN" && Boolean(task.due_at) && new Date(str(task.due_at)).getTime() < now;
        return <li key={task.id} className={completed ? "task-item completed" : "task-item"}>
          <label className="task-toggle"><input type="checkbox" checked={completed} disabled={Boolean(busy) || canceled} onChange={() => void toggle(task)} aria-label={`${completed ? "Reabrir" : "Concluir"} tarefa: ${str(task.title)}`} /><span aria-hidden="true">{completed && <Check size={19} />}</span></label>
          <div className="task-identity"><button className="text-button" onClick={() => onOpen(task)}>{str(task.title)}</button>{Boolean(task.description) && <p>{str(task.description)}</p>}<div className="task-meta"><span className={overdue ? "task-overdue" : ""}><CalendarDays size={14} />{date(task.due_at)}{overdue && " · Atrasada"}</span><span>Prioridade: {label(str(task.priority))}</span></div></div>
          <span className={`task-state ${completed ? "done" : canceled ? "canceled" : "pending"}`}>{completed ? "Concluída" : canceled ? "Cancelada" : "Pendente"}</span>
          <button className="button secondary small" onClick={() => onOpen(task)}>Detalhes</button>
        </li>;
      })}</ul>}
      {query.data && <footer className="task-footer"><span>{query.data.total} {query.data.total === 1 ? "tarefa" : "tarefas"}</span><div className="pagination"><button className="button secondary small" disabled={page === 1} onClick={() => setPage(page - 1)}>Anterior</button><span>Página {page}</span><button className="button secondary small" disabled={page * 25 >= query.data.total} onClick={() => setPage(page + 1)}>Próxima</button></div></footer>}
    </section>
  </div>;
}

