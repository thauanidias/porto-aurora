import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api, post, str, type Row, type Collection } from "../lib/api";
import { useSession } from "../lib/session";
import { ErrorBox } from "./ui";
import { simpleSchema } from "../lib/forms";
import { OperationModal, type Operation } from "../pages/Resources";

export function DuplicateReview({ candidateId }: { candidateId: string }) {
  const session = useSession();
  const allowed = session.data?.permissions.includes("candidate.merge");
  const [operation, setOperation] = useState<Operation | null>(null);
  const query = useQuery({
    queryKey: ["duplicates", candidateId],
    queryFn: () =>
      api<Collection>("/candidates/" + candidateId + "/duplicates"),
    enabled: Boolean(allowed),
  });
  if (!allowed) return null;
  return (
    <section className="surface padded">
      <h2>Revisão de duplicidades</h2>
      <ErrorBox error={query.error} />
      {query.isPending ? (
        <p role="status">Verificando possíveis duplicidades…</p>
      ) : query.data?.items.length ? (
        query.data.items.map((row) => (
          <article key={row.id}>
            <h3>Possível cadastro duplicado</h3>
            <p>
              {str(row.name)} · {str(row.email)} · {str(row.phone)}
            </p>
            <button
              className="button secondary"
              onClick={() =>
                setOperation({
                  title: "Confirmar consolidação de cadastros",
                  schema: simpleSchema({
                    reason: {
                      type: "string",
                      title: "Justificativa da identidade conferida",
                      minLength: 10,
                    },
                  }),
                  run: (data) =>
                    post("/candidates/" + candidateId + "/merge", {
                      ...data,
                      source_id: row.id,
                    }),
                })
              }
            >
              Consolidar neste perfil
            </button>
            <p className="muted">
              Confira a identidade antes de confirmar. Processos e documentos
              serão vinculados a este perfil; o acesso da conta duplicada será
              encerrado. O histórico original permanece auditável.
            </p>
          </article>
        ))
      ) : (
        <p>Nenhuma possível duplicidade identificada por e-mail ou telefone.</p>
      )}
      <OperationModal
        operation={operation}
        onClose={() => setOperation(null)}
      />
    </section>
  );
}
export function RecalculateScore({
  applicationId,
  vacancyId,
}: {
  applicationId: string;
  vacancyId: string;
}) {
  const [operation, setOperation] = useState<Operation | null>(null);
  const allowed = useSession().data?.permissions.includes("score.manage");
  const query = useQuery({
    queryKey: ["vacancy", vacancyId],
    queryFn: () => api<Row>("/vacancies/" + vacancyId),
    enabled: Boolean(allowed),
  });
  if (!allowed) return null;
  const models = (query.data?.scoring_models ?? []) as Row[];
  return (
    <>
      <ErrorBox error={query.error} />
      <button
        className="button secondary"
        disabled={!models.length}
        onClick={() =>
          setOperation({
            title: "Recalcular aderência",
            schema: simpleSchema({
              model_id: {
                enum: models.map((m) => "Versão " + str(m.number)),
                title: "Versão do modelo",
              },
              reason: {
                type: "string",
                title: "Justificativa do recálculo",
                minLength: 10,
              },
            }),
            run: (data) =>
              post("/applications/" + applicationId + "/recalculate", {
                ...data,
                model_id: models.find(
                  (m) => "Versão " + str(m.number) === data.model_id,
                )?.id,
              }),
          })
        }
      >
        Recalcular com versão escolhida
      </button>
      <p className="muted">
        {models
          .map((m) => "Versão " + str(m.number) + ": " + str(m.reason))
          .join(" · ")}
        . Os resultados anteriores são preservados.
      </p>
      <OperationModal
        operation={operation}
        onClose={() => setOperation(null)}
      />
    </>
  );
}
export function BulkMovement({
  applications,
  stages,
}: {
  applications: Row[];
  stages: Row[];
}) {
  const [selected, setSelected] = useState<string[]>([]);
  const [operation, setOperation] = useState<Operation | null>(null);
  const allowed = useSession().data?.permissions.includes("candidate.move");
  if (!allowed) return null;
  const active = applications.filter((a) =>
    ["ACTIVE", "RESERVE"].includes(str(a.status)),
  );
  return (
    <details className="surface padded">
      <summary>Movimentar candidaturas em lote</summary>
      <p>
        Selecione até 100 candidaturas carregadas. A operação só é aplicada se
        todas passarem pelas validações.
      </p>
      <div className="form-grid">
        {active.map((a) => (
          <label className="check-field" key={a.id}>
            <input
              type="checkbox"
              checked={selected.includes(a.id)}
              onChange={(e) =>
                setSelected(
                  e.target.checked
                    ? [...selected, a.id]
                    : selected.filter((id) => id !== a.id),
                )
              }
            />
            <span>
              {str((a.candidate as Row)?.name)} · {str(a.stage_name)}
            </span>
          </label>
        ))}
      </div>
      <button
        className="button secondary"
        disabled={!selected.length || selected.length > 100}
        onClick={() =>
          setOperation({
            title: "Confirmar movimentação em lote",
            schema: simpleSchema({
              target_position: {
                enum: stages.map((s) => str(s.position) + " · " + str(s.name)),
                title: "Etapa de destino",
              },
              reason: { type: "string", title: "Justificativa" },
              override: {
                type: "boolean",
                title: "Exceção autorizada pela política da vaga",
              },
            }),
            run: async (data) => {
              const stage = stages.find(
                (s) =>
                  str(s.position) + " · " + str(s.name) ===
                  data.target_position,
              );
              await post("/applications/bulk/move", {
                moves: active
                  .filter((a) => selected.includes(a.id))
                  .map((a) => ({
                    id: a.id,
                    version: a.version,
                    stage_id: stage?.id,
                    reason: data.reason,
                    override: data.override,
                  })),
              });
              setSelected([]);
            },
          })
        }
      >
        Mover {selected.length} selecionadas
      </button>
      <OperationModal
        operation={operation}
        onClose={() => setOperation(null)}
      />
    </details>
  );
}
