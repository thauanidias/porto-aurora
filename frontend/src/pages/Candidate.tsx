import { NewEmployeeWelcome } from "../components/NewEmployeeWelcome";
import { enrollSelectedVacancy } from "../lib/enrollSelectedVacancy";
import { DuplicateReview, RecalculateScore } from "../components/ReviewActions";
import { CandidateCompatibility } from "../components/CandidateCompatibility";
import { CandidateStageAction, candidateStageHint } from "../components/CandidateStageAction";
import { VacancyFitMessage } from "../components/VacancyFitMessage";
import { ResumeUpload } from "../components/ResumeUpload";
import { ResumePersonalFields, type ResumePersonalRecord } from "../components/ResumePersonalFields";
import { ResumeImportReview } from "../components/ResumeImportReview";
import { normalizeResumeDraft } from "../lib/resumeMerge";
import { SelectionRegistration } from "../components/SelectionRegistration";
import { ApplicationConversation } from "../components/ApplicationConversation";
import { RejectionEmail } from "../components/RejectionEmail";
import { ProcessInterviews } from "../components/ProcessInterviews";
import { SensitiveProfile } from "../components/SensitiveProfile";
import { CandidateSummary } from "../components/CandidateSummary";
import { ProfilePhoto } from "../components/ProfilePhoto";
import { AdmissionDocuments } from "../components/AdmissionDocuments";
import { RHDocumentProfiles } from "../components/RHDocumentProfiles";
import { RHExternalDownload } from "../components/RHExternalDownload";
import { RHConsentDownload } from "../components/RHConsentDownload";
import { CandidateDocumentFiles } from "../components/CandidateDocumentFiles";
import { ReleaseAdmissionDocuments } from "../components/ReleaseAdmissionDocuments";
import { CandidateRegistrationDocuments } from "../components/CandidateRegistrationDocuments";
import { CandidateProcesses } from "../components/CandidateProcesses";
import { RHActivityLinks } from "../components/CandidateActivityLinks";
import { StageGate } from "../components/CandidateJourney";
import { CandidateResume } from "../components/CandidateResume";
import { RHSelectionDocuments } from "../components/RHSelectionDocuments";
import { TestReviews } from "../components/AdminExtras";
import {
  CandidateTools,
  ConsensusPanel,
  NoteActions,
} from "../components/CollaborationPanels";
import { simpleSchema } from "../lib/forms";
import { useCallback, useRef, useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { safeReturnPath } from "../lib/returnPath";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  api,
  post,
  put,
  obj,
  rows,
  str,
  setToken,
  type Collection,
  type Row,
} from "../lib/api";
import { isManager, useSession } from "../lib/session";
import { Badge, Empty, ErrorBox, PageTitle } from "../components/ui";
import { SchemaForm, type Schema } from "../components/SchemaForm";
import { OperationModal, RecordDetail, type Operation } from "./Resources";
import { date, label } from "../lib/labels";
import { useCandidateActions } from "../lib/candidateActions";
import { Monitor, Smartphone, ShieldCheck, FileText, History, ClipboardList, CalendarDays, ChartNoAxesCombined, ListChecks, MessageSquare, FolderCheck } from "lucide-react";
import { InterviewAttachmentButton } from "../components/InterviewAttachmentButton";
import { InternalRegistration } from "../components/InternalRegistration";
import { useCandidateJourney } from "../lib/candidateJourney";
import { RHInternalDownloads } from "../components/RHInternalDownloads";

function candidateStageName(value: unknown) {
  const name = str(value);
  return name === "Inscritos" ? "Inscrito" : name;
}

function sessionDevice(agent: string) {
  const mobile = /Android|iPhone|iPad/i.test(agent);
  const system = /Android/i.test(agent) ? "Android" : /iPhone|iPad/i.test(agent) ? "iOS" : /Windows/i.test(agent) ? "Windows" : /Macintosh|Mac OS/i.test(agent) ? "macOS" : /Linux/i.test(agent) ? "Linux" : "Dispositivo";
  const browser = /Electron/i.test(agent) ? "Aplicativo" : /Edg\//i.test(agent) ? "Edge" : /Firefox\//i.test(agent) ? "Firefox" : /Chrome\//i.test(agent) ? "Chrome" : /Safari\//i.test(agent) ? "Safari" : "Navegador";
  return { mobile, name: system + " · " + browser };
}

function ApplicationProgress({ application }: { application: Row }) {
  const session = useSession();
  const detail = useQuery({
    queryKey: ["application", application.id],
    queryFn: () => api<Row>("/applications/" + application.id),
    refetchInterval: 30000,
  });
  const history = rows(detail.data?.history);
  const process = detail.data ?? application;
  const ownProcess = str(obj(process.candidate).user_id) === session.data?.user.id;
  return <article className="surface candidate-progress-card">
    <div className="candidate-progress-heading"><div><span className="privacy-eyebrow">ACOMPANHAMENTO DA CANDIDATURA</span><h2>{str(application.vacancy_title)}</h2></div><Badge value={application.status} /></div>
    <p>Etapa atual: <strong>{ownProcess ? <CandidateStageAction application={process} compact label={candidateStageName(process.stage_name)} /> : candidateStageName(process.stage_name)}</strong></p>
    {detail.isPending && <p className="muted" role="status">Carregando acompanhamento…</p>}
    <ErrorBox error={detail.error} />
    {ownProcess && <NewEmployeeWelcome application={process} />}
    {ownProcess && process.documents_welcome_ready !== true && <div className="notice"><p>{candidateStageHint(process)}</p><CandidateStageAction application={process} /></div>}
    {history.length > 0 && <ol className="candidate-progress-steps" aria-label="Etapas percorridas">
      {history.map(step => <li key={step.id} className={step.left_at ? "completed" : "current"} aria-current={!step.left_at ? "step" : undefined}>
        <span className="candidate-progress-dot" aria-hidden="true">{step.left_at ? "✓" : "●"}</span>
        <div><strong>{ownProcess && !step.left_at ? <CandidateStageAction application={process} compact label={candidateStageName(step.stage_name)} /> : candidateStageName(step.stage_name)}</strong><small>{step.left_at ? "Concluída" : "Etapa atual"} · {date(step.entered_at)}</small></div>
      </li>)}
    </ol>}
    <div className="candidate-progress-footer"><small className="muted">Última atualização: {date(detail.data?.updated_at ?? application.updated_at)}</small><div className="candidate-progress-actions"><Link className="button" to={"/candidato/candidaturas/" + application.id}>Ver acompanhamento completo</Link></div></div>
  </article>;
}

export function MyApplications() {
  const session = useSession();
  const employee = Boolean(session.data?.permissions.includes("internal.view"));
  const availableActions = useCandidateActions();
  const [page, setPage] = useState(1);
  const [selectedApplication, setSelectedApplication] = useState("");
  const query = useQuery({
    queryKey: ["my-applications", page],
    queryFn: () => api<Collection>("/applications?page_number=" + page),
    refetchInterval: 30000,
  });
  const applications = query.data?.items ?? [];
  const selected = applications.find(application => application.id === selectedApplication) ?? applications[0];
  return (
    <>
      <PageTitle
        title="Minhas candidaturas"
        subtitle="Acompanhe suas etapas e as próximas ações."
        actions={
          <Link className="button secondary" to="/candidato/vagas">
            Explorar oportunidades
          </Link>
        }
      />
      <ErrorBox error={query.error} />
      <ErrorBox error={availableActions.error} />
      {employee && <section className="surface employee-priority" aria-labelledby="employee-priority-title">
        <div><p className="privacy-eyebrow">SELEÇÃO INTERNA · COMECE POR AQUI</p><h2 id="employee-priority-title">Sua ficha interna em primeiro lugar</h2><p>Preencha ou atualize sua ficha para participar das oportunidades internas. Depois, acompanhe as etapas e atividades liberadas pelo RH nesta mesma área.</p></div>
        <Link className="button" to="/candidato/perfil#ficha-interna">Acessar ficha interna</Link>
      </section>}

      {Boolean(availableActions.data?.length) && <section className="candidate-released-actions" aria-label="Ações disponíveis para você" aria-live="polite">
        <h2>Você tem ações disponíveis</h2>
        <p>Confira as etapas liberadas e os próximos compromissos do seu processo.</p>
        <div>{availableActions.data?.map(action => <Link className="surface candidate-released-action" key={action.path} to={"/candidato/" + action.path}>
          <span className="candidate-action-count">{action.count}</span><div><strong>{action.title}</strong><p>{action.description}</p><span className="text-button">Acessar esta área →</span></div>
        </Link>)}</div>
      </section>}
      {query.isPending && <p role="status">Carregando suas candidaturas…</p>}
      {applications.length > 1 && <label className="field"><span>Qual candidatura deseja acompanhar?</span><select value={selected?.id ?? ""} onChange={event => setSelectedApplication(event.target.value)}>{applications.map(application => <option key={application.id} value={application.id}>{str(application.vacancy_title)}{str(obj(application.candidate).name) ? " · " + str(obj(application.candidate).name) : ""}</option>)}</select></label>}
      <div className="application-list">
        {selected && <ApplicationProgress key={selected.id} application={selected} />}
      </div>
      {(query.data?.total ?? 0) > 25 && <div className="pagination">
        <button className="button secondary" disabled={page === 1} onClick={() => setPage(page - 1)}>Anterior</button>
        <span>Página {page}</span>
        <button className="button secondary" disabled={page * 25 >= (query.data?.total ?? 0)} onClick={() => setPage(page + 1)}>Próxima</button>
      </div>}
      {query.isSuccess && !query.data.items.length && (
        <Empty title="Sua jornada começa com uma oportunidade">
          Encontre uma vaga e envie sua candidatura.
        </Empty>
      )}
    </>
  );
}
export function ProfilePage() {
  const journey = useCandidateJourney();
  const navigate = useNavigate();
  const [enrolling, setEnrolling] = useState(false);
  const [params] = useSearchParams();
  const onboarding = params.get("cadastro") === "1";
  const returnTo = safeReturnPath(params.get("next"))
    ?? safeReturnPath(sessionStorage.getItem("tgpm-selected-vacancy"))
    ?? safeReturnPath(sessionStorage.getItem("tgpm-registration-return"));
  const applying = params.get("candidatura") === "1" || Boolean(returnTo && /^(\/carreiras\/vagas\/|\/oportunidades-internas\/|\/convite)/.test(returnTo));
  const query = useQuery({
    queryKey: ["my-profile"],
    queryFn: () => api<Row | null>("/candidates/me"),
  });
  const schema = useQuery({
    queryKey: ["profile-schema"],
    queryFn: () => api<Schema>("/candidates/profile-schema"),
  });
  const [error, setError] = useState<unknown>();
  const [saved, setSaved] = useState(false);
  const [suggestions, setSuggestions] = useState<Record<string, unknown>>();
  const [resumeUploading, setResumeUploading] = useState(false);
  const [profileSaving, setProfileSaving] = useState(false);
  const [importEpoch, setImportEpoch] = useState(0);
  const basicDraft = useRef<Record<string, unknown>>({});
  const professionalDraft = useRef<Record<string, unknown>>({});
  const personalDraft = useRef<Record<string, unknown>>({});
  const onBasicDraft = useCallback((value: Record<string, unknown>) => {basicDraft.current = value;}, []);
  const onProfessionalDraft = useCallback((value: Record<string, unknown>) => {professionalDraft.current = value;}, []);
  const onPersonalDraft = useCallback((value: Record<string, unknown>) => {personalDraft.current = value;}, []);
  const personal = useQuery({queryKey: ["resume-personal"], queryFn: () => api<ResumePersonalRecord>("/candidates/me/resume-personal"), staleTime: Infinity, refetchOnWindowFocus: false});
  const client = useQueryClient();
  const session = useSession();
  const employee = Boolean(session.data?.permissions.includes("internal.view"));
  const opportunities = employee ? "/oportunidades-internas" : "/carreiras";
  const initial = query.data
    ? Object.fromEntries(
        [
          "name",
          "social_name",
          "phone",
          "city",
          "state",
          "country",
          "profile",
          "version",
        ].map((k) => [k, query.data?.[k]]),
      )
    : undefined;
  if (initial)
    initial.profile = Object.fromEntries(
      Object.entries(obj(initial.profile)).filter(([k]) => k !== "facts"),
    );
  const basicInitial = Object.fromEntries(Object.entries(initial ?? {
    name: session.data?.user.name ?? "", social_name: "", phone: "",
    city: "", state: "", country: "BR",
  }).filter(([key]) => key !== "profile" && key !== "version"));
  const basicSchema = schema.data && {
    ...schema.data,
    properties: Object.fromEntries(Object.entries(schema.data.properties ?? {}).filter(([key]) => key !== "profile" && key !== "version").map(([key, field]) => [key, key === "city" ? {
      ...field, examples: ["Belém", "Barcarena"],
    } : key === "state" ? { ...field, placeholder: "PA", examples: ["PA"] } : field])),
    required: schema.data.required?.filter(key => key !== "profile" && key !== "version"),
  };
  const professionalSchema: Schema | undefined = schema.data && {
    type: "object", $defs: Object.fromEntries(Object.entries(schema.data.$defs ?? {}).map(([key, definition]) => [key, key === "Profile" ? {
      ...definition,
      properties: Object.fromEntries(Object.entries(definition.properties ?? {}).map(([field, config]) => [field, field === "shift" ? {
        ...config, placeholder: "Selecione ou digite um turno", examples: ["Manhã", "Tarde", "Noite", "Comercial", "Disponibilidade para revezamento", "Qualquer turno"],
      } : config])),
    } : definition])),
    properties: { profile: schema.data.properties?.profile ?? {} }, required: ["profile"],
  };
  async function saveProfilePatch(data: Record<string, unknown>) {
    setProfileSaving(true);
    try {
      await put("/candidates/me", { ...basicInitial, profile: initial?.profile ?? {}, ...data, version: query.data?.version });
      setSuggestions(undefined);
      setSaved(true);
      setError(undefined);
      await client.invalidateQueries({ queryKey: ["my-profile"] });
    } catch (e) {
      setError(e);
      throw e;
    } finally {
      setProfileSaving(false);
    }
  }
  async function saveAndEnroll(data: Record<string, unknown>) {
    if (enrolling) return;
    setEnrolling(true);
    try {
      await saveProfilePatch(data);
      if (!returnTo) {
        navigate("/candidato/vagas?selecionar=1");
        return;
      }
      const application = await enrollSelectedVacancy(returnTo);
      await client.invalidateQueries({ queryKey: ["my-applications"] });
      sessionStorage.removeItem("tgpm-registration-return");
      sessionStorage.removeItem("tgpm-selected-vacancy");
      navigate("/candidato/candidaturas/" + application.id);
    } catch (cause) {
      setError(cause);
      throw cause;
    } finally {
      setEnrolling(false);
    }
  }
  return (
    <>
      <PageTitle
        title={employee ? "Ficha interna e perfil" : onboarding ? "Complete seu cadastro" : "Meu perfil"}
        subtitle={employee ? "Comece pela ficha de seleção interna. Depois, confira seu currículo e os demais dados do perfil." : "Complete seus dados, envie seu currículo e mantenha seu perfil atualizado."}
      />
      {employee && <>
        <nav className="employee-profile-shortcuts" aria-label="Seções do perfil do colaborador">
          <a className="button small" href="#ficha-interna">1. Ficha interna</a>
          <a className="button secondary small" href="#curriculo">2. Currículo</a>
          <a className="button secondary small" href="#dados-basicos">3. Dados básicos</a>
          <a className="button secondary small" href="#perfil-profissional">4. Perfil profissional</a>
        </nav>
        <div id="ficha-interna" className="employee-registration-priority"><InternalRegistration identity={session.data?.user ?? {}} /></div>
      </>}
      {onboarding && !applying && !saved && <p className="alert">Preencha os campos abaixo e clique em Salvar. {returnTo ? "Sua vaga está guardada para você continuar a candidatura depois." : "Depois, você poderá explorar as vagas disponíveis."}</p>}
      {!query.isPending && !query.error && (
        <ProfilePhoto
          name={str(query.data?.name ?? session.data?.user.name)}
          editable
          profileReady={Boolean(query.data)}
        />
      )}
      <ErrorBox error={error} />
      {saved && (
        <div className="alert success" role="status">
          <span>Perfil atualizado.</span>
        {(onboarding || applying) && <p><Link className="button" to={returnTo ?? opportunities}>{returnTo ? "Continuar candidatura" : "Ver vagas disponíveis"}</Link></p>}
        </div>
      )}
      {applying && !saved && <div className="alert candidate-profile-notice" role="status">
        <strong>Complete seu perfil para se inscrever na vaga</strong>
        <p>Para realizar sua inscrição, preencha e salve os dados básicos e as informações profissionais, anexe seu currículo e aceite o termo de consentimento.</p>
        <p>Sua vaga está guardada. Ao terminar, clique em <strong>Salvar e inscrever-se na vaga</strong> no perfil profissional para concluir sua inscrição na oportunidade selecionada.</p>
      </div>}
      {session.data?.permissions.includes("internal.view") ? <div id="curriculo"><ResumeUpload onSuggestions={data => { setSuggestions(data); setSaved(false); }} onBusyChange={value => { setResumeUploading(value); if (value) setSaved(false); }} /></div> : <StageGate id="curriculo" section="resume" title="Envio e leitura do currículo">
        <ResumeUpload onSuggestions={data => { setSuggestions(data); setSaved(false); }} onBusyChange={value => { setResumeUploading(value); if (value) setSaved(false); }} />
      </StageGate>}
      {suggestions && <ResumeImportReview ready={Boolean(query.data && personal.data) && !resumeUploading && !profileSaving}
        getSnapshot={() => ({
          candidate: normalizeResumeDraft(schema.data, {...basicInitial, ...basicDraft.current, profile: professionalDraft.current.profile ?? initial?.profile ?? {}, version: query.data?.version}) as Record<string, unknown>,
          personal: normalizeResumeDraft(client.getQueryData<Schema>(["resume-personal-schema"]), Object.keys(personalDraft.current).length ? personalDraft.current : personal.data?.data ?? {}) as Record<string, unknown>,
          personal_version: personal.data?.version ?? 0,
        })}
        onSaved={result => {
          client.setQueryData(["my-profile"], result.candidate);
          client.setQueryData(["resume-personal"], result.personal);
          setSuggestions(undefined);setSaved(true);setImportEpoch(value => value + 1);
          for (const key of ["candidate-journey", "candidate-actions", "my-applications"]) void client.invalidateQueries({queryKey: [key]});
        }} />}
      <section id="dados-basicos" className="surface padded">
        <h2>Dados básicos e acessibilidade</h2>
        <p>Atualize seus dados de contato. As informações de acessibilidade são opcionais e têm autorização própria.</p>
        {query.isPending || schema.isPending ? (
          <p role="status">Carregando perfil…</p>
        ) : (
          basicSchema && !query.error && (
            <SchemaForm
              key={"basic-" + importEpoch}
              schema={basicSchema}
              submitLabel="Salvar dados básicos"
              suggestions={suggestions && Object.fromEntries(Object.entries(suggestions).filter(([key]) => !["profile", "personal"].includes(key)))}
              onValuesChange={onBasicDraft}
              busy={resumeUploading || profileSaving || enrolling}
              initial={basicInitial}
              onSubmit={saveProfilePatch}
            />
          )
        )}
        <ErrorBox error={query.error ?? schema.error} />
        <StageGate id="informacoes-complementares" section="sensitive_profile" title="Acessibilidade e informações opcionais"><SensitiveProfile embedded /></StageGate>
      </section>
      <ResumePersonalFields key={"personal-" + importEpoch} suggestions={suggestions?.personal as Record<string, unknown> | undefined} onValuesChange={onPersonalDraft} />
      <StageGate id="perfil-profissional" section="professional_profile" title="Perfil profissional"><section className="surface padded">
        <h2>Perfil profissional</h2>
        <p>Informe sua formação, experiências e competências profissionais.</p>
        {query.isPending || schema.isPending ? <p role="status">Carregando perfil…</p> : professionalSchema && !query.error && <SchemaForm
          key={"professional-" + importEpoch}
          schema={professionalSchema}
          submitLabel="Salvar e inscrever-se na vaga"
          suggestions={suggestions?.profile ? { profile: suggestions.profile } : undefined}
          onValuesChange={onProfessionalDraft}
          busy={resumeUploading || profileSaving || enrolling}
          initial={{ profile: initial?.profile ?? {} }}
          onSubmit={saveAndEnroll}
        />}
      </section></StageGate>
      {!employee && journey.data?.sections.selection_registration.enabled ? <div id="ficha-externa"><SelectionRegistration identity={session.data?.user ?? {}} /></div> : null}
    </>
  );
}
export function CandidateDetail() {
  const { id } = useParams();
  const [params, setParams] = useSearchParams();
  const tab = params.get("aba") ?? "processos";
  const candidate = useQuery({
    queryKey: ["candidate", id],
    queryFn: () => api<Row>("/candidates/" + id),
    refetchInterval: 15000,
  });
  const [operation, setOperation] = useState<Operation | null>(null);
  return (
    <>
      <Link className="candidate-back" to="/app/candidatos">← Voltar para candidatos</Link>
      <section className="surface candidate-profile-banner">
        {id && candidate.data && !candidate.data.blind && <ProfilePhoto candidateId={id} name={str(candidate.data.name)} />}
        <div className="candidate-profile-banner-body">
      <PageTitle
        title={str(candidate.data?.name) || "Perfil do candidato"}
        subtitle="Consulte o cadastro, o perfil profissional e o histórico de participação."
        actions={
          <>
          {id && candidate.data && !candidate.data.blind && <RHExternalDownload candidateId={id} />}
          {id && candidate.data && !candidate.data.blind && <RHConsentDownload candidateId={id} />}


          </>
        }
      />
        {candidate.data && !candidate.data.blind && <div className="candidate-profile-context">{Boolean(candidate.data.city) && <span>{str(candidate.data.city)}{candidate.data.state ? " · " + str(candidate.data.state) : ""}</span>}{Boolean(candidate.data.email) && <a href={"mailto:" + str(candidate.data.email)}>{str(candidate.data.email)}</a>}</div>}
        </div>
      </section>
      <ErrorBox error={candidate.error} />
      {candidate.isPending && <p role="status">Carregando perfil do candidato…</p>}
      {id && candidate.data && <>
        <div className="tabs rh-profile-tabs" role="tablist" aria-label="Informações do candidato">
          {[{ key: "processos", name: "Processos", icon: ListChecks }, { key: "perfil", name: "Dados e currículo", icon: FileText }, { key: "selecao", name: "Ficha externa", icon: ClipboardList }, { key: "consentimento", name: "Consentimento", icon: ShieldCheck }, { key: "atividades", name: "Entrevistas e testes", icon: CalendarDays }, { key: "documentos", name: "Documentos", icon: FolderCheck }, { key: "historico", name: "Histórico", icon: History }].map(({ key, name, icon: Icon }) => <button key={key} role="tab" aria-selected={tab === key} tabIndex={tab === key ? 0 : -1} className={tab === key ? "active" : ""} onKeyDown={event => {
            if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
            event.preventDefault();
            const buttons = Array.from(event.currentTarget.parentElement?.querySelectorAll<HTMLButtonElement>('button[role="tab"]') ?? []);
            const index = buttons.indexOf(event.currentTarget);
            const nextIndex = event.key === "Home" ? 0 : event.key === "End" ? buttons.length - 1 : (index + (event.key === "ArrowRight" ? 1 : -1) + buttons.length) % buttons.length;
            buttons[nextIndex]?.focus(); buttons[nextIndex]?.click();
          }} onClick={() => { const next = new URLSearchParams(params); next.set("aba", key); setParams(next); }}><Icon size={17} aria-hidden="true" /><span>{name}</span></button>)}
        </div>
        {tab === "processos" && <CandidateProcesses key={id} candidateId={id} />}
        {tab === "perfil" && <>{!candidate.data.blind && <><RHInternalDownloads candidateId={id} /><CandidateResume candidateId={id} /></>}<CandidateSummary candidate={candidate.data} /></>}
        {tab === "selecao" && <RHSelectionDocuments candidate={candidate.data} view="registration" />}
        {tab === "consentimento" && <RHSelectionDocuments candidate={candidate.data} view="consent" />}
        {tab === "atividades" && <RHActivityLinks key={"links-" + id} candidateId={id} />}
        {tab === "documentos" && !candidate.data.blind && <><CandidateDocumentFiles key={id} candidateId={id} /><ReleaseAdmissionDocuments key={id} candidateId={id} /><AdmissionDocuments candidateId={id} showReleaseAction={false} /></>}
        {tab === "documentos" && Boolean(candidate.data.blind) && <p className="alert">Os documentos de identificação ficam disponíveis conforme as regras de sigilo desta vaga.</p>}
        {tab === "historico" && <><CandidateTools candidateId={id} /><DuplicateReview candidateId={id} /></>}
      </>}
      <OperationModal
        operation={operation}
        onClose={() => setOperation(null)}
      />
    </>
  );
}
export function ApplicationDetail({
  candidate = false,
}: {
  candidate?: boolean;
}) {
  const { id } = useParams();
  const [params, setParams] = useSearchParams();
  const tab = candidate ? "history" : params.get("aba") ?? params.get("tab") ?? "profile";
  const setTab = (value: string) => { const next = new URLSearchParams(params); next.set("aba", value); setParams(next, { replace: true }); };
  const [operation, setOperation] = useState<Operation | null>(null);
  const [error, setError] = useState<unknown>();
  const client = useQueryClient();
  const session = useSession();
  const query = useQuery({
    queryKey: ["application", id],
    queryFn: () => api<Row>("/applications/" + id),
    refetchInterval: 15000,
  });
  const messages = useQuery({
    queryKey: ["messages", id],
    queryFn: () => api<Collection>("/applications/" + id + "/messages"),
    enabled: !candidate,
  });
  const evaluations = useQuery({
    queryKey: ["evaluations", id],
    queryFn: () => api<Collection>("/evaluations?application_id=" + id),
    enabled:
      !candidate &&
      Boolean(session.data?.permissions.includes("candidate.evaluate")),
  });
  const checklist = useQuery({
    queryKey: ["checklist", id],
    queryFn: () => api<Collection>("/applications/" + id + "/checklist"),
  });
  const slots = useQuery({
    queryKey: ["slots", id],
    queryFn: () => api<Collection>("/applications/" + id + "/interview-slots"),
    enabled: candidate,
  });
  if (query.isPending) return <p role="status">Carregando candidatura…</p>;
  if (!query.data) return <ErrorBox error={query.error} />;
  const row = query.data;
  const score = rows(row.scores)[0];
  const breakdown = obj(score?.breakdown);
  const tabs = candidate
    ? [
        ["history", "Acompanhamento"],
      ]
    : [
        ["profile", "Dados e currículo"],
        ["history", "Andamento"],
        ["selection", "Ficha e termo"],
        ["activities", "Entrevistas e testes"],
        ["score", "Requisitos da vaga"],
        ["messages", "Mensagens"],
        ["checklist", "Documentos"],
      ];
  const tabIcons: Record<string, typeof FileText> = { profile: FileText, history: History, selection: ClipboardList, activities: CalendarDays, score: ChartNoAxesCombined, evaluations: ListChecks, messages: MessageSquare, checklist: FolderCheck };
  return (
    <>
      {!candidate && !isManager(session.data) && <Link className="back-link" to={row.recruitment_type === "INTERNAL" ? "/app/candidaturas-internas" : "/app/candidaturas"}>{row.recruitment_type === "INTERNAL" ? "← Voltar às candidaturas internas" : "← Voltar às candidaturas externas"}</Link>}
      <div className={!candidate ? "surface application-detail-header" : undefined}>
      {!candidate && !obj(row.candidate).blind && Boolean(row.candidate_id) && <ProfilePhoto candidateId={str(row.candidate_id)} name={str(obj(row.candidate).name)} />}
      <div className="application-detail-heading">
      <PageTitle
        title={
          candidate ? str(row.vacancy_title) : str(obj(row.candidate).name)
        }
        subtitle={
          candidate
            ? "Acompanhe os próximos passos da seleção."
            : str(row.vacancy_title)
        }
        actions={
          <>
            <Badge value={row.status} />
            {!candidate && <InterviewAttachmentButton application={row} />}
            {candidate && row.return_available === true && (
              <button
                className="button secondary"
                onClick={() =>
                  setOperation({
                    title: "Retornar ao processo seletivo",
                    schema: simpleSchema({
                      consent: {
                        type: "boolean",
                        title:
                          "Li o aviso vigente em Privacidade e aceito retornar ao processo",
                      },
                    }),
                    run: (data) =>
                      post("/applications/" + id + "/return", {
                        ...data,
                        version: row.version,
                        notice_id: row.notice_id,
                      }),
                  })
                }
              >
                Solicitar retorno
              </button>
            )}
            {candidate && ["ACTIVE", "RESERVE"].includes(str(row.status)) && (
              <button
                className="button secondary"
                onClick={() =>
                  setOperation({
                    title: "Retirar candidatura",
                    schema: simpleSchema({
                      reason: { type: "string", title: "Motivo (opcional)" },
                    }),
                    run: (data) =>
                      post("/applications/" + id + "/decision", {
                        ...data,
                        version: row.version,
                        decision: "WITHDRAWN",
                      }),
                  })
                }
              >
                Retirar candidatura
              </button>
            )}
            {!candidate &&
              session.data?.permissions.includes("candidate.select") && (
                <button
                  className="button"
                  onClick={() =>
                    setOperation({
                      title: "Registrar decisão",
                      schema: { ...simpleSchema({
                        decision: {
                          enum: ["SELECTED", "RESERVE", "REJECTED", "HIRED"],
                        },
                        reason: { type: "string", title: "Justificativa" },
                        ...(session.data?.permissions.includes("message.send") ? {
                          send_rejection_email: { type: "boolean", title: "Enviar e-mail automaticamente ao registrar Não selecionada", default: false },
                          rejection_email_body: { type: "string", title: "Mensagem de retorno (opcional; em branco usa o modelo padrão)", maxLength: 10000 },
                        } : {}),
                        override: {
                          type: "boolean",
                          title: "Exceção autorizada",
                        },
                      }), description: "Ao preencher a última posição da vaga, as demais candidaturas em andamento ou em reserva serão encerradas como não selecionadas e os e-mails de retorno serão preparados automaticamente." },
                      run: (data) =>
                        post("/applications/" + id + "/decision", {
                          ...data,
                          version: row.version,
                        }),
                    })
                  }
                >
                  Registrar decisão
                </button>
              )}
          </>
        }
      />
      {!candidate && <div className="application-detail-meta"><span>{row.recruitment_type === "INTERNAL" ? "Seleção interna" : "Seleção externa"}</span><span>Etapa: <strong>{str(row.stage_name)}</strong></span></div>}
      </div></div>
      {!candidate && !obj(row.candidate).blind && <VacancyFitMessage key={str(row.id)} application={row} />}
      <ErrorBox error={error} />
      {!candidate && row.status === "REJECTED" && session.data?.permissions.includes("message.send") && <RejectionEmail key={str(row.id)} applicationId={str(row.id)} />}
      <div className={candidate ? "tabs" : "tabs application-detail-tabs"} role="tablist" aria-label="Informações da candidatura">
        {tabs.map(([key, name]) => { const Icon = tabIcons[key] ?? FileText; return (
          <button
            role="tab"
            aria-selected={tab === key}
            className={tab === key ? "active" : ""}
            onClick={() => setTab(key)}
            key={key}
          >
            {!candidate && <Icon size={17} aria-hidden="true" />}{name}
          </button>
        ); })}
      </div>
      {tab === "history" && (
        <section className={candidate ? "surface padded application-tracking" : "surface padded"}>
          {candidate && <NewEmployeeWelcome application={row} />}
          {candidate ? <><div className="application-tracking-current"><span>ETAPA ATUAL</span><h2><CandidateStageAction application={row} compact label={candidateStageName(row.stage_name)} /></h2><p>{candidateStageHint(row)}</p><Badge value={row.status} /></div><h3>Seu caminho na seleção</h3></> : <h2>Etapa atual: {str(row.stage_name)}</h2>}
          <ol className={candidate ? "application-tracking-history" : "timeline"}>
            {rows(row.history).map((history) => (
              <li key={history.id} className={candidate ? history.left_at ? "completed" : "current" : undefined}>
                {candidate && <span className="tracking-marker" aria-hidden="true">{history.left_at ? "✓" : "●"}</span>}
                <div>
                <strong>
                  {candidate ? !history.left_at ? <CandidateStageAction application={row} compact label={candidateStageName(history.stage_name)} /> : candidateStageName(history.stage_name) : str(history.stage_name) + " · " + date(history.entered_at)}
                </strong>
                {candidate && <span className="tracking-state">{history.left_at ? "Concluída" : "Em andamento"}</span>}
                <p>
                  {history.left_at
                    ? "Etapa concluída em " + date(history.left_at)
                    : "Nesta etapa desde " + date(history.entered_at)}
                </p>
                {!candidate && history.reason ? (
                  <p>{str(history.reason)}</p>
                ) : null}
                {!candidate && Boolean(history.changed_by_name) && <small>Responsável: {str(history.changed_by_name)}</small>}
                </div>
              </li>
            ))}
          </ol>
          {candidate && Boolean(slots.data?.items.length) && (
            <>
              <h3>Escolha um horário de entrevista</h3>
              {slots.data?.items.map((slot) => (
                <button
                  className="button secondary"
                  key={slot.id}
                  onClick={async () => {
                    try {
                      await post(
                        "/applications/" +
                          id +
                          "/interview-slots/" +
                          slot.id +
                          "/book",
                      );
                      await client.invalidateQueries();
                    } catch (e) {
                      setError(e);
                    }
                  }}
                >
                  {date(slot.starts_at)} · {str(slot.title)}
                </button>
              ))}
            </>
          )}
        </section>
      )}
      {tab === "profile" && <>{!obj(row.candidate).blind && str(row.candidate_id) && <CandidateResume candidateId={str(row.candidate_id)} />}<CandidateSummary candidate={obj(row.candidate) as Row} /></>}
      {!candidate && tab === "selection" && <RHSelectionDocuments candidate={obj(row.candidate) as Row} />}
      {!candidate && tab === "activities" && str(row.candidate_id) && <RHActivityLinks key={"links-" + row.id} candidateId={str(row.candidate_id)} applicationId={row.id} />}
      {!candidate && tab === "activities" && <ProcessInterviews application={row} />}
      {!candidate && tab === "activities" && session.data?.permissions.some(permission => ["test.manage", "candidate.evaluate"].includes(permission)) && <TestReviews applicationId={str(id)} />}
      {tab === "score" && (
        <RecalculateScore
          applicationId={str(id)}
          vacancyId={str(row.vacancy_id)}
        />
      )}
      {!candidate && tab === "score" && <section className="surface padded"><h2>Compatibilidade curricular</h2><p className="muted">Consulte as evidências profissionais e confirme as informações pendentes antes de registrar seu parecer.</p><CandidateCompatibility row={row} details /></section>}
      {tab === "score" && (
        <section className="surface padded">
          <div className="section-heading">
            <div>
              <p className="eyebrow">ADERÊNCIA AOS CRITÉRIOS DA VAGA</p>
              <h2 className="score-value">
                {score?.total == null ? "—" : Number(score.total).toLocaleString("pt-BR", { maximumFractionDigits: 2 }) + "%"}
              </h2>
              <p>
                Modelo versão {str(breakdown.model_version)} ·{" "}
                {date(score?.created_at)}
              </p>
            </div>
            {score && <Badge value={breakdown.status} />}
          </div>
          <p>{str(breakdown.formula)}</p>
          <div className="notice"><strong>Aderência declarada, sujeita à conferência do RH</strong><p>Esta nota compara o perfil com os critérios configurados. Não representa probabilidade de contratação nem comprovação de competências. Pontuação parcial não significa que o requisito mínimo foi atendido.</p><p>O tempo de experiência considera os períodos profissionais informados, sem somar vínculos simultâneos. Confira se as atividades são relevantes para esta vaga; o tempo total sozinho não comprova experiência em TI ou liderança.</p></div>
          {rows(breakdown.items).length > 0 && (
            <table>
              <thead>
                <tr>
                  <th>Critério</th>
                  <th>Informado</th>
                  <th>Esperado</th>
                  <th>Peso</th>
                  <th>Nota</th>
                  <th>Contribuição</th>
                  <th>Conferência</th>
                </tr>
              </thead>
              <tbody>
                {rows(breakdown.items).map((item) => (
                  <tr key={str(item.key)}>
                    <td>
                      {str(item.name)}
                      {Boolean(item.knockout || item.mandatory) && <small>Obrigatório</small>}
                    </td>
                    <td>
                      {Array.isArray(item.value)
                        ? item.value.join(", ")
                        : item.value == null ? "Não informado" : item.field === "education_level" ? ({ 0: "Não concluída", 1: "Fundamental", 2: "Ensino médio", 3: "Técnico", 4: "Superior", 5: "Pós-graduação", 6: "Mestrado", 7: "Doutorado" }[Number(item.value)] ?? str(item.value)) : typeof item.value === "number" ? item.value.toLocaleString("pt-BR", { maximumFractionDigits: 2 }) + (item.field === "experience_years" ? " anos" : "") : str(item.value)}
                    </td>
                    <td>
                      {Array.isArray(item.expected)
                        ? item.expected.join(", ")
                        : item.field === "education_level" ? ({ 1: "Fundamental", 2: "Ensino médio", 3: "Técnico", 4: "Superior", 5: "Pós-graduação", 6: "Mestrado", 7: "Doutorado" }[Number(item.expected)] ?? str(item.expected)) : str(item.expected) + (item.field === "experience_years" ? " anos" : "")}
                    </td>
                    <td>{str(item.weight)}%</td>
                    <td>{Number(item.normalized).toLocaleString("pt-BR", { maximumFractionDigits: 2 })}%</td>
                    <td>{Number(item.contribution).toLocaleString("pt-BR", { maximumFractionDigits: 2 })} pontos</td>
                    <td>{item.applicable === false ? "Não aplicável" : item.value == null ? "Falta informação" : item.met ? "Atende ao critério declarado" : Number(item.normalized) > 0 ? "Atende parcialmente" : "Não identificado no perfil"}{Array.isArray(item.missing_choices) && item.missing_choices.length > 0 && <small>Não informado: {item.missing_choices.join(", ")}</small>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          <details>
            <summary>Ver cálculo completo</summary>
            <RecordDetail value={breakdown} />
          </details>
          <h3>Histórico de cálculos</h3>
          {rows(row.scores).map((s) => (
            <p key={s.id}>
              {date(s.created_at)} · Versão{" "}
              {str(obj(s.breakdown).model_version)} · {str(s.total)}%
            </p>
          ))}
        </section>
      )}
      {tab === "evaluations" && (
        <section className="surface padded">
          <ConsensusPanel applicationId={id ?? ""} />
          <TestReviews applicationId={id ?? ""} />
          <div className="section-heading">
            <h2>Avaliações estruturadas</h2>
            {session.data?.permissions.includes("interview.manage") && (
              <button
                className="button secondary"
                onClick={() =>
                  setOperation({
                    title: "Atribuir avaliação",
                    form: "evaluation",
                    initial: { application_id: id },
                    run: (data) => post("/evaluations", data),
                  })
                }
              >
                Atribuir avaliação
              </button>
            )}
          </div>
          {evaluations.data?.items.map((e) => (
            <article className="evaluation" key={e.id}>
              <h3>{label(str(e.category))}</h3>
              {e.sealed ? (
                <p>
                  As avaliações serão reveladas após a conclusão de todos os
                  pareceres.
                </p>
              ) : e.submitted_at ? (
                <p>
                  Nota: {str(e.score)}% · {label(str(e.recommendation))}
                </p>
              ) : (
                <p>Pendente</p>
              )}
              {e.evaluator_id === session.data?.user.id && (
                <button
                  className="button secondary small"
                  onClick={() =>
                    setOperation({
                      title: "Registrar avaliação",
                      schema: simpleSchema({
                        answers: {
                          type: "object",
                          title: "Critérios",
                          properties: Object.fromEntries(
                            rows(e.criteria).map((c) => [
                              str(c.key),
                              {
                                type: "object",
                                title: str(c.name),
                                properties: {
                                  value: {
                                    type: "number",
                                    title: "Nota",
                                    minimum: Number(c.min_value),
                                    maximum: Number(c.max_value),
                                  },
                                  comment: {
                                    type: "string",
                                    title: "Comentário",
                                  },
                                },
                              },
                            ]),
                          ),
                        },
                        recommendation: {
                          enum: ["ADVANCE", "RESERVE", "DO_NOT_ADVANCE"],
                        },
                        reason: {
                          type: "string",
                          title: "Justificativa de alteração",
                        },
                      }),
                      run: (data) =>
                        post("/evaluations/" + e.id + "/submit", {
                          ...data,
                          version: e.version,
                        }),
                    })
                  }
                >
                  Preencher ficha
                </button>
              )}
            </article>
          ))}
        </section>
      )}
      {!candidate && tab === "messages" && (
        <><ApplicationConversation applicationId={id!} />
        {!candidate && <section className="surface padded">
          <h2>Notas internas</h2>
          <button
            className="button secondary"
            onClick={() =>
              setOperation({
                title: "Nova nota interna",
                schema: simpleSchema({
                  subject: { type: "string" },
                  body: { type: "string" },
                  ...(!candidate
                    ? {
                        visibility: {
                          enum: ["TEAM", "RH", "PRIVATE"],
                        },
                      }
                    : {}),
                }),
                run: (data) => post("/applications/" + id + "/messages", data),
              })
            }
          >
            Adicionar nota interna
          </button>
          <div className="message-list">
            {messages.data?.items.filter(message => message.visibility !== "CANDIDATE").map((message) => (
              <article key={message.id}>
                <h3>{str(message.subject)}</h3>
                <small>{date(message.created_at)}</small>
                <p className="preserve">{str(message.body)}</p>
                {!candidate && <NoteActions message={message} />}
              </article>
            ))}
          </div>
        </section>}</>
      )}
      {tab === "checklist" && Boolean(checklist.data?.items.length) && (
        <section className="surface padded">
          <h2>Pré-admissão</h2>
          {checklist.data?.items.length ? (
            checklist.data.items.map((item) => (
              <div className="checklist-row" key={item.id}>
                <span>{str(item.title)}</span>
                <Badge value={item.status} />
                {!candidate && (
                  <button
                    className="text-button"
                    onClick={() =>
                      setOperation({
                        title: "Revisar item",
                        schema: simpleSchema({
                          status: { enum: ["APPROVED", "REJECTED", "PENDING"] },
                          comment: { type: "string" },
                        }),
                        run: (data) =>
                          put("/checklist/" + item.id, {
                            ...data,
                            version: item.version,
                          }),
                      })
                    }
                  >
                    Revisar
                  </button>
                )}
              </div>
            ))
          ) : null}
        </section>
      )}
      {!candidate && tab === "checklist" && !obj(row.candidate).blind && str(row.candidate_id) && <><ReleaseAdmissionDocuments candidateId={str(row.candidate_id)} /><AdmissionDocuments candidateId={str(row.candidate_id)} showReleaseAction={false} /></>}
      <OperationModal
        operation={operation}
        onClose={() => setOperation(null)}
      />
    </>
  );
}
export function SessionsPage() {
  const navigate = useNavigate();
  const client = useQueryClient();
  const [error, setError] = useState<unknown>();
  const [busy, setBusy] = useState("");
  const [showHistory, setShowHistory] = useState(false);
  const query = useQuery({
    queryKey: ["sessions"],
    queryFn: async () => {
      const result = await api<Collection>("/auth/sessions");
      const now = Date.now();
      return result.items.map((row): Row & { active: boolean } => ({ ...row, active: !row.revoked_at && new Date(str(row.expires_at)).getTime() > now }));
    },
    refetchInterval: 30000,
  });
  const sessions = query.data ?? [];
  const active = sessions.filter(row => row.active);
  const visible = (showHistory ? sessions : active).slice().sort((a, b) => Number(Boolean(b.current)) - Number(Boolean(a.current)));
  return <>
    <PageTitle title="Minhas sessões" subtitle="Veja onde sua conta está conectada e gerencie seus acessos." />
    <ErrorBox error={error ?? query.error} />
    <section className="surface sessions-summary">
      <span className="experience-icon"><ShieldCheck size={28} aria-hidden="true" /></span>
      <div><h2>Seus dispositivos conectados</h2><p>{query.isSuccess ? `${active.length} ${active.length === 1 ? "sessão ativa" : "sessões ativas"}.` : "Consultando seus acessos…"} A sessão atual aparece primeiro.</p></div>
      <label className="check-field"><input type="checkbox" checked={showHistory} onChange={event => setShowHistory(event.target.checked)} />Mostrar histórico</label>
    </section>
    {query.isPending && <p role="status">Carregando sessões…</p>}
    {query.isError && <button className="button secondary" onClick={() => void query.refetch()}>Tentar novamente</button>}
    {query.isSuccess && !visible.length && <Empty title="Nenhuma sessão para mostrar" />}
    <div className="session-card-list">{visible.map(row => {
      const device = sessionDevice(str(row.user_agent));
      const Icon = device.mobile ? Smartphone : Monitor;
      return <article className="surface session-card" key={row.id}>
        <span className="session-device-icon"><Icon size={26} aria-hidden="true" /></span>
        <div className="session-card-content">
          <div className="session-card-heading"><h2>{device.name}</h2><span className={"privacy-participation " + (row.active ? "active" : "inactive")}>{row.current && row.active ? "Sessão atual" : row.revoked_at ? "Encerrada" : row.active ? "Ativa" : "Expirada"}</span></div>
          <dl className="session-card-dates"><div><dt>Conectada em</dt><dd>{date(row.created_at)}</dd></div><div><dt>Validade</dt><dd>{date(row.expires_at)}</dd></div></dl>
          <details className="session-technical"><summary>Detalhes do acesso</summary><p><strong>IP registrado:</strong> {str(row.ip)}</p><p><strong>Identificação do navegador:</strong> {str(row.user_agent)}</p></details>
        </div>
        {row.active && <button className="button secondary" disabled={Boolean(busy)} onClick={async () => {
          setBusy(row.id); setError(undefined);
          try {
            await api("/auth/sessions/" + row.id, { method: "DELETE" });
            if (row.current) { setToken(""); client.clear(); navigate("/entrar"); return; }
            await client.invalidateQueries({ queryKey: ["sessions"] });
          } catch (err) { setError(err); } finally { setBusy(""); }
        }}>{busy === row.id ? "Encerrando…" : row.current ? "Sair deste dispositivo" : "Encerrar sessão"}</button>}
      </article>;
    })}</div>
  </>;
}

export function DocumentsPage() {
  const session = useSession();
  const { candidateId } = useParams();
  if (session.isPending) return <p role="status">Carregando seus documentos…</p>;
  if (session.data?.user.kind === "INTERNAL") return <>
    <PageTitle title="Documentos dos candidatos" subtitle="Acesse o perfil de documentos de cada candidato e baixe os arquivos enviados." />
    <RHDocumentProfiles candidateId={candidateId} />
  </>;
  return <>
    <PageTitle
      title="Meus documentos"
      subtitle="Consulte seus documentos admissionais, o termo de consentimento e a ficha de inscrição preenchida."
    />
    <AdmissionDocuments />
    <CandidateRegistrationDocuments />
  </>;
}
