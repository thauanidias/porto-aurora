import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  api,
  post,
  put,
  obj,
  str,
  type Collection,
  type Row,
} from "../lib/api";
import { useSession } from "../lib/session";
import { DataTable, ErrorBox } from "./ui";
import {
  OperationModal,
  RecordDetail,
  type Operation,
} from "../pages/Resources";
import { simpleSchema } from "../lib/forms";

export function ConfigHistory({
  kind,
  recordId,
}: {
  kind: string;
  recordId: string;
}) {
  const query = useQuery({
    queryKey: ["config-history", recordId],
    queryFn: () =>
      api<Collection>("/configuration/" + kind + "/" + recordId + "/history"),
  });
  return (
    <div>
      <h3>Histórico de versões</h3>
      <ErrorBox error={query.error} />
      {query.data?.items.map((row) => (
        <details key={row.id}>
          <summary>
            Versão {str(row.revision)} · {str(row.reason)}
          </summary>
          <RecordDetail value={obj(row.data)} />
        </details>
      ))}
    </div>
  );
}
export function RoleControls({ row }: { row?: Row }) {
  const session = useSession();
  const allowed = session.data?.permissions.includes("role.manage");
  const [operation, setOperation] = useState<Operation | null>(null);
  const perms = useQuery({
    queryKey: ["permissions"],
    queryFn: () => api<Collection>("/permissions"),
    enabled: Boolean(allowed),
  });
  if (!allowed || row?.name === "SUPER_ADMIN") return null;
  return (
    <>
      <button
        className="button secondary small"
        onClick={() =>
          setOperation({
            title: row ? "Editar perfil" : "Criar perfil",
            schema: simpleSchema({
              name: { type: "string", title: "Nome" },
              permissions: {
                type: "array",
                title: "Permissões",
                items: {
                  type: "string",
                  enum: perms.data?.items.map((p) => p.name) ?? [],
                },
              },
            }),
            initial: row
              ? { name: row.name, permissions: row.permissions }
              : undefined,
            run: (data) =>
              row
                ? put("/roles/" + row.id, { ...data, version: row.version })
                : post("/roles", data),
          })
        }
      >
        {row ? "Editar perfil" : "Criar perfil"}
      </button>
      <OperationModal
        operation={operation}
        onClose={() => setOperation(null)}
      />
    </>
  );
}
export function UserAccess({ row }: { row: Row }) {
  const [operation, setOperation] = useState<Operation | null>(null);
  const session = useSession();
  if (row.id === session.data?.user.id) return null;
  return (
    <>
      <button
        className="text-button"
        onClick={() =>
          setOperation({
            title: "Perfis e estrutura do usuário",
            schema: simpleSchema({
              roles: {
                type: "array",
                title: "Perfis",
                items: { type: "string" },
              },
              org_unit_id: {
                type: "string",
                title: "Centro de custo",
              },
              reason: { type: "string", minLength: 10, title: "Justificativa" },
            }),
            initial: { org_unit_id: row.org_unit_id, roles: row.roles ?? [] },
            run: (data) =>
              put("/users/" + row.id + "/access", {
                ...data,
                org_unit_id: data.org_unit_id || null,
                version: row.version,
              }),
          })
        }
      >
        Perfis e estrutura
      </button>
      <OperationModal
        operation={operation}
        onClose={() => setOperation(null)}
      />
    </>
  );
}
export function TestReviews({ applicationId }: { applicationId: string }) {
  const [operation, setOperation] = useState<Operation | null>(null);
  const [error, setError] = useState<unknown>();
  const query = useQuery({
    queryKey: ["test-reviews", applicationId],
    queryFn: () =>
      api<Collection>("/test-assignments?application_id=" + applicationId),
  });
  const attempts = (query.data?.items ?? [])
    .filter((r) => r.application_id === applicationId)
    .flatMap((row) =>
      Array.isArray(row.attempts)
        ? (row.attempts as Row[]).map((a) => ({
            ...a,
            test_name: obj(row.snapshot).name,
          }))
        : [],
    );
  return (
    <>
      <h3>Provas e correção humana</h3>
      <ErrorBox error={error ?? query.error} />
      <DataTable
        data={attempts}
        columns={["test_name", "number", "status", "score"]}
        actions={(a) =>
          Boolean(a.submitted_at) && (
            <button
              className="text-button"
              onClick={async () => {
                try {
                  const detail = await api<Row>(
                    "/test-attempts/" + a.id + "/review",
                  );
                  const questions = Array.isArray(detail.questions)
                    ? (detail.questions as Row[])
                    : [];
                  setOperation({
                    title: "Revisar respostas",
                    schema: simpleSchema({
                      grading: {
                        type: "object",
                        title: "Critérios de correção",
                        properties: Object.fromEntries(
                          questions
                            .filter((q) =>
                              ["TEXT", "ESSAY", "PRACTICAL", "UPLOAD"].includes(
                                str(q.kind),
                              ),
                            )
                            .map((q) => [
                              str(q.key),
                              {
                                type: "object",
                                title:
                                  str(q.text) +
                                  " · Resposta: " +
                                  str(obj(detail.answers)[str(q.key)]),
                                properties: {
                                  score: {
                                    type: "number",
                                    title: "Nota (0 a 100)",
                                    minimum: 0,
                                    maximum: 100,
                                  },
                                  comment: {
                                    type: "string",
                                    title: "Parecer da correção",
                                    minLength: 3,
                                  },
                                },
                              },
                            ]),
                        ),
                      },
                    }),
                    run: (data) =>
                      post("/test-attempts/" + a.id + "/grade", {
                        ...data,
                        version: detail.version,
                      }),
                  });
                } catch (e) {
                  setError(e);
                }
              }}
            >
              Corrigir
            </button>
          )
        }
      />
      <OperationModal
        operation={operation}
        onClose={() => setOperation(null)}
      />
    </>
  );
}
