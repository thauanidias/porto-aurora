import { VacancyHealthCards } from "../components/VacancyHealthCards";
import { EmailSettingsPanel } from "../components/EmailSettingsPanel";
import { RHWorkflowGuide } from "../components/RHWorkflow";
import { label } from "../lib/labels";
import {
  ConfigHistory,
  RoleControls,
  UserAccess,
} from "../components/AdminExtras";
import { ReportBuilder } from "./Reporting";
import { simpleSchema } from "../lib/forms";
import { useState } from "react";
import { Check, Circle, Plus, Search, Settings2 } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
} from "recharts";
import {
  ArrowUpRight,
  ArrowRight,
  Info,
  ClipboardList,
  BriefcaseBusiness,
  CheckCircle2,
  Clock3,
  Users,
} from "lucide-react";
import { Link, Navigate } from "react-router-dom";
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
import { DataTable, Empty, ErrorBox, PageTitle } from "../components/ui";
import { type Schema } from "../components/SchemaForm";
import { OperationModal, RecordDetail, type Operation } from "./Resources";

export function Dashboard() {
  const session = useSession();
  const can = session.data?.permissions.includes("report.view");
  const query = useQuery({
    queryKey: ["dashboard"],
    queryFn: () => api<Record<string, unknown>>("/dashboard"),
    enabled: Boolean(can),
  });
  const canViewCandidates = Boolean(session.data?.permissions.includes("candidate.view"));
  const registered = useQuery({
    queryKey: ["dashboard-registered-candidates"],
    queryFn: () => api<Collection>("/candidates?page_size=1"),
    enabled: Boolean(can) && canViewCandidates,
  });
  if (session.data?.permissions.includes("request.create") && !session.data.permissions.includes("vacancy.create") && !session.data.permissions.includes("request.approve")) return <Navigate to="/app/vagas" replace />;
  if (!can)
    return (
      <>
        <PageTitle
          title="Seu espaço de trabalho"
          subtitle="Acesse suas solicitações e atividades pelo menu."
        />
        <Link className="button" to="/app/trabalho">
          Ver meu trabalho
        </Link>
        <RHWorkflowGuide />
      </>
    );
  const data = query.data ?? {};
  const canViewVacancies = session.data?.permissions.includes("vacancy.view");
  const groupedStages = new Map<string, { name: string; count: number }>();
  for (const stage of rows(data.stage_counts)) {
    const name = str(stage.name).trim();
    const key = name.toLocaleLowerCase("pt-BR");
    const previous = groupedStages.get(key);
    groupedStages.set(key, { name, count: (previous?.count ?? 0) + Number(stage.count ?? 0) });
  }
  const stages = [...groupedStages.values()];
  const occupiedStages = stages.filter(stage => stage.count > 0);
  const emptyStages = stages.filter(stage => stage.count === 0);
  return (
    <div className="rh-overview-v2">
      <header className="dashboard-overview-header">
        <div>
          <h1>Painel do RH</h1>
          <p>Olá, {str(session.data?.user.name.split(" ")[0])}. Acesse suas vagas, candidatos e tarefas.</p>
        </div>
      </header>
      <ErrorBox error={query.error} />
      <ErrorBox error={registered.error} />
      <nav className="rh-overview-shortcuts" aria-label="Ações do recrutamento">
        {canViewVacancies && <Link to="/app/vagas"><BriefcaseBusiness size={20} aria-hidden="true" /><span><strong>Gerenciar vagas</strong><small>Inscrições e andamento da seleção</small></span><ArrowRight size={17} aria-hidden="true" /></Link>}
        {canViewCandidates && <Link to="/app/candidatos"><Users size={20} aria-hidden="true" /><span><strong>Consultar candidatos</strong><small>Perfis, currículos e informações</small></span><ArrowRight size={17} aria-hidden="true" /></Link>}
        <Link to="/app/trabalho"><ClipboardList size={20} aria-hidden="true" /><span><strong>Organizar meu trabalho</strong><small>Tarefas e próximas ações</small></span><ArrowRight size={17} aria-hidden="true" /></Link>
      </nav>
      <div className="dashboard-overview-metrics rh-essential-metrics" aria-label="Indicadores essenciais" aria-busy={query.isPending}>
        {[
          { name: "Vagas abertas", key: "open_vacancies", Icon: BriefcaseBusiness, tone: "vacancies" },
          { name: "Candidaturas em andamento", key: "active_candidates", Icon: Users, tone: "applications" },
          { name: "Aprovações pendentes", key: "pending_approval", Icon: Clock3, tone: "pending" },
        ].map(({ name, key, Icon, tone }) => <section key={key} className={"dashboard-stat stat-" + tone}><div className="dashboard-stat-top"><span className="dashboard-stat-icon"><Icon size={20} aria-hidden="true" /></span><h2>{name}</h2></div><strong className="dashboard-stat-value">{query.data ? Number(data[key] ?? 0).toLocaleString("pt-BR") : "—"}</strong></section>)}
      </div>
      {Number(data.overdue_tasks ?? 0) > 0 && <div className="dashboard-task-summary has-pending"><span className="dashboard-task-icon"><ClipboardList size={22} aria-hidden="true" /></span><div><strong>{str(data.overdue_tasks)} tarefa(s) com prazo vencido</strong></div><Link className="text-button" to="/app/trabalho">Ver tarefas<ArrowRight size={16} aria-hidden="true" /></Link></div>}
      <details className="surface padded rh-dashboard-extra"><summary>Ver indicadores e informações complementares</summary>
      <Link className="button secondary small" to="/app/relatorios">Ver relatórios<ArrowUpRight size={17} aria-hidden="true" /></Link>
      <div className="rh-overview-section-title"><h2>Resumo dos processos</h2><span>Dados das vagas disponíveis para seu acesso</span></div>
      <div className="dashboard-overview-metrics" aria-label="Resumo do recrutamento" aria-busy={query.isPending}>
        {canViewCandidates && <section className="dashboard-stat stat-people">
          <div className="dashboard-stat-top"><span className="dashboard-stat-icon"><Users size={20} aria-hidden="true" /></span><h2>Pessoas cadastradas</h2></div>
          <strong className="dashboard-stat-value">{registered.data ? registered.data.total.toLocaleString("pt-BR") : "—"}</strong>
          <p>Perfis disponíveis para consulta.</p>
          <Link className="dashboard-stat-link" to="/app/candidatos">Ver candidatos <ArrowRight size={16} aria-hidden="true" /></Link>
        </section>}
        {[
          { name: "Vagas publicadas", key: "open_vacancies", Icon: BriefcaseBusiness, description: "Oportunidades abertas a inscrições.", tone: "vacancies" },
          { name: "Inscrições em andamento", key: "active_candidates", Icon: Users, description: "Candidaturas em processos ativos.", tone: "applications" },
          { name: "Aguardando aprovação", key: "pending_approval", Icon: Clock3, description: "Vagas que precisam de uma decisão.", tone: "pending" },
          { name: "Contratações concluídas", key: "hired", Icon: CheckCircle2, description: "Processos finalizados com contratação.", tone: "hired" },
          { name: "Entrevistas agendadas", key: "scheduled_interviews", Icon: Clock3, description: "Agendamentos futuros confirmados.", tone: "pending" },
          { name: "Testes pendentes", key: "pending_tests", Icon: ClipboardList, description: "Avaliações ainda sem correção concluída.", tone: "pending" },
          { name: "Pessoas aprovadas", key: "approved_candidates", Icon: CheckCircle2, description: "Selecionadas, em pré-admissão ou contratadas.", tone: "hired" },
          { name: "Não selecionadas", key: "rejected_candidates", Icon: Users, description: "Candidaturas encerradas sem seleção.", tone: "applications" },
        ].map(({ name, key, Icon, description, tone }) => (
          <section key={key} className={"dashboard-stat stat-" + tone}>
            <div className="dashboard-stat-top"><span className="dashboard-stat-icon"><Icon size={20} aria-hidden="true" /></span><h2>{name}</h2></div>
            <strong className="dashboard-stat-value">{!query.data ? "—" : Number(data[key] ?? 0).toLocaleString("pt-BR")}</strong>
            <p>{description}</p>
            {key === "open_vacancies" && canViewVacancies && <Link className="dashboard-stat-link" to="/app/vagas">Gerenciar vagas <ArrowRight size={16} aria-hidden="true" /></Link>}
            {key === "pending_approval" && query.data && <span className="dashboard-stat-status">{Number(data[key] ?? 0) === 0 ? "Nenhuma aprovação pendente" : "Atenção às aprovações"}</span>}
          </section>
        ))}
      </div>
      <div className="dashboard-overview-note"><Info size={17} aria-hidden="true" /><p>Cadastro não é candidatura. As inscrições são contabilizadas quando a pessoa se candidata a uma vaga.</p></div>
      <details className="rh-overview-help surface"><summary><span><strong>Precisa de ajuda para conduzir a seleção?</strong><small>Consulte o guia com as 7 etapas do processo.</small></span><span className="rh-overview-help-label">Ver passo a passo</span></summary><RHWorkflowGuide /></details>
      <section className="surface padded process-dashboard simplified-stage-summary"><h2>Onde estão os candidatos?</h2><p className="muted">Candidaturas ativas e em reserva, somadas entre as vagas. Etapas com o mesmo nome aparecem uma única vez.</p>
        <div className="process-stage-counts">{occupiedStages.map(stage => <div key={stage.name}><strong>{stage.count}</strong><span>{stage.name}<small>{stage.count === 1 ? "candidatura nesta etapa" : "candidaturas nesta etapa"}</small></span></div>)}</div>
        {!occupiedStages.length && <p className="muted">{query.isPending ? "Carregando candidaturas…" : "Nenhuma candidatura ativa ou em reserva nas etapas."}</p>}
        {emptyStages.length > 0 && <details className="empty-stage-details"><summary>Ver {emptyStages.length} etapas sem candidatos</summary><ul>{emptyStages.map(stage => <li key={stage.name}>{stage.name} <span>0 candidaturas</span></li>)}</ul></details>}
      </section>
      <VacancyHealthCards vacancies={rows(data.vacancy_health)} canOpen={Boolean(canViewVacancies)} loading={query.isPending} failed={Boolean(query.error)} />
      <div className={"dashboard-task-summary" + (Number(data.overdue_tasks ?? 0) > 0 ? " has-pending" : "")}>
        <span className="dashboard-task-icon"><ClipboardList size={22} aria-hidden="true" /></span>
        <div><strong>{!query.data ? "Acompanhamento de tarefas" : Number(data.overdue_tasks ?? 0) > 0 ? str(data.overdue_tasks) + " tarefa(s) com prazo vencido" : "Nenhuma tarefa com prazo vencido"}</strong><p>Organize as próximas ações dos seus processos.</p></div>
        <Link className="text-button" to="/app/trabalho">Ver minhas tarefas <ArrowRight size={16} aria-hidden="true" /></Link>
      </div>
      <details className="dashboard-more surface padded">
      <summary>Ver indicadores detalhados de candidaturas e prazos</summary>
      <div className="dashboard-grid dashboard-analysis">
        <section className="surface padded">
          <h2>Situação das candidaturas</h2>
          <p className="muted">Quantidade de inscrições em cada situação do processo seletivo.</p>
          {rows(data.funnel).length ? (
            <ResponsiveContainer width="100%" height={270}>
              <BarChart
                data={rows(data.funnel).map((item) => ({
                  ...item,
                  name: label(str(item.name)),
                }))}
                layout="vertical"
                margin={{ left: 20, right: 20 }}
              >
                <CartesianGrid strokeDasharray="3 3" horizontal={false} />
                <XAxis type="number" allowDecimals={false} />
                <YAxis dataKey="name" type="category" width={130} />
                <Tooltip />
                <Bar
                  dataKey="value"
                  name="Candidaturas"
                  fill="var(--brand)"
                  radius={[0, 4, 4, 0]}
                />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <Empty title={query.isPending ? "Carregando candidaturas…" : query.error ? "Não foi possível carregar as candidaturas" : "Nenhuma candidatura enviada ainda"}>
              {!query.isPending && !query.error && <p>Os cadastros de conta não entram neste gráfico. Ele será atualizado quando uma candidatura for enviada.</p>}
            </Empty>
          )}
        </section>
        <section className="surface padded">
          <h2>Prazos e pendências</h2>
          <div className="timing-row">
            <span>Da publicação ao encerramento da vaga</span>
            <strong>
              {obj(data.time_to_fill).mean == null ? <small>Aguardando dados</small> : <>{str(obj(data.time_to_fill).mean)} <small>dias em média</small></>}
            </strong>
          </div>
          <div className="timing-row">
            <span>Da candidatura ao aceite da oferta</span>
            <strong>
              {obj(data.time_to_hire).median == null ? <small>Aguardando dados</small> : <>{str(obj(data.time_to_hire).median)} <small>dias (mediana)</small></>}
            </strong>
          </div>
          <div className="timing-row">
            <span>Suas tarefas com prazo vencido</span>
            <strong>{query.data ? str(data.overdue_tasks ?? 0) : "—"}</strong>
          </div>
          <details>
            <summary>Como são calculados?</summary>
            <p>A média considera o tempo entre publicação e encerramento das vagas. A mediana é o valor central dos tempos entre candidatura e aceite da oferta. Sem processos concluídos, os indicadores aguardam dados.</p>
          </details>
          <Link className="text-button" to="/app/trabalho">Ver minhas tarefas →</Link>
        </section>
      </div>
      </details>
      </details>
    </div>
  );
}
const catalogNames: Record<string, string> = {
  "vacancy-templates": "Templates de vaga",
  workflows: "Fluxos de aprovação",
  pipelines: "Templates de pipeline",
  "privacy-notices": "Avisos de privacidade",
  "retention-policies": "Políticas de retenção",
  "message-templates": "Templates de comunicação",
  scorecards: "Fichas de avaliação",
  "interview-templates": "Roteiros de entrevista",
  checklists: "Checklists de pré-admissão",
  surveys: "Pesquisas de satisfação",
  automations: "Automações",
  "saved-reports": "Relatórios salvos",
  "document-types": "Tipos de documento",
  skills: "Competências",
  tags: "Tags",
  "closure-reasons": "Motivos de encerramento",
  branding: "Identidade institucional",
};

export function SettingsPage() {
  const [kind, setKind] = useState("smtp");
  const [search, setSearch] = useState("");
  const [operation, setOperation] = useState<Operation | null>(null);
  const [selected, setSelected] = useState<Row | null>(null);
  const [error] = useState<unknown>();
  const schemas = useQuery({
    queryKey: ["config-schemas"],
    queryFn: () => api<Record<string, Schema>>("/configuration/schemas"),
  });
  const records = useQuery({
    queryKey: ["configuration", kind],
    queryFn: () => api<Collection>("/configuration/" + kind),
    enabled: kind !== "smtp",
  });
  const system = useQuery({
    queryKey: ["settings"],
    queryFn: () => api<Record<string, unknown>>("/settings"),
  });
  const schema = schemas.data?.[kind];
  const configure = (row?: Row) => {
    if (!schema) return;
    setOperation({
      title: row
        ? "Editar " + catalogNames[kind]
        : "Criar " + catalogNames[kind],
      schema: {
        type: "object",
        $defs: schema.$defs,
        properties: {
          name: { type: "string", title: "Nome" },
          data: { ...schema, title: catalogNames[kind] },
          active: { type: "boolean", default: true, title: "Ativo" },
          reason: { type: "string", title: "Justificativa da configuração" },
        },
      },
      initial: row
        ? { name: row.name, data: row.data, active: row.active, reason: "" }
        : undefined,
      run: (data) =>
        row
          ? put("/configuration/" + kind + "/" + row.id, {
              ...data,
              version: row.version,
            })
          : post("/configuration/" + kind, data),
    });
  };
  return (
    <>
      <PageTitle
        title="Configurações"
        subtitle="Configure os canais de comunicação, os fluxos e os critérios dos processos."
      />
      <div className="settings-status settings-overview">
        <span>
          Ambiente <strong>{str(system.data?.environment) || "Carregando…"}</strong>
        </span>
        <span>
          E-mails · SMTP
          <strong className={system.data?.smtp ? "integration-on" : "integration-off"}>{system.data?.smtp ? <Check size={14} /> : <Circle size={12} />}{!system.data ? "Carregando…" : system.data.smtp ? "Habilitado" : "Desabilitado"}</strong>
        </span>
        <span>
          Acesso de rede · AD / LDAP
          <strong className={system.data?.ldap ? "integration-on" : "integration-off"}>{system.data?.ldap ? <Check size={14} /> : <Circle size={12} />}{!system.data ? "Carregando…" : system.data.ldap ? "Habilitado" : "Desabilitado"}</strong>
        </span>
        <span>
          Calendário Microsoft
          <strong className={system.data?.graph ? "integration-on" : "integration-off"}>{system.data?.graph ? <Check size={14} /> : <Circle size={12} />}{!system.data ? "Carregando…" : system.data.graph ? "Habilitado" : "Desabilitado"}</strong>
        </span>
      </div>
      <ErrorBox error={error ?? records.error ?? system.error ?? schemas.error} />
      <div className="settings-layout settings-redesign">
        <nav aria-label="Categorias de configuração">
          <h2>Central de configurações</h2>
          {[
            { title: "Integrações", keys: ["smtp"] },
            { title: "Processos seletivos", keys: ["vacancy-templates", "workflows", "pipelines", "scorecards", "interview-templates", "checklists"] },
            { title: "Comunicação e experiência", keys: ["message-templates", "surveys", "branding"] },
            { title: "Privacidade e documentos", keys: ["privacy-notices", "retention-policies", "document-types"] },
            { title: "Organização e automação", keys: ["skills", "tags", "closure-reasons", "automations", "saved-reports"] },
          ].map(group => <div className="settings-nav-group" key={group.title}><h3>{group.title}</h3>{group.keys.map(key => <button key={key} className={kind === key ? "active" : ""} aria-current={kind === key ? "page" : undefined} onClick={() => { setKind(key); setSelected(null); setSearch(""); }}>{key === "smtp" ? "E-mails · Microsoft 365" : catalogNames[key]}</button>)}</div>)}
        </nav>
        {kind === "smtp" ? <EmailSettingsPanel /> : <section className="surface padded settings-content">
          <div className="section-heading">
            <div className="settings-content-title"><Settings2 size={22} aria-hidden="true" /><div><h2>{catalogNames[kind]}</h2><p>Consulte os registros, ajuste as regras e acompanhe as versões.</p></div></div>
            <button className="button" disabled={!schema} onClick={() => configure()}><Plus size={16} /> Adicionar</button>
          </div>
          <label className="message-search settings-search"><Search size={18} aria-hidden="true" /><input type="search" aria-label="Buscar configurações pelo nome" placeholder="Buscar pelo nome do registro" value={search} onChange={event => setSearch(event.target.value)} /></label>
          {records.isPending ? <p role="status" className="loading">Carregando configurações…</p> : records.isError ? <button className="button secondary" onClick={() => void records.refetch()}>Tentar novamente</button> : <DataTable
            data={(records.data?.items ?? []).filter(row => str(row.name).toLocaleLowerCase("pt-BR").includes(search.toLocaleLowerCase("pt-BR")))}
            columns={["name", "active", "version", "updated_at"]}
            cells={{ active: row => <span className={`task-state ${row.active ? "done" : "canceled"}`}>{row.active ? "Ativo" : "Inativo"}</span> }}
            onOpen={setSelected}
            actions={row => <button className="button secondary small" disabled={!schema} onClick={() => configure(row)}>Editar</button>}
          />}
          {selected && <details open className="settings-record-detail"><summary>{str(selected.name)}</summary><RecordDetail value={obj(selected.data)} /><ConfigHistory kind={kind} recordId={selected.id} /></details>}
        </section>}
      </div>
      <OperationModal operation={operation} onClose={() => setOperation(null)} />
    </>
  );
}
export function AdminPage() {
  const [secret, setSecret] = useState("");
  const [tab, setTab] = useState("org");
  const [operation, setOperation] = useState<Operation | null>(null);
  const query = useQuery({
    queryKey: ["admin", tab],
    queryFn: () => api<Collection>("/" + tab),
  });
  return (
    <>
      <PageTitle
        title="Administração"
        subtitle="Estrutura organizacional, usuários e permissões."
      />
      <div className="tabs">
        {[
          ["org", "Estrutura"],
          ["users", "Usuários internos"],
          ["roles", "Perfis e permissões"],
          ["deliveries", "Entregas de mensagens"],
          ["webhooks", "Webhooks"],
        ].map(([key, title]) => (
          <button
            className={tab === key ? "active" : ""}
            key={key}
            onClick={() => setTab(key)}
          >
            {title}
          </button>
        ))}
      </div>
      <section className="surface padded">
        <div className="section-toolbar">
          <h2>
            {tab === "org"
              ? "Estrutura organizacional"
              : tab === "users"
                ? "Usuários internos"
                : tab === "roles"
                  ? "Perfis"
                  : tab === "webhooks"
                    ? "Webhooks"
                    : "Fila de entregas"}
          </h2>
          {["org", "users"].includes(tab) && (
            <button
              className="button"
              onClick={() =>
                setOperation({
                  title: "Adicionar registro",
                  form: tab === "org" ? "org" : "user",
                  run: (data) => post("/" + tab, data),
                })
              }
            >
              Adicionar
            </button>
          )}
          {tab === "webhooks" && (
            <button
              className="button"
              onClick={() =>
                setOperation({
                  title: "Configurar webhook",
                  schema: simpleSchema({
                    name: { type: "string" },
                    url: { type: "string", title: "URL HTTPS" },
                    events: {
                      type: "array",
                      items: { type: "string" },
                      title: "Eventos",
                    },
                    enabled: { type: "boolean", title: "Habilitado" },
                  }),
                  run: async (data) => {
                    const result = await post<Row>("/webhooks", data);
                    setSecret(str(result.secret_once));
                    return result;
                  },
                })
              }
            >
              Adicionar
            </button>
          )}
        </div>
        {tab === "roles" && <RoleControls />}
        {secret && (
          <div className="alert" role="status">
            <p>
              Copie a chave de assinatura para configurar o destinatário. Ela
              será exibida apenas nesta sessão.
            </p>
            <code>{secret}</code>
            <button className="text-button" onClick={() => setSecret("")}>
              Já armazenei a chave
            </button>
          </div>
        )}
        <ErrorBox error={query.error} />
        <DataTable
          data={query.data?.items ?? []}
          columns={
            tab === "org"
              ? ["name", "code", "kind", "active"]
              : tab === "users"
                ? ["name", "email", "active"]
                : tab === "roles"
                  ? ["name", "permissions"]
                  : tab === "webhooks"
                    ? ["name", "url", "enabled"]
                    : ["kind", "status", "attempts", "error"]
          }
          actions={(row) => (
            <>
              {tab === "roles" && <RoleControls row={row} />}{" "}
              {tab === "users" && <UserAccess row={row} />}{" "}
              {tab === "org" && (
                <button
                  className="text-button"
                  onClick={() =>
                    setOperation({
                      title: "Editar estrutura",
                      form: "org",
                      initial: {
                        name: row.name,
                        code: row.code,
                        kind: row.kind,
                        parent_id: row.parent_id,
                        active: row.active,
                      },
                      run: (data) =>
                        put("/org/" + row.id, {
                          ...data,
                          version: row.version,
                        }),
                    })
                  }
                >
                  Editar
                </button>
              )}
              {tab === "users" && (
                <button
                  className="text-button"
                  onClick={() =>
                    setOperation({
                      title: "Alterar acesso do usuário",
                      schema: simpleSchema({
                        active: {
                          type: "boolean",
                          default: Boolean(row.active),
                        },
                        reason: { type: "string", title: "Motivo" },
                      }),
                      run: (data) =>
                        put("/users/" + row.id + "/status", {
                          ...data,
                          version: row.version,
                        }),
                    })
                  }
                >
                  Alterar acesso
                </button>
              )}
              {tab === "deliveries" &&
                ["DEAD", "DISABLED"].includes(str(row.status)) && (
                  <button
                    className="text-button"
                    onClick={() =>
                      setOperation({
                        title: "Reprocessar entrega",
                        schema: simpleSchema({}),
                        run: () => post("/deliveries/" + row.id + "/replay"),
                      })
                    }
                  >
                    Reprocessar
                  </button>
                )}
            </>
          )}
        />
      </section>
      <OperationModal
        operation={operation}
        onClose={() => setOperation(null)}
      />
    </>
  );
}
export function ReportsPage() {
  return <ReportBuilder />;
}
