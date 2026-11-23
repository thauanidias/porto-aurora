import { useState } from "react";
import { Link } from "react-router-dom";
import { AlertCircle, ArrowRight, BriefcaseBusiness, CheckCircle2, Users } from "lucide-react";
import { str, type Row } from "../lib/api";

export function VacancyHealthCards({ vacancies, canOpen, loading, failed }: { vacancies: Row[]; canOpen: boolean; loading: boolean; failed: boolean }) {
  const [attentionOnly, setAttentionOnly] = useState(false);
  const attention = vacancies.filter(v => ["CRÍTICO", "ATENÇÃO"].includes(str(v.status)));
  const priority: Record<string, number> = { "CRÍTICO": 0, "ATENÇÃO": 1, "SAUDÁVEL": 2 };
  const visible = [...(attentionOnly ? attention : vacancies)].sort((a,b) => (priority[str(a.status)] ?? 3) - (priority[str(b.status)] ?? 3));
  return <section className="surface vacancy-health-overview">
    <div className="vacancy-health-heading"><div><p className="privacy-eyebrow">ACOMPANHAMENTO DA SELEÇÃO</p><h2>Suas vagas, com o próximo passo à vista</h2><p>{loading ? "Carregando o acompanhamento…" : `${vacancies.length} vaga(s) em acompanhamento · ${attention.length} precisam de atenção`}</p></div>{canOpen && <Link className="text-button" to="/app/vagas">Ver todas as vagas <ArrowRight size={16} aria-hidden="true" /></Link>}</div>
    {vacancies.length > 0 && <div className="vacancy-health-view" role="group" aria-label="Filtrar acompanhamento de vagas"><button aria-pressed={!attentionOnly} className={!attentionOnly ? "active" : ""} onClick={() => setAttentionOnly(false)}>Todas as vagas <span>{vacancies.length}</span></button><button aria-pressed={attentionOnly} className={attentionOnly ? "active" : ""} onClick={() => setAttentionOnly(true)}>Precisam de atenção <span>{attention.length}</span></button></div>}
    <div className="vacancy-health-cards">{visible.map(v => {
      const late = v.status === "CRÍTICO";
      const needsAttention = late || v.status === "ATENÇÃO";
      const count = Number(v.candidate_count ?? 0);
      const reasons = Array.isArray(v.reasons) ? v.reasons.map(str) : [];
      const nearDeadline = reasons.includes("Prazo do processo próximo do limite");
      const recommendation = late ? "Revise o prazo previsto e defina as próximas etapas da seleção." : !count ? "Confira a divulgação e as informações da vaga para atrair candidaturas." : nearDeadline ? "Priorize as próximas etapas para concluir a seleção dentro do prazo." : "Acompanhe os perfis recebidos e dê continuidade às etapas da seleção.";
      return <article key={v.id} className={needsAttention ? "needs-attention" : "on-track"}>
        <div className="vacancy-health-card-heading"><span className="vacancy-health-icon"><BriefcaseBusiness size={21} aria-hidden="true" /></span><h3>{str(v.title)}</h3></div>
        <div className="vacancy-health-status">{needsAttention ? <AlertCircle size={16} aria-hidden="true" /> : <CheckCircle2 size={16} aria-hidden="true" />}<strong>{late ? "Prazo da seleção vencido" : nearDeadline ? "Prazo próximo do limite" : !count ? "Aguardando candidaturas" : "Seleção dentro do prazo"}</strong></div>
        <div className="vacancy-health-applicants"><Users size={20} aria-hidden="true" /><strong>{count}</strong><span>{count === 1 ? "candidatura recebida" : "candidaturas recebidas"}</span>{!count && <small>A vaga ainda não recebeu inscrições.</small>}</div>
        <div className="vacancy-health-next"><span>PRÓXIMO PASSO</span><p>{recommendation}</p></div>
        {canOpen && <Link className="button secondary" to={"/app/vagas/" + v.id} aria-label={"Acompanhar a vaga " + str(v.title)}>{late ? "Revisar seleção" : "Acompanhar vaga"}<ArrowRight size={16} aria-hidden="true" /></Link>}
      </article>;
    })}</div>
    {!visible.length && <p className="vacancy-health-empty">{loading ? "Carregando vagas…" : failed ? "Não foi possível carregar as vagas. Atualize a página para tentar novamente." : attentionOnly ? "Nenhuma vaga precisa de atenção neste momento." : "Nenhuma vaga em andamento para acompanhar."}</p>}
  </section>;
}
