import { useQuery } from "@tanstack/react-query";
import { api, obj, rows, str, type Row } from "../lib/api";
import { DataTable, ErrorBox } from "./ui";
import { RecordDetail } from "../pages/Resources";
export function ProcessAnalytics() {
  const query = useQuery({
    queryKey: ["process-analytics"],
    queryFn: () => api<Row>("/analytics/processes"),
  });
  const data: Record<string, unknown> = query.data ?? {};
  return (
    <section className="surface padded">
      <h2>Saúde e capacidade de recrutamento</h2>
      <ErrorBox error={query.error} />
      <h3>Carga por recrutador</h3>
      <DataTable
        data={rows(data.capacity)}
        columns={["name", "open_vacancies", "active_applications"]}
      />
      <details>
        <summary>Permanência, conversão e atrasos por etapa</summary>
        <DataTable
          data={rows(data.stages)}
          columns={[
            "vacancy",
            "name",
            "entered",
            "active",
            "advanced",
            "conversion",
            "mean_hours",
            "overdue",
          ]}
        />
      </details>
      <details>
        <summary>Resultados e governança da aderência</summary>
        <DataTable
          data={rows(data.model_outcomes)}
          columns={["status", "count", "mean_score"]}
        />
      </details>
      <div className="timing-row">
        <span>Satisfação do candidato (NPS)</span>
        <strong>
          {str(obj(data.satisfaction).nps) || "—"}{" "}
          <small>{str(obj(data.satisfaction).responses ?? 0)} respostas</small>
        </strong>
      </div>
      <div className="timing-row">
        <span>Taxa de desistência</span>
        <strong>
          {data.withdrawal_rate == null ? "—" : str(data.withdrawal_rate) + "%"}
        </strong>
      </div>
      <details>
        <summary>Fórmulas e limites de interpretação</summary>
        <RecordDetail value={obj(data.formulas)} />
      </details>
    </section>
  );
}
