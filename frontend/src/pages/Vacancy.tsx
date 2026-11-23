import { RejectedCandidatesPanel } from "../components/RejectedCandidatesPanel";
import { RHWelcome } from "../components/RHWelcome";
import { BulkMovement } from "../components/ReviewActions";
import { CandidateCompatibility, CompatibilityRanking } from "../components/CandidateCompatibility";
import { VacancyConversation } from "../components/VacancyConversation";
import {
  ComparePanel,
  RediscoveryPanel,
} from "../components/CollaborationPanels";
import { approvalSchema, simpleSchema, submitSchema } from "../lib/forms";
import { useRef, useState } from "react";
import { isStageAdvanceDrag } from "../lib/stageDrag";
import { Link, useLocation, useParams } from "react-router-dom";
import {
  useQuery,
  useInfiniteQuery,
  useQueryClient,
} from "@tanstack/react-query";
import {
  DndContext,
  KeyboardSensor,
  PointerSensor,
  useDraggable,
  useDndMonitor,
  useDroppable,
  useSensor,
  useSensors,
  type DragEndEvent,
} from "@dnd-kit/core";
import { ArrowRight, BriefcaseBusiness, Clock3, GripVertical, Plus, Users, FileText, MessagesSquare, SlidersHorizontal, ListChecks, Search, GitCompareArrows } from "lucide-react";
import {
  api,
  post,
  put,
  obj,
  rows,
  str,
  type Collection,
  type Row,
} from "../lib/api";
import { useSession } from "../lib/session";
import { Badge, ErrorBox, PageTitle } from "../components/ui";
import { OperationModal, type Operation } from "./Resources";
import { VacancyInformation } from "../components/VacancyInformation";
import { ScoringModelSummary } from "../components/ScoringModelSummary";
import { PublicationChecklist } from "../components/PublicationChecklist";
import { ResumeScreening } from "../components/ResumeScreening";
import { ProfilePhoto } from "../components/ProfilePhoto";
import { StageReleaseActions } from "../components/StageReleaseActions";
import { CandidateStageActivity } from "../components/CandidateStageActivity";
import { VacancyQuestions } from "../components/VacancyQuestions";

function VacancyTabIcon({ name }: { name: string }) {
  const icons = { pipeline: Users, details: FileText, messages: MessagesSquare, scoring: SlidersHorizontal, checklist: ListChecks, compare: GitCompareArrows, rediscover: Search };
  const Icon = icons[name as keyof typeof icons] ?? FileText;
  return <Icon size={19} aria-hidden="true" />;
}

export function VacancyPage() {
  const currentLocation = useLocation();
  const managerArea = currentLocation.pathname.startsWith("/gestor/");
  const { id } = useParams();
  const client = useQueryClient();
  const session = useSession();
  const [tab, setTab] = useState(() => { const initial = new URLSearchParams(location.search).get("tab"); return initial === "messages" || initial === "scoring" ? initial : "screening"; });
  const [error, setError] = useState<unknown>();
  const [operation, setOperation] = useState<Operation | null>(null);
  const [suggestingCriteria, setSuggestingCriteria] = useState(false);
  const [filters, setFilters] = useState({ q: "", status: "", stage_id: "", start: "", end: "" });
  const vacancy = useQuery({
    queryKey: ["vacancy", id],
    queryFn: () => api<Row>("/vacancies/" + id),
  });
  const applications = useInfiniteQuery({
    queryKey: ["vacancy-applications", id, filters],
    initialPageParam: 1,
    queryFn: ({ pageParam }) =>
      api<Collection & { stage_counts?: Record<string, number> }>(
        "/applications?vacancy_id=" +
          id +
          "&page_size=100&page_number=" +
          pageParam + "&include_ranking=true&order_by=compatibility&" + new URLSearchParams({ q: filters.q, status: filters.status, stage_id: filters.stage_id,
            ...(filters.start ? { registered_from: new Date(filters.start + "T00:00:00").toISOString() } : {}),
            ...(filters.end ? { registered_to: new Date(filters.end + "T23:59:59").toISOString() } : {}) }),
      ),
    getNextPageParam: (last) =>
      last.page * last.page_size < last.total ? last.page + 1 : undefined,
    select: (data) => ({
      items: data.pages.flatMap((page) => page.items),
      total: data.pages[0]?.total ?? 0,
      stage_counts: data.pages[0]?.stage_counts ?? {},
    }),
    refetchInterval: 30000,
  });
  const can = (p: string) => session.data?.permissions.includes(p);
  const run = async (fn: () => Promise<unknown>) => {
    setError(undefined);
    try {
      await fn();
      await client.invalidateQueries();
    } catch (e) {
      setError(e);
    }
  };
  const extractCriteria = async () => {
    if (suggestingCriteria) return;
    setSuggestingCriteria(true);
    await run(async () => {
      const initial = await post<Record<string, unknown>>("/vacancies/" + id + "/suggest-compatibility-criteria", {});
      setOperation({ title: "Conferir critérios extraídos da descrição", form: "scoring", initial, submitLabel: "Aplicar critérios à vaga", run: data => post("/vacancies/" + id + "/scoring-models", data) });
    });
    setSuggestingCriteria(false);
  };
  if (vacancy.isPending) return <p role="status">Carregando vaga…</p>;
  if (!vacancy.data) return <>
    {!managerArea && <RHWelcome />}
    <section className="surface padded">
      <h2>Não foi possível abrir esta vaga</h2>
      <p>Ela pode ter sido removida ou seu acesso pode ter mudado. Volte à lista para consultar as vagas disponíveis.</p>
      <Link className="button" to={managerArea ? "/gestor/vagas" : "/app/vagas"}>Ir para a página de Vagas</Link>
      <details style={{marginTop: 20}}><summary>Ver detalhes do atendimento</summary><ErrorBox error={vacancy.error} /></details>
    </section>
  </>;
  const row = vacancy.data;
  const stages = rows(row.stages).filter(stage => !["OFFER", "HIRED"].includes(str(stage.kind)));
  const pipelineLocked = !["DRAFT", "APPROVED"].includes(str(row.status)) ||
    !applications.data || applications.data.total > 0;
  const models = rows(row.scoring_models);
  const editFields = [
    "title",
    "org_unit_id",
    "recruiter_id",
    "manager_id",
    "quantity",
    "audience",
    "confidential",
    "blind",
    "description",
    "city",
    "state",
    "modality",
    "contract_type",
    "deadline",
    "details",
  ];
  const editData = Object.fromEntries(editFields.map((k) => [k, row[k]]));
  return (
    <>
      <Link className="back-link" to="/app/vagas">
        ← Vagas
      </Link>
      <div className="vacancy-workspace-header surface"><p className="privacy-eyebrow">GESTÃO DO PROCESSO SELETIVO</p><PageTitle
        title={str(row.title)}
        subtitle={
          str(row.code) + " · " + str(row.city) + " / " + str(row.state)
        }
        actions={
          <>
            <Badge value={row.status} />
            <VacancyQuestions vacancyId={row.id} />
            {can("vacancy.edit") &&
              ["DRAFT", "APPROVED"].includes(str(row.status)) && (
                <button
                  className="button secondary"
                  onClick={() =>
                    setOperation({
                      title: "Editar vaga",
                      form: "vacancy",
                      initial: editData,
                      run: (data) =>
                        put("/vacancies/" + id, {
                          ...data,
                          version: row.version,
                        }),
                    })
                  }
                >
                  Editar vaga
                </button>
              )}
            {can("vacancy.publish") &&
              ["DRAFT", "APPROVED", "PAUSED"].includes(str(row.status)) && (
                <button
                  className="button"
                  onClick={() =>
                    run(() =>
                      post("/vacancies/" + id + "/status", {
                        version: row.version,
                        status: "PUBLISHED",
                      }),
                    )
                  }
                >
                  Publicar vaga
                </button>
              )}
            {row.status === "DRAFT" && can("vacancy.edit") && !can("vacancy.publish") && (
              <button
                className="button"
                onClick={() =>
                  setOperation({
                    title: "Enviar para aprovação",
                    schema: submitSchema,
                    run: (data) =>
                      post("/vacancies/" + id + "/status", {
                        ...data,
                        version: row.version,
                        status: "PENDING_APPROVAL",
                      }),
                  })
                }
              >
                Solicitar aprovação
              </button>
            )}
            {row.status === "PENDING_APPROVAL" && can("vacancy.approve") && (
              <button
                className="button"
                onClick={() =>
                  setOperation({
                    title: "Decidir publicação",
                    schema: approvalSchema,
                    run: (data) =>
                      post("/vacancies/" + id + "/approve", {
                        ...data,
                        version: row.version,
                      }),
                  })
                }
              >
                Decidir
              </button>
            )}
          </>
        }
      />
      <div className="vacancy-workspace-meta"><span>{Number(row.quantity)} {Number(row.quantity) === 1 ? "posição disponível" : "posições disponíveis"}</span>{Boolean(row.org_unit_name) && <span>Centro de custo: <strong>{str(row.org_unit_name)}</strong></span>}{Boolean(row.recruiter_name) && <span>RH responsável: <strong>{str(row.recruiter_name)}</strong></span>}</div></div>
      <ErrorBox error={error ?? applications.error} />
      <div className="tabs vacancy-workspace-tabs" role="tablist" aria-label="Áreas da vaga">
        {[
          ["screening", "Triagem de currículos"],
          ["pipeline", "Etapas da seleção"],
          ["details", "Detalhes da vaga"],
          ...((can("message.send") || can("request.create")) ? [["messages", "Mensagens gestor e RH"]] : []),
          ["scoring", "Modelo de aderência"],
          ["checklist", "Checklist de publicação"],
          ...(can("candidate.evaluate")
            ? [["compare", "Comparar candidatos"]]
            : []),
          ...(can("talent.manage")
            ? [["rediscover", "Redescobrir talentos"]]
            : []),
        ].map(([key, title]) => (
          <button
            role="tab"
            aria-selected={tab === key}
            className={tab === key ? "active" : ""}
            key={key}
            onClick={() => setTab(key)}
          >
            <VacancyTabIcon name={key} /><span>{title}</span>
          </button>
        ))}
      </div>
      {tab === "messages" && id && <VacancyConversation key={id} vacancyId={id} />}
      {tab === "screening" && <>
        {can("score.manage") && <aside className="surface padded criteria-from-description"><div><h2>Ranking baseado no que a vaga pede</h2><p>Extraia os requisitos profissionais da descrição, confira os critérios e os pesos e aplique à vaga.</p></div><div className="actions"><button className="button secondary" disabled={suggestingCriteria} onClick={() => void extractCriteria()}>{suggestingCriteria ? "Lendo descrição…" : "Extrair critérios da descrição"}</button><button className="text-button" onClick={() => setTab("scoring")}>Ver critérios atuais</button></div></aside>}
        <ResumeScreening key={str(id)} vacancyId={str(id)} stages={stages} />
      </>}
      {tab === "pipeline" && (
        <>
          <ErrorBox error={applications.error} />
          <section className="surface padded vacancy-board-controls"><div className="section-heading"><div><h2>Central de etapas e liberações</h2><p className="muted">Cada etapa reúne seus candidatos. Use <strong>Liberar</strong> para avançar e atualizar o acesso na área do candidato ou colaborador.</p></div><span className="vacancy-board-total">{applications.data?.total ?? 0} candidatura(s)</span></div>
          <div className="process-filters"><label className="field"><span>Buscar candidato</span><input placeholder="Digite o nome" value={filters.q} onChange={e => setFilters({ ...filters, q: e.target.value })} /></label>
            <label className="field"><span>Etapa</span><select value={filters.stage_id} onChange={e => setFilters({ ...filters, stage_id: e.target.value })}><option value="">Todas</option>{stages.map(stage => <option key={stage.id} value={stage.id}>{str(stage.name)}</option>)}</select></label>
            <label className="field"><span>Situação</span><select value={filters.status} onChange={e => setFilters({ ...filters, status: e.target.value })}><option value="">Todas</option><option value="ACTIVE">Em andamento</option><option value="RESERVE">Em reserva</option><option value="SELECTED">Selecionada</option><option value="REJECTED">Não selecionada</option><option value="WITHDRAWN">Desistência</option><option value="PRE_ADMISSION">Pré-admissão</option><option value="HIRED">Contratada</option></select></label>
            <label className="field"><span>Inscrições desde</span><input type="date" max={filters.end || undefined} value={filters.start} onChange={e => setFilters({ ...filters, start: e.target.value })} /></label><label className="field"><span>Inscrições até</span><input type="date" min={filters.start || undefined} value={filters.end} onChange={e => setFilters({ ...filters, end: e.target.value })} /></label>
            {Object.values(filters).some(Boolean) && <button className="text-button" onClick={() => setFilters({ q: "", status: "", stage_id: "", start: "", end: "" })}>Limpar filtros</button>}
          </div>
          </section>
          <Kanban
            vacancyId={str(id)}
            stages={filters.stage_id ? stages.filter(stage => stage.id === filters.stage_id) : stages}
            allStages={stages}
            stageCounts={applications.data?.stage_counts ?? {}}
            applications={applications.data?.items ?? []}
            canMove={Boolean(can("candidate.move"))}
            onMove={async (application, stageId) =>
              run(() =>
                post("/applications/" + application.id + "/move", {
                  stage_id: stageId,
                  version: application.version,
                }),
              )
            }
          />
          {applications.hasNextPage && (
            <button
              className="button secondary"
              disabled={applications.isFetchingNextPage}
              onClick={() => void applications.fetchNextPage()}
            >
              Carregar mais candidaturas
            </button>
          )}
          <details className="surface padded vacancy-extra-tools"><summary>Comparar candidatos e configurar a vaga</summary>
          {can("score.manage") && <div className="actions">
            <button className="button secondary" onClick={() => setTab("scoring")}>Configurar critérios e pesos</button>
            <button className="button secondary" disabled={suggestingCriteria} onClick={() => void extractCriteria()}>{suggestingCriteria ? "Lendo descrição…" : "Extrair critérios da descrição"}</button>
            {models.length > 0 && <button className="button secondary" onClick={() => setOperation({
              title: "Faixas de compatibilidade",
              schema: simpleSchema({ moderate: { type: "number", title: "Compatibilidade moderada a partir de (%)", minimum: 1, maximum: 98, default: 60 }, high: { type: "number", title: "Alta compatibilidade a partir de (%)", minimum: 2, maximum: 100, default: 80 }, reason: { type: "string", title: "Motivo da alteração", minLength: 5 } }),
              run: data => { const model = models[0]; if (Number(data.moderate) >= Number(data.high)) throw new Error("A faixa alta deve começar acima da moderada."); return post("/vacancies/" + id + "/scoring-models", { criteria: model.criteria, composition: model.composition, bands: [{ key: "low", min: 0, max: Number(data.moderate) }, { key: "moderate", min: Number(data.moderate), max: Number(data.high) }, { key: "high", min: Number(data.high), max: 100 }], reason: data.reason }); },
            })}>Configurar faixas de pontuação</button>}
            <button className="button secondary" onClick={() => setOperation({
              title: "Atualizar compatibilidade dos candidatos",
              schema: simpleSchema({ reason: { type: "string", title: "Motivo da atualização", minLength: 10 } }),
              run: data => post("/vacancies/" + id + "/recalculate-compatibility", data),
            })}>Atualizar porcentagens</button>
          </div>}
          <CompatibilityRanking applications={applications.data?.items ?? []} total={applications.data?.total ?? 0} vacancyTitle={str(row.title)} />
          <div className="section-toolbar vacancy-candidate-toolbar">
            <span>{applications.data?.total ?? 0} candidaturas</span>
            {can("vacancy.edit") && obj(row.details).structured_workflow !== true && <button className="button secondary small" onClick={() => setOperation({ title: "Ativar fluxo completo", schema: { type: "object", description: "Inclui Perguntas e ficha externa e exige avaliações antes dos avanços. Os candidatos permanecem nas etapas atuais.", properties: {} }, submitLabel: "Ativar fluxo completo", run: () => post("/vacancies/" + id + "/structured-workflow", { version: row.version }) })}>Ativar fluxo completo</button>}
            {can("vacancy.edit") && <button className="button secondary small" onClick={() => setOperation({
              title: "Liberação das atividades por etapa",
              schema: simpleSchema({ phases: { type: "object", title: "Etapas da vaga", properties: Object.fromEntries(stages.map((stage, index) => [stage.id, {
                type: "string", title: `${index + 1}. ${str(stage.name)}`, enum: ["REGISTER", "RECRUITMENT", "SELECTION", "FORM", "INTERVIEW", "TEST", "ADMISSION"],
              }])) } }),
              initial: { phases: Object.fromEntries(stages.map((stage, index) => [stage.id, stage.candidate_phase ?? (stage.kind === "INTERVIEW" || stage.kind === "TEST" ? stage.kind : ["FINALIST", "OFFER", "HIRED"].includes(str(stage.kind)) ? "ADMISSION" : index === 0 ? "RECRUITMENT" : "SELECTION")])) },
              run: data => put("/vacancies/" + id + "/candidate-flow", { ...data, version: row.version }),
            })}>Liberação por etapas</button>}
            {can("vacancy.edit") && (
              <button
                className="button secondary small"
                disabled={pipelineLocked}
                title={pipelineLocked ? "As etapas só podem ser configuradas antes da publicação e sem candidaturas." : undefined}
                onClick={() =>
                  setOperation({
                    title: "Configurar pipeline",
                    form: "pipeline",
                    initial: {
                      version: row.version,
                      stages: stages.map((s) =>
                        Object.fromEntries(
                          [
                            "name",
                            "position",
                            "kind",
                            "candidate_phase",
                            "required",
                            "reveal_identity",
                            "sla_hours",
                            "rules",
                          ].map((k) => [k, s[k]]),
                        ),
                      ),
                    },
                    run: (data) =>
                      put("/vacancies/" + id + "/pipeline", {
                        ...data,
                        version: row.version,
                      }),
                  })
                }
              >
                Configurar etapas
              </button>
            )}
          </div>
          {pipelineLocked && <p className="muted">As etapas só podem ser configuradas antes da publicação e sem candidaturas.</p>}
          <BulkMovement
            applications={applications.data?.items ?? []}
            stages={stages}
          />
          </details>
        </>
      )}
      {tab === "details" && (
        <section className="surface padded">
          <VacancyInformation vacancy={row} />
          <div className="actions">
            {can("vacancy.create") && (
              <button
                className="button secondary"
                onClick={() =>
                  run(async () => {
                    const result = await post<Row>(
                      "/vacancies/" + id + "/clone",
                    );
                    location.assign("/app/vagas/" + result.id);
                  })
                }
              >
                Clonar vaga
              </button>
            )}
            {can("vacancy.edit") &&
              ["PUBLISHED", "PAUSED", "CLOSED"].includes(str(row.status)) && (
                <button
                  className="button secondary"
                  onClick={() =>
                    setOperation({
                      title: "Alterar situação da vaga",
                      schema: simpleSchema({
                        status: {
                          enum:
                            row.status === "CLOSED"
                              ? ["DRAFT", "ARCHIVED"]
                              : row.status === "PUBLISHED"
                                ? ["PAUSED", "CLOSED", "CANCELED"]
                                : ["CLOSED", "CANCELED"],
                        },
                        reason: { type: "string", title: "Motivo" },
                      }),
                      run: (data) =>
                        post("/vacancies/" + id + "/status", {
                          ...data,
                          version: row.version,
                        }),
                    })
                  }
                >
                  Alterar situação
                </button>
              )}
          </div>
        </section>
      )}
      {tab === "scoring" && (
        <section className="surface padded">
          <div className="section-heading">
            <div>
              <h2>Como os candidatos serão avaliados</h2>
              <p className="muted">
                Use a descrição da vaga como base. Confira cada requisito, o trecho que o justifica e quanto ele pesa na compatibilidade.
              </p>
            </div>
            {can("score.manage") && (
              <button
                className="button"
                onClick={() =>
                  setOperation({
                    title: "Configurar critérios de avaliação",
                    form: "scoring",
                    run: (data) =>
                      post("/vacancies/" + id + "/scoring-models", data),
                  })
                }
              >
                <Plus size={16} />
                Configurar avaliação
              </button>
            )}
          </div>
          {can("score.manage") && <div className="actions"><button className="button secondary" disabled={suggestingCriteria} onClick={() => void extractCriteria()}>{suggestingCriteria ? "Lendo descrição…" : "Extrair critérios da descrição"}</button>{models.length > 0 && <button className="button secondary" onClick={() => void run(() => post("/vacancies/" + id + "/recalculate-compatibility", { reason: "Atualização do ranking com os critérios profissionais revisados pelo RH." }))}>Atualizar ranking com estes critérios</button>}</div>}
          <ScoringModelSummary models={models} />
        </section>
      )}
      {tab === "checklist" && <PublicationChecklist vacancy={row} onNavigate={setTab} />}
      {tab === "compare" && id && (
        <ComparePanel
          vacancyId={id}
          applications={applications.data?.items ?? []}
        />
      )}
      {tab === "rediscover" && id && <RediscoveryPanel vacancyId={id} />}
      <OperationModal
        operation={operation}
        onClose={() => setOperation(null)}
      />
    </>
  );
}
function Kanban({
  vacancyId,
  stages: pipelineStages,
  allStages,
  stageCounts,
  applications,
  canMove,
  onMove,
}: {
  vacancyId: string;
  stages: Row[];
  allStages: Row[];
  stageCounts: Record<string, number>;
  applications: Row[];
  canMove: boolean;
  onMove: (row: Row, id: string) => Promise<unknown>;
}) {
  const stages = pipelineStages.filter(stage => !["OFFER", "HIRED"].includes(str(stage.kind)));
  const [rejectedPage, setRejectedPage] = useState(1);
  const rejected = useQuery({ queryKey: ["vacancy-rejected", vacancyId, rejectedPage], queryFn: () => api<Collection>(`/applications?vacancy_id=${vacancyId}&status=REJECTED&page_size=25&page_number=${rejectedPage}`), refetchInterval: 15000 });
  const [onlyOccupied, setOnlyOccupied] = useState(true);
  const [focusedStage, setFocusedStage] = useState<string | null>();
  const occupied = stages.filter(stage => (stageCounts[stage.id] ?? 0) > 0);
  const available = onlyOccupied ? occupied : stages;
  const selectedStage = focusedStage === undefined
    ? (occupied.find(stage => applications.some(row => row.stage_id === stage.id && ["ACTIVE", "RESERVE"].includes(str(row.status))))?.id ?? occupied[0]?.id ?? null)
    : focusedStage;
  const visible = selectedStage && stages.some(stage => stage.id === selectedStage)
    ? stages.filter(stage => stage.id === selectedStage) : available;
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 6 } }),
    useSensor(KeyboardSensor),
  );
  const dragEnd = (event: DragEndEvent) => {
    const dragged = applications.find(row => row.id === event.active.id);
    const index = dragged ? allStages.findIndex(stage => stage.id === dragged.stage_id) : -1;
    const next = index >= 0 ? allStages[index + 1] : undefined;
    if (dragged && isStageAdvanceDrag(event.delta, event.over ? String(event.over.id) : null, str(dragged.stage_id), next?.id)) return;
    if (event.over && canMove) {
      const row = applications.find((a) => a.id === event.active.id);
      if (row && row.stage_id !== event.over.id)
        void onMove(row, String(event.over.id));
    }
  };
  return (
    <DndContext sensors={sensors} onDragEnd={dragEnd}>
      <div className="stage-board-overview"><div className="stage-board-overview-title"><h2>Candidatos por etapa</h2><p>Aprove o currículo e libere a próxima atividade diretamente no cartão.</p><div className="stage-board-totals"><span><Users size={17} aria-hidden="true" /><strong>{Object.values(stageCounts).reduce((sum, count) => sum + count, 0)}</strong> candidaturas</span><span><BriefcaseBusiness size={17} aria-hidden="true" /><strong>{occupied.length}</strong> etapas com candidatos</span></div></div><label className="check-field"><input type="checkbox" checked={onlyOccupied} onChange={event => setOnlyOccupied(event.target.checked)} />Ocultar etapas vazias</label></div>
      <nav className="stage-board-navigation" aria-label="Escolher etapa da seleção">
        <button type="button" aria-pressed={!selectedStage} onClick={() => setFocusedStage(null)}>Visão geral</button>
        {stages.map(stage => <button type="button" key={stage.id} aria-pressed={selectedStage === stage.id} onClick={() => setFocusedStage(stage.id)}><small>Etapa {Number(stage.position ?? allStages.findIndex(item => item.id === stage.id)) + 1}</small><span>{str(stage.name)}</span><strong>{stageCounts[stage.id] ?? 0}</strong></button>)}
        <button type="button" className="stage-rejected-tab" aria-pressed={selectedStage === "__rejected"} onClick={() => setFocusedStage("__rejected")}><span>Não selecionados</span><strong>{rejected.data?.total ?? 0}</strong></button>
      </nav>
      {selectedStage === "__rejected" && <><ErrorBox error={rejected.error} /><RejectedCandidatesPanel data={rejected.data} pending={rejected.isPending} page={rejectedPage} onPage={setRejectedPage} /></>}
      {selectedStage !== "__rejected" && <div className={"kanban vacancy-stage-board stage-board-organized stage-board-dynamic" + (selectedStage ? " single-stage" : "") + (onlyOccupied ? " is-focused" : "")} role="region" aria-label="Candidatos organizados por etapa">
        {visible.map((stage) => (
          <Column
            key={stage.id}
            stage={stage}
            total={stageCounts[stage.id] ?? 0}
            applications={applications.filter((a) => a.stage_id === stage.id)}
            allStages={allStages}
            canMove={canMove}
            onMove={onMove}
          />
        ))}
      </div>}
      {selectedStage !== "__rejected" && onlyOccupied && !occupied.length && <p className="alert">Nenhuma etapa tem candidaturas nos filtros atuais. Desmarque a opção acima para ver o fluxo completo.</p>}
      {!stages.length && (
        <div className="empty">
          <h3>Configure as etapas deste processo</h3>
          <p>O pipeline define a jornada e os prazos da candidatura.</p>
        </div>
      )}
    </DndContext>
  );
}
function Column({
  stage,
  total,
  applications,
  allStages,
  canMove,
  onMove,
}: {
  stage: Row;
  total: number;
  applications: Row[];
  allStages: Row[];
  canMove: boolean;
  onMove: (row: Row, id: string) => Promise<unknown>;
}) {
  const { setNodeRef, isOver } = useDroppable({ id: stage.id });
  const closedStatuses = ["REJECTED", "WITHDRAWN", "HIRED"];
  const current = applications.filter(row => !closedStatuses.includes(str(row.status)));
  const closed = applications.filter(row => closedStatuses.includes(str(row.status)));
  return (
    <section
      ref={setNodeRef}
      className={"kanban-column " + (!total ? "is-empty " : "has-candidates ") + (isOver ? "drag-over" : "")}
    >
      <header>
        <div><small className="stage-order-label">ETAPA {Number(stage.position ?? allStages.findIndex(item => item.id === stage.id)) + 1}</small><h3>{str(stage.name)}</h3></div>
        <span title="Total de candidaturas nesta etapa para os filtros selecionados">{total}</span>
      </header>
      <p className="stage-sla"><Clock3 size={13} aria-hidden="true" />Prazo: {Number(stage.sla_hours) % 24 === 0 ? `${Number(stage.sla_hours) / 24} dia(s)` : `${str(stage.sla_hours)} horas`}</p>
      <div className="kanban-candidates">
      {current.map((row) => (
        <ApplicationCard
          key={row.id}
          row={row}
          stages={allStages}
          canMove={canMove}
          onMove={onMove}
        />
      ))}
      {closed.length > 0 && <details className="stage-closed-candidates"><summary>Encerradas nesta etapa <span>{closed.length}</span></summary><div>{closed.map(row => <ApplicationCard key={row.id} row={row} stages={allStages} canMove={false} onMove={onMove} />)}</div></details>}
      {!applications.length && (
        <div className="column-empty"><Users size={25} aria-hidden="true" /><p>{total ? "Carregue mais candidaturas para visualizar esta etapa." : "Nenhum candidato nesta etapa"}</p>{canMove && !total && <small>Arraste um cartão para cá ou use “Mover para”.</small>}</div>
      )}
      </div>
    </section>
  );
}
function ApplicationCard({
  row,
  stages,
  canMove,
  onMove,
}: {
  row: Row;
  stages: Row[];
  canMove: boolean;
  onMove: (row: Row, id: string) => Promise<unknown>;
}) {
  const advanceRef = useRef<{ open: () => void }>(null);
  const index = stages.findIndex(stage => stage.id === row.stage_id);
  const next = index >= 0 ? stages[index + 1] : undefined;
  const draggable = canMove && ["ACTIVE", "RESERVE"].includes(str(row.status));
  useDndMonitor({ onDragEnd: event => {
    if (draggable && event.active.id === row.id && isStageAdvanceDrag(event.delta, event.over ? String(event.over.id) : null, str(row.stage_id), next?.id)) advanceRef.current?.open();
  } });
  const { attributes, listeners, setNodeRef, transform, isDragging } =
    useDraggable({ id: row.id, disabled: !draggable });
  return (
    <article
      ref={setNodeRef}
      style={
        transform
          ? {
              transform:
                "translate(" + transform.x + "px," + transform.y + "px)",
              zIndex: 5,
            }
          : undefined
      }
      className={"candidate-card " + (isDragging ? "dragging" : "")}
    >
      <div className="candidate-card-top">
        {!obj(row.candidate).blind && row.candidate_id ? <ProfilePhoto candidateId={str(row.candidate_id)} name={str(obj(row.candidate).name)} /> : <span className="avatar">{str(obj(row.candidate).name).replace(/^\[TESTE\]\s*/, "").slice(0, 1)}</span>}
        <div className="stage-card-identity"><Link to={"/app/candidaturas/" + row.id}><h4>{str(obj(row.candidate).name)}</h4></Link><p>{str(obj(row.candidate).city) || "Perfil profissional"}</p></div>
        {draggable && (
          <button
            className="drag-handle"
            aria-label="Mover candidato"
            title="Arraste para a direita para liberar a próxima etapa"
            style={{ touchAction: "none" }}
            {...attributes}
            {...listeners}
          >
            <GripVertical size={17} />
          </button>
        )}
      </div>
      <Badge value={row.status} />
      {typeof row.compatibility_rank === "number" && row.compatibility_rank <= 3 && <span className={"stage-candidate-rank rank-" + row.compatibility_rank}>{row.compatibility_rank}º lugar na vaga</span>}
      <CandidateCompatibility row={row} />
      <CandidateStageActivity application={row} />
      {draggable && next && <small className="stage-swipe-hint"><ArrowRight size={14} aria-hidden="true" />Arraste pela alça para a direita para avançar</small>}
      <StageReleaseActions application={row} stages={stages} advanceRef={advanceRef} />
      {canMove && (
        <details className="stage-manual-move"><summary>Ajustar etapa manualmente</summary><label className="field move-select">
          <span>Mover para</span>
          <select
            value={str(row.stage_id)}
            onChange={(e) => void onMove(row, e.target.value)}
          >
            {stages.map((stage) => (
              <option key={stage.id} value={stage.id}>
                {str(stage.name)}
              </option>
            ))}
          </select>
        </label></details>
      )}
      <Link className="stage-card-open" to={"/app/candidaturas/" + row.id}>Abrir candidatura<ArrowRight size={15} aria-hidden="true" /></Link>
    </article>
  );
}
