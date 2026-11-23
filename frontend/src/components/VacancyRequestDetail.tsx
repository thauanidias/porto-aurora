import { obj, str, type Row } from "../lib/api";
import { date, label } from "../lib/labels";
import { Badge } from "./ui";

function calendarDate(value: unknown) {
  const text = str(value);
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(text);
  return match ? `${match[3]}/${match[2]}/${match[1]}` : date(value);
}

export function VacancyRequestDetail({ request }: { request: Row }) {
  const details = obj(request.details);
  const steps = Array.isArray(request.workflow_snapshot) ? request.workflow_snapshot.map(obj) : [];
  const current = Number(request.current_step ?? 0);
  const pending = request.status === "PENDING_APPROVAL";
  const descriptions: Record<string, string> = {
    PENDING_APPROVAL: "Sua solicitação foi enviada e aguarda análise do RH.",
    APPROVED: "Solicitação aprovada pelo RH. Acompanhe a criação da vaga.",
    DRAFT: request.last_decision === "REJECTED" ? "O RH solicitou ajustes. Confira o retorno antes de reenviar." : "Solicitação em rascunho, ainda não enviada ao RH.",
    CONVERTED: "A solicitação foi transformada em uma vaga.",
    REJECTED: "Confira abaixo o retorno do RH sobre esta solicitação.",
  };
  const fields = [
    ["Setor", str(request.org_unit_name) || "Não informado"],
    ["Solicitante", str(request.requested_by_name) || "Não informado"],
    ["Cargo", str(details.position) || "Não informado"],
    ["Quantidade", `${str(request.quantity)} ${Number(request.quantity) === 1 ? "posição" : "posições"}`],
    ["Motivo da abertura", details.request_type ? label(str(details.request_type)) : "Não informado"],
    ["Urgência", details.urgency ? label(str(details.urgency)) : "Normal"],
    ["Prazo desejado", calendarDate(details.desired_date)],
    ["Centro de custo", str(details.cost_center) || "Não informado"],
  ];
  return <div className="vacancy-request-detail">
    <section className="request-status-summary" aria-label="Andamento da solicitação">
      <Badge value={request.status === "DRAFT" && request.last_decision === "REJECTED" ? "RETURNED" : request.status} />
      <p>{descriptions[str(request.status)] || "Acompanhe as informações e o retorno do RH nesta solicitação."}</p>
      {Boolean(request.created_at) && <small>Enviada em {date(request.created_at)}</small>}
    </section>
    <section aria-labelledby="request-overview-title">
      <h3 id="request-overview-title">Resumo da contratação</h3>
      <dl className="request-overview-grid">{fields.map(([title, value]) => <div key={title}><dt>{title}</dt><dd>{value}</dd></div>)}</dl>
    </section>
    <section className="request-reasons" aria-labelledby="request-reasons-title">
      <h3 id="request-reasons-title">Necessidade da vaga</h3>
      {Boolean(details.reason) && <div><h4>Motivo da solicitação</h4><p>{str(details.reason)}</p></div>}
      <div><h4>Justificativa</h4><p>{str(details.justification) || "Não informada"}</p></div>
      {details.request_type === "REPLACEMENT" && Boolean(details.replaced_employee) && <div><h4>Colaborador substituído</h4><p>{str(details.replaced_employee)}</p></div>}
    </section>
    {Boolean(request.rh_feedback) && <section className="request-feedback" aria-label="Retorno do RH"><h3>Retorno do RH</h3><p>{str(request.rh_feedback)}</p></section>}
    {steps.length > 0 && <section className="request-approval" aria-labelledby="request-approval-title"><h3 id="request-approval-title">Análise e aprovação</h3><ol>{steps.map((step, index) => <li key={index} aria-current={pending && index === current ? "step" : undefined}>
      <span className="request-step-number" aria-hidden="true">{index + 1}</span><div><strong>{str(step.name) || `Etapa ${index + 1}`}</strong><p>{pending && index === current ? "Aguardando análise" : index < current || ["APPROVED", "CONVERTED"].includes(str(request.status)) ? "Concluída" : "Próxima etapa"}{Number(step.sla_hours) > 0 ? ` · Prazo de análise: ${step.sla_hours} horas` : ""}</p></div>
    </li>)}</ol></section>}
  </div>;
}
