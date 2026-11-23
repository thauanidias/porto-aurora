import { AlertCircle, ArrowRight, CheckCircle2 } from "lucide-react";
import { rows, str, type Row } from "../lib/api";

const guidance: Record<string, { name: string; text: string; tab?: string }> = {
  "Título": { name: "Nome da vaga", text: "Informe um título com pelo menos 3 caracteres.", tab: "details" },
  "Descrição": { name: "Descrição da oportunidade", text: "Descreva a oportunidade com pelo menos 30 caracteres.", tab: "details" },
  "Localização": { name: "Cidade e estado", text: "Preencha a cidade e o estado do local de trabalho.", tab: "details" },
  "Pipeline": { name: "Etapas da seleção", text: "Configure as etapas pelas quais os candidatos passarão.", tab: "pipeline" },
  "Responsável": { name: "Recrutador responsável", text: "Defina quem será responsável por acompanhar a seleção.", tab: "details" },
  "Requisitos e aderência": { name: "Requisitos e avaliação", text: "Preencha os requisitos profissionais e configure o modelo de avaliação da vaga.", tab: "scoring" },
  "Formulário de candidatura": { name: "Formulário de inscrição", text: "Confira a configuração das perguntas da candidatura nos dados da vaga.", tab: "details" },
  "Política de privacidade": { name: "Aviso de privacidade", text: "Vincule um aviso de privacidade ativo ao cadastro da vaga.", tab: "details" },
  "Prazo": { name: "Prazo de inscrição", text: "A data de encerramento não foi preenchida ou já passou. Confira o prazo e defina uma data futura antes de publicar ou reabrir a vaga.", tab: "details" },
  "Aprovação": { name: "Aprovação da publicação", text: "Confira a situação da vaga e utilize a ação de aprovação disponível no cabeçalho, conforme suas permissões." },
};

export function PublicationChecklist({ vacancy, onNavigate }: { vacancy: Row; onNavigate: (tab: string) => void }) {
  const items = rows(vacancy.checklist);
  const pending = items.filter(item => !item.ok);
  const completed = items.filter(item => item.ok);
  const progress = items.length ? Math.round(completed.length * 100 / items.length) : 0;
  const published = vacancy.status === "PUBLISHED";
  return <section className="surface padded publication-readiness">
    <div className="publication-readiness-heading"><div><p className="privacy-eyebrow">CONFERÊNCIA DA VAGA</p><h2>{published ? "Acompanhe os dados da publicação" : "O que falta para publicar?"}</h2><p className="muted">{published ? "A vaga está publicada. Confira abaixo os itens que precisam de revisão." : "Revise as pendências abaixo antes de disponibilizar a oportunidade aos candidatos."}</p></div><span className={"publication-readiness-count " + (!pending.length && items.length ? "complete" : "")}>{items.length ? pending.length ? `${pending.length} ${pending.length === 1 ? "item para revisar" : "itens para revisar"}` : "Conferência concluída" : "Sem dados de conferência"}</span></div>
    <div className="publication-readiness-progress"><div><strong>{completed.length} de {items.length} itens conferidos</strong><span>{progress}%</span></div><progress max={100} value={progress} aria-label="Progresso da conferência da publicação" /></div>
    {pending.length > 0 ? <div className="publication-pending-list"><h3>Resolva estes pontos</h3>{pending.map(item => {
      const info = guidance[str(item.label)] ?? { name: str(item.label), text: "Confira este item no cadastro da vaga." };
      return <article key={str(item.label)}><AlertCircle size={21} aria-hidden="true" /><div><h4>{info.name}</h4><p>{info.text}</p></div>{info.tab && <button className="button secondary small" onClick={() => onNavigate(info.tab!)}>Ver {info.tab === "scoring" ? "avaliação" : info.tab === "pipeline" ? "etapas" : "dados da vaga"}<ArrowRight size={14} aria-hidden="true" /></button>}</article>;
    })}</div> : items.length > 0 ? <p className="publication-all-clear"><CheckCircle2 size={20} aria-hidden="true" />{published ? "Todos os itens desta conferência estão em dia." : "Todos os itens desta conferência foram atendidos. Utilize a ação de publicação no cabeçalho, conforme sua permissão."}</p> : <p className="muted">Não há informações de conferência disponíveis para esta vaga.</p>}
    {completed.length > 0 && <details className="publication-completed"><summary>Ver {completed.length} itens já conferidos</summary><ul>{completed.map(item => <li key={str(item.label)}><CheckCircle2 size={17} aria-hidden="true" /><span>{guidance[str(item.label)]?.name ?? str(item.label)}</span><strong>Concluído</strong></li>)}</ul></details>}
  </section>;
}
