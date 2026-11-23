import { useState } from "react";
import { Link } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { api, obj, post, rows, str, download, type Row } from "../lib/api";
import { useSession } from "../lib/session";
import { ErrorBox } from "./ui";
import { CandidateScreeningProfile } from "./CandidateScreeningProfile";
import { OperationModal, type Operation } from "../pages/Resources";
import { simpleSchema } from "../lib/forms";
import { CandidateCompatibility, compatibilityReport, compatibilityPercentage, compatibilityCategory, categoryNames, mandatoryPending } from "./CandidateCompatibility";

export function CompatibilityRanking({ applications, total, vacancyTitle = "" }: { applications: Row[]; total: number; vacancyTitle?: string }) {
  const session = useSession();
  const client = useQueryClient();
  const canAnalyze = Boolean(session.data?.permissions.includes("score.manage"));
  const [filter, setFilter] = useState("all");
  const [mandatory, setMandatory] = useState(false);
  const [search, setSearch] = useState("");
  const [field, setField] = useState("");
  const [order, setOrder] = useState("score");
  const [busy, setBusy] = useState("");
  const [error, setError] = useState<unknown>();
  const [feedback, setFeedback] = useState("");
  const [history, setHistory] = useState<{ name: string; entries: Row[] } | null>(null);
  const [operation, setOperation] = useState<Operation | null>(null);
  const active = applications.filter(row => ["ACTIVE", "RESERVE"].includes(str(row.status)));
  const ranked = active.filter(row => {
    const report = compatibilityReport(row);
    return (!search || str(obj(row.candidate).name).toLocaleLowerCase("pt-BR").includes(search.toLocaleLowerCase("pt-BR"))) &&
      (filter === "all" || filter === "review" && (compatibilityCategory(row) === "low" || mandatoryPending(row)) || compatibilityCategory(row) === filter || filter === "provisional" && report.status === "PENDING") &&
      (!mandatory || mandatoryPending(row)) && (!field || rows(report.items).some(item => item.field === field && (item.status === "MET" || item.status === "PARTIAL" || item.value != null)));
  }).sort((a, b) => order === "name" ? str(obj(a.candidate).name).localeCompare(str(obj(b.candidate).name), "pt-BR") :
    (compatibilityPercentage(b) ?? -1) - (compatibilityPercentage(a) ?? -1) || str(obj(a.candidate).name).localeCompare(str(obj(b.candidate).name), "pt-BR"));

  async function analyze(list: Row[]) {
    setError(undefined); setFeedback("");
    let completed = 0;
    const failures: string[] = [];
    try {
      for (const row of list) {
        setBusy(row.id);
        try { await post(`/applications/${row.id}/curriculum-analysis`, {}); completed++; }
        catch (err) { failures.push(str(obj(row.candidate).name) + ": " + (err instanceof Error ? err.message : "Análise indisponível")); }
        setFeedback(`${completed} análise(s) concluída(s) de ${list.length}.`);
      }
      if (failures.length) setError(new Error(failures.join("\n")));
      await client.invalidateQueries({ queryKey: ["vacancy-applications"] });
      await client.invalidateQueries({ queryKey: ["application"] });
    } finally { setBusy(""); }
  }
  return <section className="surface padded compatibility-ranking">
    <div className="compatibility-ranking-heading"><div><p className="privacy-eyebrow">APOIO À TRIAGEM CURRICULAR</p><h2>Quem combina com esta vaga?</h2><p className="muted">{vacancyTitle || "Compare as evidências profissionais de cada candidatura."}</p></div>
      {canAnalyze && <button className="button" disabled={Boolean(busy) || !active.length} onClick={() => void analyze(active)}>{busy ? "Analisando currículo…" : "Analisar compatibilidade com currículos"}</button>}
    </div>
    <p className="compatibility-guidance">A nota apoia sua análise. Informação ausente precisa ser confirmada com o candidato. A decisão e o avanço de etapa continuam com o RH.</p>
    <div className="compatibility-summary-cards">{["high", "moderate", "low", "pending"].map(key => <button key={key} className={filter === key ? "selected" : ""} aria-pressed={filter === key} onClick={() => setFilter(filter === key ? "all" : key)}><strong>{active.filter(r => compatibilityCategory(r) === key).length}</strong><span>{categoryNames[key]}</span></button>)}</div>
    <div className="compatibility-filters"><label className="field"><span>Buscar candidato</span><input value={search} onChange={e => setSearch(e.target.value)} placeholder="Nome do candidato" /></label>
      <label className="field"><span>Resultado</span><select aria-label="Resultado" value={filter} onChange={e => setFilter(e.target.value)}><option value="all">Todos os resultados</option><option value="high">Alta compatibilidade</option><option value="moderate">Compatibilidade moderada</option><option value="low">Baixa compatibilidade</option><option value="pending">Sem nota disponível</option><option value="provisional">Resultado provisório</option><option value="review">Revisar currículos com baixa compatibilidade</option></select></label>
      <label className="field"><span>Evidência profissional</span><select aria-label="Evidência profissional" value={field} onChange={e => setField(e.target.value)}><option value="">Todos os critérios</option><option value="education_level">Formação informada</option><option value="experience_years">Experiência informada</option><option value="skills">Competências informadas</option></select></label>
      <label className="field"><span>Ordenar por</span><select aria-label="Ordenar por" value={order} onChange={e => setOrder(e.target.value)}><option value="score">Maior compatibilidade</option><option value="name">Nome do candidato</option></select></label>
    </div>
    <label className="check-field"><input type="checkbox" checked={mandatory} onChange={e => setMandatory(e.target.checked)} /><span>Somente requisitos obrigatórios que precisam de confirmação</span></label>
    <ErrorBox error={error} />
    {feedback && <p role="status">{feedback}</p>}
    {applications.length < total && <p role="status">Exibindo {applications.length} de {total} candidaturas. Carregue as demais para completar a comparação. A análise e os filtros consideram apenas os candidatos carregados.</p>}
    <p className="compatibility-list-count">{ranked.length} candidatura(s) nesta visualização</p>
    {ranked.length ? <div className="table-scroll"><table>
      <thead><tr><th>Candidato e perfil profissional</th><th>Compatibilidade e evidências</th><th>Decisão do RH</th></tr></thead>
      <tbody>{ranked.map(row => <tr key={row.id}>
        <td><Link className="compatibility-candidate-name" to={"/app/candidaturas/" + row.id}>{str(obj(row.candidate).name)}</Link><small className="compatibility-stage">{str(row.stage_name)}</small>{vacancyTitle && <small className="muted">{vacancyTitle}</small>}<CandidateScreeningProfile candidate={obj(row.candidate) as Row} /></td>
        <td><CandidateCompatibility row={row} details /></td>
        <td><div className="compatibility-row-actions"><Link className="button secondary small" to={"/app/candidaturas/" + row.id}>Revisar candidatura</Link>
          {obj(row.screening_review).status === "APPROVED" && <p className="screening-approved" role="status">Aprovado na etapa atual</p>}
          {session.data?.permissions.includes("candidate.move") && <button className="button small" disabled={Boolean(busy) || obj(row.screening_review).status === "APPROVED"} onClick={() => setOperation({ title: "Aprovar etapa · " + str(obj(row.candidate).name), schema: { ...simpleSchema({ reason: { type: "string", title: "Justificativa da aprovação", minLength: 5, maxLength: 4000 } }), description: "Registra a aprovação na etapa atual. A pessoa permanece nesta etapa até o RH confirmar o avanço. Esta ação não representa aprovação final ou contratação." }, submitLabel: "Confirmar aprovação da etapa", run: async data => { await post(`/applications/${row.id}/stage-reviews`, { status: "APPROVED", reason: data.reason, version: row.version }); setFeedback("Aprovação da etapa registrada para " + str(obj(row.candidate).name) + "."); } })}>Aprovar etapa</button>}
          {session.data?.permissions.includes("candidate.select") && <button className="button secondary small screening-reject" disabled={Boolean(busy)} onClick={() => setOperation({ title: "Não aprovar candidatura · " + str(obj(row.candidate).name), schema: { ...simpleSchema({ reason: { type: "string", title: "Justificativa da decisão", minLength: 5, maxLength: 4000 } }), description: "Esta ação encerra a candidatura nesta vaga como não selecionada. O perfil e o currículo são preservados. O envio de retorno por e-mail não será solicitado aqui." }, submitLabel: "Confirmar não aprovação", run: async data => { await post(`/applications/${row.id}/decision`, { decision: "REJECTED", reason: data.reason, version: row.version, send_rejection_email: false }); setFeedback("Candidatura encerrada como não selecionada para " + str(obj(row.candidate).name) + "."); } })}>Não aprovar candidatura</button>}
          {Boolean(row.cv_id) && <button className="text-button" onClick={async () => { setError(undefined); try { await download(`/documents/${row.cv_id}/download`, "curriculo"); } catch (err) { setError(err); } }}>Ver currículo completo</button>}
          {canAnalyze && <><button className="text-button" disabled={Boolean(busy)} onClick={() => void analyze([row])}>{busy === row.id ? "Analisando…" : "Analisar novamente"}</button><button className="text-button" onClick={async () => { setError(undefined); try { const result = await api<{ items: Row[] }>(`/applications/${row.id}/curriculum-analysis/history`); setHistory({ name: str(obj(row.candidate).name), entries: result.items }); } catch (err) { setError(err); } }}>Histórico de análises</button></>}
        </div></td>
      </tr>)}</tbody>
    </table></div> : <p className="compatibility-empty">{active.length ? "Nenhuma candidatura corresponde aos filtros. Altere os filtros para ver outros resultados." : "Nenhum candidato ativo para comparar."}</p>}
    {history && <section className="compatibility-history" aria-label="Histórico de análises"><div className="section-heading"><h3>Histórico · {history.name}</h3><button className="text-button" onClick={() => setHistory(null)}>Fechar histórico</button></div>{history.entries.length ? history.entries.map(entry => <article key={entry.id}><p>{new Date(str(entry.created_at)).toLocaleString("pt-BR", { timeZone: "America/Fortaleza" })}</p><CandidateCompatibility row={{ id: entry.id, version: 1, compatibility: { curriculum: entry.analysis } }} details /></article>) : <p>Nenhuma análise curricular por IA registrada.</p>}</section>}
    <OperationModal operation={operation} onClose={() => setOperation(null)} />
  </section>;
}
