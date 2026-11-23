import { useState, type ReactNode } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowRight, MapPin, Plus, Search } from "lucide-react";
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
import { DataTable, Empty, ErrorBox, Modal, PageTitle, Badge } from "../components/ui";
import { RemoteForm, SchemaForm, type Schema } from "../components/SchemaForm";
import { label, date } from "../lib/labels";
import { ProfilePhoto } from "../components/ProfilePhoto";
import { InterviewCandidates } from "../components/InterviewCandidates";
import { InterviewLinkForm } from "../components/InterviewLinkForm";
import { TaskChecklist } from "../components/TaskChecklist";
import { VacancyDirectory } from "../components/VacancyDirectory";
import { EvaluationsDirectory } from "../components/EvaluationsDirectory";
import { VacancyRequestDetail } from "../components/VacancyRequestDetail";
import { RequestDecisionForm } from "../components/RequestDecisionForm";
import { RequestCardList } from "../components/RequestCardList";

export type Operation = {
  title: string;
  schema?: Schema;
  form?: string;
  submitLabel?: string;
  initial?: Record<string, unknown>;
  renderForm?: (onSubmit: (values: Record<string, unknown>) => Promise<void>) => ReactNode;
  run: (data: Record<string, unknown>) => Promise<unknown>;
};
export function OperationModal({
  operation,
  onClose,
}: {
  operation: Operation | null;
  onClose: () => void;
}) {
  const client = useQueryClient();
  const submit = async (values: Record<string, unknown>) => {
    if (!operation) return;
    await operation.run(values);
    await client.invalidateQueries();
    onClose();
  };
  return (
    <Modal
      open={Boolean(operation)}
      onOpenChange={(v) => {
        if (!v) {
          onClose();
        }
      }}
      title={operation?.title ?? ""}
    >
      {operation &&
        (operation.renderForm ? operation.renderForm(submit) : operation.form ? (
          <RemoteForm
            name={operation.form}
            submitLabel={operation.submitLabel}
            initial={operation.initial}
            onSubmit={submit}
          />
        ) : (
          <SchemaForm
            submitLabel={operation.submitLabel}
            schema={operation.schema ?? { type: "object", properties: {} }}
            initial={operation.initial}
            onSubmit={submit}
          />
        ))}
    </Modal>
  );
}
const specifications: Record<
  string,
  {
    title: string;
    endpoint: string;
    columns: string[];
    form?: string;
    permission?: string;
  }
> = {
  requests: {
    title: "Solicitações de vaga",
    endpoint: "/vacancy-requests",
    columns: ["title", "requested_by_name", "org_unit_name", "quantity", "status", "rh_feedback", "created_at"],
    form: "request",
    permission: "request.create",
  },
  vacancies: {
    title: "Vagas",
    endpoint: "/vacancies",
    columns: ["title", "city", "quantity", "status"],
    form: "vacancy",
    permission: "vacancy.create",
  },
  candidates: {
    title: "Candidatos",
    endpoint: "/candidates",
    columns: ["name", "recruitment_type", "vacancy_titles", "finalist_history", "updated_at"],
    form: "rh-candidate",
    permission: "candidate.import",
  },
  pools: {
    title: "Banco de talentos",
    endpoint: "/talent-pools",
    columns: ["name", "description", "created_at"],
    form: "pool",
    permission: "talent.manage",
  },
  interviews: {
    title: "Entrevistas",
    endpoint: "/interviews/candidates",
    columns: ["name", "vacancy_title", "stage_name", "interview_links"],
    permission: "interview.manage",
  },
  evaluations: {
    title: "Feedback dos candidatos",
    endpoint: "/evaluations",
    columns: ["application_id", "category", "status", "submitted_at"],
  },
  tests: {
    title: "Biblioteca de testes",
    endpoint: "/tests",
    columns: ["name", "duration_minutes", "attempts_allowed", "pass_score"],
    form: "test",
    permission: "test.manage",
  },
  offers: {
    title: "Cartas oferta",
    endpoint: "/offers",
    columns: ["application_id", "number", "status", "expires_at"],
    form: "offer",
    permission: "offer.create",
  },
  tasks: {
    title: "Meu trabalho",
    endpoint: "/tasks",
    columns: ["title", "priority", "due_at", "status"],
    form: "task",
    permission: "task.manage",
  },
  audit: {
    title: "Auditoria",
    endpoint: "/audit",
    columns: ["created_at", "action", "entity", "entity_id", "user_id"],
  },
};
export function ResourcePage({ kind }: { kind: string }) {
  const spec = specifications[kind];
  const [q, setQ] = useState("");
  const [page, setPage] = useState(1);
  const [operation, setOperation] = useState<Operation | null>(null);
  const [detail, setDetail] = useState<Row | null>(null);
  const [requestMessage, setRequestMessage] = useState("");
  const [error, setError] = useState<unknown>();
  const client = useQueryClient();
  const navigate = useNavigate();
  const session = useSession();
  const welcomeNames = session.data?.user.name.trim().split(/\s+/).filter(Boolean) ?? [];
  const welcomeName = welcomeNames.length > 1 ? `${welcomeNames[0]} ${welcomeNames[welcomeNames.length - 1]}` : welcomeNames[0];
  const managerArea = Boolean(session.data?.permissions.includes("request.create")) && !session.data?.permissions.includes("vacancy.create") && !session.data?.permissions.includes("request.approve");
  const managerRequests = kind === "requests" && !session.data?.permissions.includes("vacancy.all") && !session.data?.permissions.includes("request.approve");
  const managerFinalists = managerArea && kind === "candidates";
  const endpoint = managerFinalists ? "/manager-finalists" : spec.endpoint;
  const Listing = kind === "requests" ? RequestCardList : DataTable;
  const query = useQuery({
    enabled: !["tasks", "vacancies", "evaluations"].includes(kind),
    queryKey: [kind, endpoint, q, page],
    refetchInterval: kind === "requests" || kind === "interviews" || kind === "candidates" ? 15000 : false,
    queryFn: () =>
      api<Collection>(
        endpoint +
          "?" +
          new URLSearchParams({ q, page_number: String(page) }),
      ),
  });
  const act = async (fn: () => Promise<unknown>) => {
    setError(undefined);
    try {
      await fn();
      await client.invalidateQueries();
    } catch (e) {
      setError(e);
    }
  };
  const open = (row: Row) => {
    if (kind === "vacancies") navigate((managerArea ? "/gestor/" : "/app/") + "vagas/" + row.id);
    else if (kind === "candidates") navigate((managerArea ? "/gestor/" : "/app/") + "candidatos/" + row.id);
    else if (kind === "evaluations")
      navigate((managerArea ? "/gestor/" : "/app/") + "candidaturas/" + str(row.application_id));
    else if (kind === "interviews")
      navigate((managerArea ? "/gestor/" : "/app/") + "candidaturas/" + row.id);
    else setDetail(row);
  };
  const canDecideRequest = (row: Row) => row.status === "PENDING_APPROVAL" && row.can_decide === true && session.data?.permissions.includes("request.approve") === true;
  const decideRequest = (row: Row, approve: boolean) => {
    setDetail(null);
    setRequestMessage("");
    setOperation({
      title: approve ? "Aceitar solicitação" : "Devolver solicitação para ajustes",
      renderForm: submit => <RequestDecisionForm request={row} approve={approve} onSubmit={submit} />,
      run: async data => {
        const result = await post<Row>("/vacancy-requests/" + row.id + "/approve", {
          comment: data.comment || "", decision: approve ? "APPROVED" : "REJECTED", version: row.version,
        });
        setRequestMessage(approve ? result.status === "APPROVED" ? "Solicitação aceita. A vaga já pode ser criada pelo RH." : "Aceite registrado. A solicitação segue para a próxima aprovação." : "Solicitação devolvida ao gestor com as orientações de ajuste.");
      },
    });
  };
  const attachInterviewLink = (row: Row) => setOperation({
    title: "Anexar link da entrevista · " + str(obj(row.candidate).name),
    renderForm: submit => <InterviewLinkForm onSubmit={submit} />,
    run: data => post("/candidate-activity-links", { ...data, application_id: row.id, kind: "INTERVIEW" }),
  });
  const scheduleInterview = (row: Row) => setOperation({
    title: "Agendar entrevista", form: "interview",
    initial: { vacancy_id: row.vacancy_id, application_ids: [row.id] },
    run: data => post("/interviews", data),
  });
  return (
    <>
      <PageTitle
        title={managerRequests ? "Minhas solicitações de vaga" : managerArea && kind === "vacancies" ? "Minhas vagas" : managerFinalists ? "Finalistas do meu setor" : spec.title}
        subtitle={
          managerArea && kind === "vacancies" ? "Abra uma vaga sob sua responsabilidade para acompanhar os candidatos e as etapas do processo." : managerFinalists ? "Acompanhe os candidatos que o RH definiu como finalistas nas vagas do seu setor." : kind === "requests" ? managerRequests ? "Solicite uma contratação para sua equipe e acompanhe o retorno do RH." : "Acompanhe os pedidos dos gestores, analise e transforme as solicitações aprovadas em vagas." : kind === "vacancies" ? `Olá${welcomeName ? ", " + welcomeName : ", RH"}! Acompanhe suas vagas e os candidatos em cada etapa da seleção.` : kind === "tasks"
            ? "Suas pendências, prazos e próximas ações."
            : kind === "interviews" ? "Envie links e orientações de entrevista para os candidatos nas fases de entrevistas e testes." : kind === "candidates" ? "Banco central de perfis: candidatos antigos e atuais, internos e externos, com ou sem candidatura em vagas." : undefined
        }
        actions={
          kind === "candidates" && !managerArea ? <><Link className="button secondary small" to="/app/candidaturas">Candidaturas externas</Link><Link className="button secondary small" to="/app/candidaturas-internas">Candidaturas internas</Link></> : spec.form &&
          (!spec.permission ||
            session.data?.permissions.includes(spec.permission)) && (
            <button
              className="button"
              onClick={() =>
                setOperation({
                  title: kind === "requests" ? "Nova solicitação de vaga" : kind === "vacancies" ? "Nova vaga" : "Novo registro",
                  form: spec.form,
                  submitLabel: managerRequests ? "Enviar solicitação ao RH" : undefined,
                  initial:
                    kind === "vacancies"
                      ? {
                          publish_on_save: Boolean(
                            session.data?.permissions.includes("vacancy.publish"),
                          ),
                        }
                      : kind === "requests" ? {org_unit_id: session.data?.user.org_unit_id} : undefined,
                  run: (data) => post(managerRequests ? "/vacancy-requests/send" : kind === "interviews" ? "/interviews" : spec.endpoint, data),
                })
              }
            >
              <Plus size={17} />
              {kind === "requests" ? "Solicitar nova vaga" : kind === "vacancies" ? "Nova vaga" : "Novo registro"}
            </button>
          )
        }
      />
      {!managerArea && kind === "candidates" && <p className="alert">Todos os perfis cadastrados ficam reunidos aqui, inclusive os não selecionados em processos anteriores. As decisões de uma vaga não removem o perfil deste banco. Você pode consultar os dados, currículos e histórico pelo botão <strong>Ver perfil</strong>.</p>}
      {managerArea && kind === "vacancies" && <p className="alert">Precisa contratar para sua equipe? <Link to="/gestor/solicitacoes">Enviar uma solicitação ao RH →</Link></p>}
      {kind === "requests" && <p className="alert">{managerRequests
        ? "Envie sua necessidade de contratação ao RH. A decisão, as observações e a vaga criada aparecem nesta mesma tela."
        : "Os pedidos enviados pelos gestores aparecem aqui. Analise a solicitação e registre sua decisão; o gestor acompanha o retorno no painel dele."}</p>}

      {kind === "requests" && requestMessage && <p className="alert success" role="status">{requestMessage}</p>}
      {kind === "evaluations" ? <EvaluationsDirectory manager={managerArea} /> : kind === "vacancies" ? <VacancyDirectory manager={managerArea} /> : kind === "tasks" ? <TaskChecklist onOpen={open} /> : <div className={kind === "candidates" ? "surface candidate-directory" : kind === "interviews" ? "surface interview-directory" : kind === "requests" ? "surface request-directory" : "surface"}>
        <div className="list-toolbar">
          <label className="search-field">
            <Search size={18} />
            <input
              value={q}
              onChange={(e) => {
                setQ(e.target.value);
                setPage(1);
              }}
              aria-label={kind === "vacancies" ? "Buscar vagas" : "Buscar registros"}
              placeholder={kind === "vacancies" ? "Buscar por cargo ou palavra-chave" : kind === "candidates" ? "Buscar candidato pelo nome" : kind === "interviews" ? "Buscar candidato ou vaga" : kind === "requests" ? "Buscar solicitação pelo título…" : "Buscar registros"}
            />
          </label>
        </div>
        <ErrorBox error={error ?? query.error} />
        {query.isPending ? (
          <p className="loading" role="status">
            Carregando registros…
          </p>
        ) : managerFinalists && !query.error && !query.data?.items.length ? (
          <Empty title={q ? "Nenhum finalista encontrado" : "Seu setor ainda não tem finalistas"}>
            {q ? "Tente buscar por outro nome." : "Os candidatos aparecerão aqui quando o RH os mover para a etapa Finalistas ou registrar a seleção. Candidatos em triagem e de outros setores não aparecem nesta lista."}
          </Empty>
        ) : kind === "interviews" && !query.error && !query.data?.items.length ? (
          <Empty title={q ? "Nenhum candidato encontrado" : "Nenhum candidato nas fases de entrevistas ou testes"}>
            {q ? "Tente buscar por outro nome ou vaga." : "Os candidatos aparecerão aqui quando o RH os mover para a etapa de entrevistas ou testes da vaga."}
          </Empty>
        ) : kind === "interviews" ? (
          <InterviewCandidates data={query.data} page={page} onPage={setPage} onOpen={open}
            onAttach={attachInterviewLink} onSchedule={scheduleInterview}
            canAttach={Boolean(session.data?.permissions.includes("candidate.move"))}
            canSchedule={Boolean(session.data?.permissions.includes("interview.manage"))} />
        ) : (
          <Listing
            data={query.data?.items ?? []}
            columns={kind === "requests" ? ["title", "status", "rh_feedback", "created_at"] : managerFinalists ? ["name", "vacancy_titles", "updated_at"] : spec.columns}
            columnLabels={kind === "requests" ? { title: "Solicitação", status: "Andamento", rh_feedback: "Retorno do RH", created_at: "Enviada em" } : managerFinalists ? { vacancy_titles: "Vagas e etapa final" } : kind === "candidates" ? { recruitment_type: "Tipo de perfil", finalist_history: "Finalista em vagas" } : undefined}
            cells={kind === "vacancies" ? {
              title: row => <div className="vacancy-list-title"><Link to={(managerArea ? "/gestor/" : "/app/") + "vagas/" + row.id}>{str(row.title)}</Link><span>{str(row.code)}</span></div>,
              city: row => <span className="vacancy-location"><MapPin size={15} aria-hidden="true" />{str(row.city) || "Local a definir"}</span>,
              quantity: row => <span className="vacancy-quantity">{str(row.quantity)} {Number(row.quantity) === 1 ? "vaga" : "vagas"}</span>,
            } : kind === "candidates" ? {
              finalist_history: row => Array.isArray(row.finalist_history) && row.finalist_history.length ? <ul className="candidate-finalist-history">{row.finalist_history.map((process: Row) => <li key={str(process.application_id)}><span className="candidate-finalist-badge">{process.current ? "Finalista" : "Foi finalista"}</span><Link to={"/app/candidaturas/" + str(process.application_id)}>{str(process.vacancy_title)}</Link><small>Desde {date(process.entered_at)}</small></li>)}</ul> : <span className="muted">—</span>,
              recruitment_type: row => <span>{row.recruitment_type === "INTERNAL" ? "Colaborador" : "Candidato externo"}</span>,
              vacancy_titles: row => managerFinalists && Array.isArray(row.finalist_processes) ? <ul className="manager-finalist-processes">{row.finalist_processes.map((process: Row) => <li key={str(process.application_id)}><Link to={"/gestor/candidaturas/" + str(process.application_id)}>{str(process.vacancy_title)}</Link><span><Badge value="FINALIST" />{str(process.stage_name)}</span></li>)}</ul> : Array.isArray(row.vacancy_titles) && row.vacancy_titles.length
                ? <ul className="candidate-vacancies">{row.vacancy_titles.map((title: string) => <li key={title}>{title}</li>)}</ul>
                : <span className="candidate-no-applications">Sem candidaturas</span>,
              name: row => <div className="candidate-list-name">
                {!row.blind && <ProfilePhoto candidateId={row.id} name={str(row.name)} />}
                <div className="candidate-list-identity"><Link to={(managerArea ? "/gestor/" : "/app/") + "candidatos/" + row.id}>{str(row.name)}</Link>{!row.blind && <span className="candidate-list-location"><MapPin size={13} aria-hidden="true" />{str(row.city) || "Cidade não informada"}</span>}</div>
              </div>,
              updated_at: row => <span className="candidate-list-date">{date(row.updated_at)}</span>,
            } : kind === "requests" ? {
              title: row => <div className="request-list-identity"><button className="request-title-link" onClick={() => open(row)}>{str(row.title)}</button><span>{str(row.requested_by_name)}</span><small>{str(row.org_unit_name)}<span aria-hidden="true"> · </span>{str(row.quantity)} {Number(row.quantity) === 1 ? "posição" : "posições"}</small></div>,
              quantity: row => <span className="request-quantity">{str(row.quantity)} {Number(row.quantity) === 1 ? "posição" : "posições"}</span>,
              status: row => <Badge value={row.status === "DRAFT" && row.last_decision === "REJECTED" ? "RETURNED" : row.status} />,
              rh_feedback: row => <span className={row.rh_feedback ? "request-list-feedback" : "request-list-feedback muted"}>{str(row.rh_feedback) || (row.status === "PENDING_APPROVAL" ? "Enviada ao RH. Aguarde o retorno da análise." : row.status === "APPROVED" ? "Pedido aceito. Próximo passo: criação da vaga." : row.status === "CONVERTED" ? "Vaga criada. Acompanhe o processo seletivo." : "Sem retorno registrado.")}</span>,
            } : undefined}
            total={query.data?.total}
            page={page}
            pageSize={query.data?.page_size ?? 25}
            onPage={setPage}
            onOpen={kind === "vacancies" || kind === "candidates" ? undefined : open}
            actions={(row) => (
              <>
                {kind === "candidates" && <Link className="candidate-profile-link" to={(managerArea ? "/gestor/" : "/app/") + "candidatos/" + row.id} aria-label={"Ver perfil de " + str(row.name)}>Ver perfil <ArrowRight size={15} aria-hidden="true" /></Link>}
                {kind === "vacancies" && <Link className="vacancy-open" to={(managerArea ? "/gestor/" : "/app/") + "vagas/" + row.id} aria-label={"Gerenciar vaga " + str(row.title)}>Gerenciar <ArrowRight size={15} aria-hidden="true" /></Link>}
                {kind === "tasks" && row.status === "OPEN" && (
                  <button
                    className="text-button"
                    onClick={() =>
                      act(() =>
                        put("/tasks/" + row.id, {
                          status: "DONE",
                          version: row.version,
                        }),
                      )
                    }
                  >
                    Concluir
                  </button>
                )}
                {kind === "requests" && row.status === "DRAFT" && session.data?.permissions.includes("request.create") && (row.requested_by === session.data.user.id || session.data.permissions.includes("vacancy.all")) && <button className="text-button" onClick={() => setOperation({
                  title: "Editar solicitação", form: "request",
                  initial: { ...obj(row.details), title: row.title, org_unit_id: row.org_unit_id, quantity: row.quantity },
                  run: data => put("/vacancy-requests/" + row.id, { ...data, version: row.version }),
                })}>Editar</button>}
                {kind === "requests" && row.status === "DRAFT" && session.data?.permissions.includes("request.create") && (
                  <button
                    className="text-button"
                    onClick={() =>
                      setOperation({
                        title: "Enviar solicitação ao RH",
                        submitLabel: "Enviar ao RH",
                        schema: { type: "object", properties: { request_workflow_id: { type: "string", title: "Fluxo de análise do RH" } } },
                        run: (data) =>
                          post("/vacancy-requests/" + row.id + "/submit", {
                            workflow_id: data.request_workflow_id || null,
                            version: row.version,
                            status: "PENDING_APPROVAL",
                          }),
                      })
                    }
                  >
                    Enviar ao RH
                  </button>
                )}
                {kind === "requests" && canDecideRequest(row) && <div className="request-decision-actions">
                  <button className="button small" onClick={() => decideRequest(row, true)}>Aceitar solicitação</button>
                  <button className="text-button" onClick={() => decideRequest(row, false)}>Devolver para ajustes</button>
                </div>}
                {kind === "requests" &&
                  row.status === "APPROVED" &&
                  session.data?.permissions.includes("vacancy.create") && (
                    <button
                      className="text-button"
                      onClick={() =>
                        setOperation({
                          title: "Criar vaga aprovada",
                          form: "vacancy",
                          initial: {
                            title: row.title,
                            org_unit_id: row.org_unit_id,
                            quantity: row.quantity,
                            recruiter_id: session.data?.user.id,
                            manager_id: row.requested_by,
                            audience: "EXTERNAL",
                            modality: "PRESENCIAL",
                            contract_type: "CLT",
                            details: {},
                            publish_on_save: Boolean(
                              session.data?.permissions.includes("vacancy.publish"),
                            ),
                          },
                          run: (data) =>
                            post(
                              "/vacancy-requests/" + row.id + "/vacancy",
                              data,
                            ),
                        })
                      }
                    >
                      Criar vaga
                    </button>
                  )}
                {kind === "requests" && Boolean(row.vacancy_id) && session.data?.permissions.includes("vacancy.view") && <Link className="text-button" to={(managerArea ? "/gestor/vagas/" : "/app/vagas/") + str(row.vacancy_id)}>Acompanhar vaga</Link>}
                {kind === "tests" && (
                  <button
                    className="text-button"
                    onClick={() =>
                      setOperation({
                        title: "Liberar teste para candidato",
                        form: "test-assignment",
                        run: (data) =>
                          post("/tests/" + row.id + "/assign", data),
                      })
                    }
                  >
                    Liberar teste
                  </button>
                )}
              </>
            )}
          />
        )}
      </div>}
      <OperationModal
        operation={operation}
        onClose={() => setOperation(null)}
      />
      <Modal
        open={Boolean(detail)}
        onOpenChange={(v) => !v && setDetail(null)}
        title={str(detail?.name ?? detail?.title ?? "Detalhes")}
      >
        {kind === "requests" && detail ? <VacancyRequestDetail request={query.data?.items.find(row => row.id === detail.id) ?? detail} /> : <RecordDetail value={query.data?.items.find(row => row.id === detail?.id) ?? detail ?? {}} />}
        {kind === "requests" && detail && canDecideRequest(query.data?.items.find(row => row.id === detail.id) ?? detail) && <div className="request-modal-actions">
          <button className="button" onClick={() => decideRequest(query.data?.items.find(row => row.id === detail.id) ?? detail, true)}>Aceitar solicitação</button>
          <button className="button secondary" onClick={() => decideRequest(query.data?.items.find(row => row.id === detail.id) ?? detail, false)}>Devolver para ajustes</button>
        </div>}
        {kind === "pools" && detail && <PoolMembers poolId={detail.id} />}
      </Modal>
    </>
  );
}
export function RecordDetail({ value }: { value: Record<string, unknown> }) {
  return (
    <dl className="record-detail">
      {Object.entries(value)
        .filter(
          ([key]) =>
            ![
              "id",
              "version",
              "created_by",
              "updated_at",
              "user_id",
              "storage_key",
              "profile_snapshot",
            ].includes(key),
        )
        .map(([key, val]) => (
          <div key={key}>
            <dt>{label(key)}</dt>
            <dd>
              {key === "status" ? (
                <Badge value={val} />
              ) : key.endsWith("_at") ? (
                date(val)
              ) : Array.isArray(val) ? (
                val.length ? (
                  val.map((v, i) => (
                    <div key={i}>
                      {typeof v === "object" ? (
                        <RecordDetail value={obj(v)} />
                      ) : (
                        str(v)
                      )}
                    </div>
                  ))
                ) : (
                  "—"
                )
              ) : typeof val === "object" && val ? (
                <RecordDetail value={obj(val)} />
              ) : typeof val === "boolean" ? (
                val ? (
                  "Sim"
                ) : (
                  "Não"
                )
              ) : (
                str(val) || "—"
              )}
            </dd>
          </div>
        ))}
    </dl>
  );
}
function PoolMembers({ poolId }: { poolId: string }) {
  const query = useQuery({
    queryKey: ["pool-members", poolId],
    queryFn: () => api<Collection>("/talent-pools/" + poolId + "/members"),
  });
  return (
    <section>
      <h3>Candidatos no banco</h3>
      <ErrorBox error={query.error} />
      <DataTable
        data={query.data?.items ?? []}
        columns={["name", "city", "state"]}
      />
    </section>
  );
}
