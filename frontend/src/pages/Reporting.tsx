import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api, post, download, obj, str, type Collection } from "../lib/api";
import { useSession } from "../lib/session";
import { label } from "../lib/labels";
import { DataTable, ErrorBox, PageTitle } from "../components/ui";
import { CalibrationPanel } from "../components/CollaborationPanels";
import { ProcessAnalytics } from "../components/ProcessAnalytics";
import { OperationModal, type Operation } from "./Resources";
import { simpleSchema } from "../lib/forms";
export function ReportBuilder() {
  const session = useSession();
  const [entity, setEntity] = useState("vacancies");
  const [status, setStatus] = useState("");
  const [selected, setSelected] = useState<string[]>([]);
  const [page, setPage] = useState(1);
  const [error, setError] = useState<unknown>();
  const [operation, setOperation] = useState<Operation | null>(null);
  const options = useQuery({
    queryKey: ["report-options"],
    queryFn: () => api<Record<string, string[]>>("/reports"),
  });
  const saved = useQuery({
    queryKey: ["saved-reports"],
    queryFn: () => api<Collection>("/configuration/saved-reports"),
  });
  const columns = selected.length ? selected : (options.data?.[entity] ?? []);
  const query = useQuery({
    queryKey: ["report", entity, status, columns, page],
    queryFn: () =>
      api<Collection>(
        "/reports/" +
          entity +
          "?" +
          new URLSearchParams({
            status,
            columns: columns.join(","),
            page_number: String(page),
          }),
      ),
  });
  return (
    <>
      <PageTitle
        title="Relatórios"
        subtitle="Configure colunas, filtre e exporte os registros autorizados."
        actions={
          <>
            {["csv", "xlsx"].map((format) => (
              <button
                className="button secondary"
                key={format}
                onClick={async () => {
                  try {
                    await download(
                      "/reports/" +
                        entity +
                        "?" +
                        new URLSearchParams({
                          output: format,
                          status,
                          columns: columns.join(","),
                        }),
                      "relatorio." + format,
                    );
                  } catch (e) {
                    setError(e);
                  }
                }}
              >
                Exportar {format.toUpperCase()}
              </button>
            ))}
          </>
        }
      />
      <section className="surface padded">
        <div className="inline-form">
          <label className="field">
            <span>Relatório salvo</span>
            <select
              defaultValue=""
              onChange={(e) => {
                const item = saved.data?.items.find(
                  (r) => r.id === e.target.value,
                );
                if (item) {
                  const data = obj(item.data);
                  setEntity(str(data.entity));
                  setStatus(str(obj(data.filters).status));
                  setSelected(
                    Array.isArray(data.columns)
                      ? (data.columns as string[])
                      : [],
                  );
                  setPage(1);
                }
              }}
            >
              <option value="">Selecionar configuração</option>
              {saved.data?.items.map((r) => (
                <option key={r.id} value={r.id}>
                  {str(r.name)}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            <span>Relatório</span>
            <select
              value={entity}
              onChange={(e) => {
                setEntity(e.target.value);
                setSelected([]);
                setPage(1);
              }}
            >
              {Object.keys(options.data ?? {}).map((key) => (
                <option key={key} value={key}>
                  {{
                    vacancies: "Vagas",
                    applications: "Candidaturas",
                    interviews: "Entrevistas",
                    offers: "Ofertas",
                    tasks: "Tarefas",
                    audit: "Auditoria",
                  }[key] ?? key}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            <span>Situação</span>
            <input
              value={status}
              onChange={(e) => {
                setStatus(e.target.value);
                setPage(1);
              }}
              placeholder="Todas"
            />
          </label>
        </div>
        <details>
          <summary>Colunas do relatório</summary>
          <div className="compare-select">
            {(options.data?.[entity] ?? []).map((key) => (
              <label className="check-field" key={key}>
                <input
                  type="checkbox"
                  checked={columns.includes(key)}
                  onChange={(e) => {
                    const next = e.target.checked
                      ? [...columns, key]
                      : columns.filter((c) => c !== key);
                    if (next.length) setSelected(next);
                  }}
                />
                <span>{label(key)}</span>
              </label>
            ))}
          </div>
        </details>
        {session.data?.permissions.includes("config.manage") && (
          <button
            className="button secondary small"
            onClick={() =>
              setOperation({
                title: "Salvar configuração do relatório",
                schema: simpleSchema({
                  name: { type: "string", title: "Nome", minLength: 2 },
                  reason: {
                    type: "string",
                    title: "Justificativa",
                    minLength: 5,
                  },
                }),
                run: (values) =>
                  post("/configuration/saved-reports", {
                    ...values,
                    data: {
                      entity,
                      columns,
                      filters: { status },
                      order_by: "created_at",
                    },
                  }),
              })
            }
          >
            Salvar relatório
          </button>
        )}
        <ErrorBox error={error ?? query.error} />
        <DataTable
          data={query.data?.items ?? []}
          columns={columns}
          total={query.data?.total}
          page={page}
          pageSize={50}
          onPage={setPage}
        />
      </section>
      <CalibrationPanel />
      <ProcessAnalytics />
      <OperationModal
        operation={operation}
        onClose={() => setOperation(null)}
      />
    </>
  );
}
