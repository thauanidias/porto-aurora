import { str, type Row } from "../lib/api";
import { SchemaForm } from "./SchemaForm";

export function RequestDecisionForm({ request, approve, onSubmit }: {
  request: Row; approve: boolean; onSubmit: (values: Record<string, unknown>) => Promise<void>;
}) {
  return <div className="request-decision-form">
    <div className="request-decision-summary"><strong>{str(request.title)}</strong><p>{str(request.requested_by_name)} · {str(request.org_unit_name)}</p></div>
    <p>{approve ? "Confirme o aceite desta solicitação. A decisão ficará registrada no histórico e o gestor será notificado. Se houver outras aprovações, o pedido seguirá para a próxima etapa." : "Informe o que precisa ser corrigido. A solicitação retornará ao gestor para ajustes e novo envio."}</p>
    <SchemaForm schema={{ type: "object", properties: { comment: {
      type: "string", title: approve ? "Observação para o gestor (opcional)" : "Orientações para ajuste",
      ...(approve ? {} : { minLength: 5 }), maxLength: 2000,
    } }, required: approve ? [] : ["comment"] }} submitLabel={approve ? "Confirmar aceite" : "Devolver para ajustes"} onSubmit={onSubmit} />
  </div>;
}
