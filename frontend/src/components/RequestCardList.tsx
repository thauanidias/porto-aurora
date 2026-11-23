import type { ComponentProps } from "react";
import { ArrowRight, BriefcaseBusiness, Building2, CalendarDays, ChevronLeft, ChevronRight, MessageSquare, UserRound } from "lucide-react";
import { str } from "../lib/api";
import { date } from "../lib/labels";
import { Badge, DataTable, Empty } from "./ui";

export function RequestCardList({ data, total, page = 1, pageSize = 25, onPage, onOpen, actions }: ComponentProps<typeof DataTable>) {
  if (!data.length) return <Empty title="Nenhuma solicitação encontrada">Crie uma solicitação ou ajuste a busca pelo título.</Empty>;
  return <>
    <div className="request-list-caption"><span><strong>{total ?? data.length}</strong> {(total ?? data.length) === 1 ? "solicitação" : "solicitações"}</span><span>Mais recentes primeiro</span></div>
    <div className="request-cards">{data.map(row => <article key={row.id} className="request-card" aria-label={str(row.title)}>
      <div className="request-card-heading"><span className="request-card-icon"><BriefcaseBusiness size={22} aria-hidden="true" /></span><div><button className="request-title-link" onClick={() => onOpen?.(row)}>{str(row.title)}</button><div className="request-card-meta"><span><UserRound size={14} aria-hidden="true" />{str(row.requested_by_name)}</span><span><Building2 size={14} aria-hidden="true" />{str(row.org_unit_name)}</span><span className="request-card-quantity">{str(row.quantity)} {Number(row.quantity) === 1 ? "posição" : "posições"}</span></div></div><Badge value={row.status === "DRAFT" && row.last_decision === "REJECTED" ? "RETURNED" : row.status} /></div>
      <div className={row.rh_feedback ? "request-card-update has-feedback" : "request-card-update"}><MessageSquare size={17} aria-hidden="true" /><div><strong>{row.rh_feedback ? "Retorno do RH" : row.status === "PENDING_APPROVAL" ? "Aguardando análise do RH" : row.status === "APPROVED" ? "Solicitação aceita" : row.status === "CONVERTED" ? "Processo seletivo iniciado" : "Próximo passo"}</strong><p>{str(row.rh_feedback) || (row.status === "PENDING_APPROVAL" ? "O pedido foi recebido. Você será notificado quando houver uma decisão." : row.status === "APPROVED" ? "O RH já pode criar a vaga a partir deste pedido." : row.status === "CONVERTED" ? "A vaga foi criada. Acompanhe o andamento pelo seu painel." : "Abra os detalhes para conferir as informações desta solicitação.")}</p></div></div>
      <footer className="request-card-footer"><span className="request-card-date"><CalendarDays size={15} aria-hidden="true" />Criada em {date(row.created_at)}</span><div className="request-card-actions"><button className="button secondary small request-details-button" onClick={() => onOpen?.(row)}>Ver detalhes <ArrowRight size={15} aria-hidden="true" /></button>{actions?.(row)}</div></footer>
    </article>)}</div>
    {onPage && (total ?? 0) > pageSize && <div className="pagination"><button className="icon-button" disabled={page <= 1} onClick={() => onPage(page - 1)} aria-label="Página anterior"><ChevronLeft size={18} /></button><span>Página {page}</span><button className="icon-button" disabled={page * pageSize >= (total ?? 0)} onClick={() => onPage(page + 1)} aria-label="Próxima página"><ChevronRight size={18} /></button></div>}
  </>;
}
