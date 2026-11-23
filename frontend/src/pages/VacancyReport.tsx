import { useState } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { ArrowRight, BriefcaseBusiness, CalendarDays, Search, Download, UsersRound, UserCheck, BadgeCheck } from "lucide-react";
import { api, str, download, type Row, type Collection } from "../lib/api";
import { date, label } from "../lib/labels";
import { Badge, Empty, ErrorBox, PageTitle, Modal } from "../components/ui";

export function VacancyReport() {
  const [month, setMonth] = useState("");
  const [exportOpen, setExportOpen] = useState(false);
  const [exportVacancy, setExportVacancy] = useState<Row | null>(null);
  const [exportMonth, setExportMonth] = useState(new Date().toLocaleDateString("sv-SE", { timeZone: "America/Fortaleza" }).slice(0, 7));
  const [exporting, setExporting] = useState(false);
  const [exportError, setExportError] = useState<unknown>();
  const openExport = (vacancy: Row | null) => { setExportVacancy(vacancy); setExportError(undefined); if (month) setExportMonth(month); setExportOpen(true); };
  const [q, setQ] = useState("");
  const [status, setStatus] = useState("");
  const [page, setPage] = useState(1);
  const query = useQuery({ queryKey: ["vacancy-report", q, status, month, page],
    queryFn: () => api<Collection & { summary: Record<string, number> }>("/analytics/vacancies?" + new URLSearchParams({ q, status, month, page_number: String(page) })),
    refetchInterval: 30000,
  });
  return <>
    <PageTitle title="Relatório por vagas" subtitle="Acompanhe as vagas divulgadas, o volume de candidatos e os resultados de cada seleção." actions={<button className="button" onClick={() => openExport(null)}><Download size={17} />Exportar relatório</button>} />
    <section className="surface padded vacancy-report">
      <div className="vacancy-report-filters">
        <label className="field"><span>Mês de divulgação</span><input type="month" value={month} onChange={event => { setMonth(event.target.value); setPage(1); }} /></label>
        <label className="field vacancy-report-search"><span>Buscar vaga</span><div className="search-field"><Search size={18} aria-hidden="true" /><input aria-label="Buscar vaga no relatório" placeholder="Digite o cargo ou código da vaga" value={q} onChange={e => { setQ(e.target.value); setPage(1); }} /></div></label>
        <label className="field"><span>Situação da vaga</span><select value={status} onChange={e => { setStatus(e.target.value); setPage(1); }}><option value="">Todas as divulgadas</option>{["PUBLISHED", "PAUSED", "CLOSED", "CANCELED"].map(value => <option key={value} value={value}>{label(value)}</option>)}</select></label>
      </div>
      <div className="vacancy-report-filter-summary"><span>{month ? "Divulgadas em " + month.split("-").reverse().join("/") : "Todos os meses"} · {status ? label(status) : "Todas as situações"}</span>{Boolean(month || q || status) && <button className="text-button" onClick={() => { setMonth(""); setQ(""); setStatus(""); setPage(1); }}>Limpar filtros</button>}</div>
      <ErrorBox error={query.error} />
      {query.isPending ? <p role="status">Carregando relatório…</p> : !query.isError && <>
        <div className="metric-grid vacancy-report-metrics">{[{ title: "Candidatos", key: "candidates", icon: UsersRound }, { title: "Selecionados", key: "selected", icon: UserCheck }, { title: "Contratados", key: "hired", icon: BadgeCheck }].map(({ title, key, icon: Icon }) => <div className="metric vacancy-report-stat" data-result={key} key={key}><span className="vacancy-report-stat-icon"><Icon size={23} aria-hidden="true" /></span><div><span>{title}</span><strong>{query.data?.summary[key] ?? 0}</strong></div></div>)}</div>
        <div className="vacancy-report-list-heading"><h2>Resultados por vaga</h2><span>{query.data?.total ?? 0} vagas encontradas</span></div>
        {!query.data?.items.length ? <Empty title="Nenhuma vaga encontrada">Ajuste a busca ou a situação para consultar as vagas divulgadas.</Empty> : <div className="vacancy-report-list">{query.data.items.map(row => <article className="vacancy-report-card" key={row.id}>
          <header className="vacancy-report-card-heading">
            <div className="vacancy-report-identity"><span className="vacancy-report-icon"><BriefcaseBusiness size={22} aria-hidden="true" /></span><div><h3><Link to={"/app/vagas/" + row.id}>{str(row.title)}</Link></h3><span className="muted">{str(row.code)} · {label(str(row.audience))}</span></div></div>
            <Badge value={row.status} />
          </header>
          <div className="vacancy-report-meta"><span>{str(row.quantity)} {Number(row.quantity) === 1 ? "posto de trabalho" : "postos de trabalho"}</span><span><CalendarDays size={14} aria-hidden="true" />{row.published_at ? "Divulgada em " + date(row.published_at) : "Data de divulgação não registrada"}</span></div>
          <dl className="vacancy-report-numbers">{[["Candidatos", "candidates"], ["Selecionados", "selected"], ["Contratados", "hired"]].map(([title, key]) => <div key={key} data-result={key}><dt>{title}</dt><dd>{str(row[key])}</dd></div>)}</dl>
          <footer className="vacancy-report-card-footer"><button className="button secondary small" onClick={() => openExport(row)}><Download size={15} />Exportar esta vaga</button>
            <Link className="button secondary small" to={"/app/vagas/" + row.id}>Acompanhar vaga <ArrowRight size={15} aria-hidden="true" /></Link>
          </footer>
        </article>)}</div>}
        {Boolean(query.data?.total) && <footer className="task-footer"><span>Exibindo {(page - 1) * 25 + 1}–{Math.min(page * 25, query.data?.total ?? 0)} de {query.data?.total} vagas</span>{(query.data?.total ?? 0) > 25 && <div className="pagination"><button className="button secondary small" disabled={page === 1} onClick={() => setPage(page - 1)}>Anterior</button><span>Página {page}</span><button className="button secondary small" disabled={page * 25 >= (query.data?.total ?? 0)} onClick={() => setPage(page + 1)}>Próxima</button></div>}</footer>}
        <details className="vacancy-report-help"><summary>Como ler os números</summary><p>Os totais respeitam os filtros acima. Uma pessoa inscrita em duas vagas conta uma vez em cada vaga. Selecionados aguardam admissão; contratados já concluíram o processo.</p></details>
      </>}
    </section>
    <Modal open={exportOpen} onOpenChange={value => { if (!exporting) setExportOpen(value); }} title={exportVacancy ? "Exportar relatório desta vaga" : "Exportar relatório do mês"}>
      <form onSubmit={async event => { event.preventDefault(); if (exporting) return; setExporting(true); setExportError(undefined); try {
        const params = new URLSearchParams(exportVacancy ? { vacancy_id: str(exportVacancy.id) } : { month: exportMonth });
        await download("/analytics/vacancies/export.xlsx?" + params, "Porto Aurora-relatorio-" + (exportVacancy ? str(exportVacancy.code) : exportMonth) + ".xlsx");
        setExportOpen(false);
      } catch (failure) { setExportError(failure); } finally { setExporting(false); } }}>
        {exportVacancy ? <p><strong>{str(exportVacancy.title)}</strong><br />{str(exportVacancy.code)}</p> : <label className="field"><span>Selecione o mês</span><input type="month" required value={exportMonth} onChange={event => setExportMonth(event.target.value)} disabled={exporting} /></label>}
        <p>{exportVacancy ? "Inclui os resultados atuais e o histórico desta vaga." : "Inclui todas as vagas divulgadas no mês escolhido às quais você tem acesso."}</p><p className="muted">Excel com resumo, resultados por vaga e, conforme sua permissão, candidaturas e histórico de etapas. Os números refletem a situação na data da exportação.</p>
        <ErrorBox error={exportError} /><div className="actions"><button className="button secondary" type="button" disabled={exporting} onClick={() => setExportOpen(false)}>Cancelar</button><button className="button" disabled={exporting || !exportVacancy && !exportMonth}><Download size={17} />{exporting ? "Gerando relatório…" : "Baixar Excel"}</button></div>
      </form>
    </Modal>
  </>;
}
