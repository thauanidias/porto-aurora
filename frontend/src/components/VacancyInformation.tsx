import { obj, rows, str, type Row } from "../lib/api";
import { label } from "../lib/labels";
import { Badge } from "./ui";

export function VacancyInformation({ vacancy }: { vacancy: Row }) {
  const details = obj(vacancy.details);
  const deadline = vacancy.deadline ? new Date(str(vacancy.deadline)) : null;
  const deadlineText = deadline && !Number.isNaN(deadline.getTime()) ? deadline.toLocaleString("pt-BR", { timeZone: "America/Fortaleza", dateStyle: "short", timeStyle: "short" }) : "Não informado";
  const textSections = [
    ["Sobre a oportunidade", vacancy.description], ["Principais atividades", details.responsibilities],
    ["Requisitos obrigatórios", details.requirements], ["Diferenciais desejáveis", details.desirable],
    ["Formação", details.education], ["Experiência profissional", details.experience],
    ["Benefícios", details.benefits], ["Acessibilidade", details.accessibility],
    ["Informação de vaga afirmativa", details.affirmative],
  ].filter(([, content]) => str(content).trim());
  const groups: { title: string; fields: [string, unknown][] }[] = [
    { title: "Responsáveis e centro de custo", fields: [["Centro de custo", vacancy.org_unit_name], ["Recrutador responsável", vacancy.recruiter_name], ["Gestor requisitante", vacancy.manager_name]] },
    { title: "Condições da oportunidade", fields: [["Local de trabalho", [vacancy.city, vacancy.state].filter(Boolean).join(" / ")], ["Modalidade", label(str(vacancy.modality))], ["Tipo de contrato", label(str(vacancy.contract_type))], ["Cargo", details.position], ["Nível", details.level], ["Jornada", details.workload], ["Turno", details.shift], ["Salário", typeof details.salary === "number" ? details.salary.toLocaleString("pt-BR", { style: "currency", currency: "BRL" }) + (details.hide_salary ? " · oculto no portal" : "") : "Não informado"]] },
    { title: "Prazos e regras da seleção", fields: [["Inscrições até", deadlineText], ["Fuso horário", "Fortaleza (UTC−3)"], ["Prazo previsto do processo", details.sla_hours ? `${Number(details.sla_hours) % 24 === 0 ? `${Number(details.sla_hours) / 24} dias` : `${str(details.sla_hours)} horas`}` : "Não informado"], ["Exceções com justificativa", details.allow_override ? "Permitidas" : "Não permitidas"], ["Retorno após desistência", details.allow_withdrawal_return ? "Permitido dentro do prazo de inscrição" : "Não permitido"]] },
  ];
  return <div className="vacancy-information">
    <header className="vacancy-information-heading"><div><p className="privacy-eyebrow">DETALHES DA OPORTUNIDADE</p><h2>{str(vacancy.title)}</h2><p>{str(vacancy.code)}{vacancy.code ? " · " : ""}{Number(vacancy.quantity)} {Number(vacancy.quantity) === 1 ? "posição" : "posições"} · Público {label(str(vacancy.audience)).toLocaleLowerCase("pt-BR")}</p></div><Badge value={vacancy.status} /></header>
    {textSections.length ? <div className="vacancy-information-description">{textSections.map(([title, content]) => <section key={str(title)}><h3>{str(title)}</h3><p>{str(content)}</p></section>)}</div> : <p className="muted">A descrição e os requisitos ainda não foram preenchidos.</p>}
    <div className="vacancy-information-groups">{groups.map(group => <section key={group.title}><h3>{group.title}</h3><dl>{group.fields.map(([name, value]) => <div key={name}><dt>{name}</dt><dd>{str(value).trim() || "Não informado"}</dd></div>)}</dl></section>)}</div>
    {rows(details.questions).length > 0 && <section className="vacancy-information-questions"><h3>Perguntas da candidatura</h3><ol>{rows(details.questions).map((question, index) => <li key={str(question.key) || index}>{str(question.label)}{question.required ? " · resposta obrigatória" : " · resposta opcional"}</li>)}</ol></section>}
  </div>;
}
