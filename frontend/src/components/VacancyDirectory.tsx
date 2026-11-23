import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { ArrowRight, Building2, CircleX, MapPin, Search, Users } from "lucide-react";
import { api, post, str, type Collection, type Row } from "../lib/api";
import { label } from "../lib/labels";
import { Badge, Empty, ErrorBox, Modal } from "./ui";

import { useSession } from "../lib/session";
import { SchemaForm } from "./SchemaForm";

export function VacancyDirectory({ manager = false }: { manager?: boolean }) {
  const session = useSession();
  const client = useQueryClient();
  const [closing, setClosing] = useState<Row | null>(null);
  const canClose = !manager && Boolean(session.data?.permissions.includes("vacancy.edit"));
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("");
  const [audience, setAudience] = useState("");
  const [page, setPage] = useState(1);
  const query = useQuery({ queryKey: ["vacancy-directory", search, status, audience, page], queryFn: () => api<Collection>("/vacancies?" + new URLSearchParams({ q: search, status, audience, page_number: String(page) })) });
  return <section className="surface vacancy-board vacancy-directory-v2">
    <div className="vacancy-directory-quick" role="group" aria-label="Atalhos por situação">{[["", "Todas"], ["PUBLISHED", "Publicadas"], ["DRAFT", "Em preparação"], ["PAUSED", "Pausadas"], ["CLOSED", "Encerradas"], ["CANCELED", "Canceladas"]].map(([value, title]) => <button key={value} aria-pressed={status === value} className={status === value ? "active" : ""} onClick={() => { setStatus(value); setPage(1); }}>{title}</button>)}</div>
    <div className="vacancy-board-filters"><label className="message-search"><Search size={18} aria-hidden="true" /><input aria-label="Buscar vagas" type="search" placeholder="Buscar por cargo ou código da vaga" value={search} onChange={e => { setSearch(e.target.value); setPage(1); }} /></label><label className="task-filter">Público<select value={audience} onChange={e => { setAudience(e.target.value); setPage(1); }}><option value="">Todos os públicos</option><option value="INTERNAL">Interno</option><option value="EXTERNAL">Externo</option><option value="BOTH">Interno e externo</option></select></label></div>
    {(search || status || audience) && <div className="vacancy-directory-filter-summary"><span>{search ? `Busca por “${search}”` : "Filtros aplicados"}{status ? ` · ${label(status)}` : ""}{audience ? ` · Público ${label(audience).toLocaleLowerCase("pt-BR")}` : ""}</span><button className="text-button" onClick={() => { setSearch(""); setStatus(""); setAudience(""); setPage(1); }}>Limpar filtros</button></div>}
    <ErrorBox error={query.error} />
    {query.isPending ? <p className="loading" role="status">Carregando vagas…</p> : query.isError ? <button className="button secondary" onClick={() => void query.refetch()}>Tentar novamente</button> : !query.data?.items.length ? <Empty title="Nenhuma vaga encontrada">Ajuste a busca ou os filtros para consultar outras oportunidades.</Empty> : <><div className="vacancy-board-count" role="status">{query.data.total} {query.data.total === 1 ? "vaga encontrada" : "vagas encontradas"}</div><ul className="vacancy-board-list">{query.data.items.map(vacancy => <li key={vacancy.id} data-status={str(vacancy.status)}>
      <div className="vacancy-board-tags"><Badge value={vacancy.status} /><span className="vacancy-audience">Público {label(str(vacancy.audience)).toLocaleLowerCase("pt-BR")}</span></div>
      <div className="vacancy-board-identity"><Link to={(manager ? "/gestor/" : "/app/") + "vagas/" + vacancy.id}>{str(vacancy.title)}</Link><div className="vacancy-board-meta vacancy-facts"><div><MapPin size={18} aria-hidden="true" /><span><small>Local de trabalho</small><strong>{[vacancy.city, vacancy.state].filter(Boolean).join(" / ") || "Local a definir"}</strong></span></div><div><Users size={18} aria-hidden="true" /><span><small>Vagas disponíveis</small><strong>{str(vacancy.quantity)} {Number(vacancy.quantity) === 1 ? "posição" : "posições"}</strong></span></div>{Boolean(vacancy.modality) && <div><Building2 size={18} aria-hidden="true" /><span><small>Modalidade</small><strong>{label(str(vacancy.modality))}</strong></span></div>}</div><span className="vacancy-board-code">Código da vaga <strong>{str(vacancy.code)}</strong></span></div>
      <div className="actions vacancy-card-actions"><Link className="button small vacancy-follow-button" to={(manager ? "/gestor/" : "/app/") + "vagas/" + vacancy.id} aria-label={"Acompanhar seleção de " + str(vacancy.title)}>Acompanhar seleção <ArrowRight size={16} aria-hidden="true" /></Link>
      {canClose && ["PUBLISHED", "PAUSED"].includes(str(vacancy.status)) && <button className="button secondary small vacancy-close-button" aria-label={"Encerrar vaga " + str(vacancy.title)} onClick={() => setClosing(vacancy)}><CircleX size={16} aria-hidden="true" />Encerrar vaga</button>}</div>
    </li>)}</ul></>}
    {query.data && query.data.total > 0 && <footer className="task-footer"><span>Exibindo {((page - 1) * 25) + 1}–{Math.min(page * 25, query.data.total)} de {query.data.total} vagas</span>{query.data.total > 25 && <div className="pagination"><button className="button secondary small" disabled={page === 1} onClick={() => setPage(page - 1)}>Anterior</button><span>Página {page}</span><button className="button secondary small" disabled={page * 25 >= query.data.total} onClick={() => setPage(page + 1)}>Próxima</button></div>}</footer>}
    <Modal open={Boolean(closing)} onOpenChange={open => { if (!open) setClosing(null); }} title="Encerrar vaga">
      {closing && <>
        <p>Confirme o encerramento de <strong>{str(closing.title)}</strong> ({str(closing.code)}).</p>
        <p>A vaga deixará de receber inscrições. As candidaturas em andamento ou no banco de reserva serão encerradas como não selecionadas.</p>
        <SchemaForm key={closing.id} schema={{ type: "object", properties: { reason: { type: "string", title: "Motivo do encerramento", minLength: 5 } }, required: ["reason"] }} submitLabel="Confirmar encerramento" onSubmit={async data => {
          await post("/vacancies/" + closing.id + "/status", { status: "CLOSED", reason: data.reason, version: closing.version });
          setClosing(null);
          await client.invalidateQueries();
        }} />
      </>}
    </Modal>
  </section>;
}
