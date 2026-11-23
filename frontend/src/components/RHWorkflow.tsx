import { useState } from "react";
import { Link } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowRight, CheckCircle2 } from "lucide-react";
import { api, obj, post, rows, str, type Row } from "../lib/api";
import { useSession } from "../lib/session";
import { canUseRHGuide } from "../lib/rhProcessGuide";
import { ErrorBox } from "./ui";

const steps = [
  { name: "Cadastro", text: "Consulte os dados básicos e a acessibilidade informados pelo candidato.", path: "candidatos", permission: "candidate.view" },
  { name: "Recrutamento", text: "Abra a vaga, confira as inscrições e analise o currículo e o perfil profissional.", path: "vagas", permission: "vacancy.view" },
  { name: "Seleção de currículo", text: "Analise o currículo e registre aprovação, reprovação ou pendência com justificativa.", path: "candidatos", permission: "candidate.view" },
  { name: "Perguntas e ficha externa", text: "Gere o link exclusivo da candidatura e acompanhe o preenchimento.", path: "candidaturas", permission: "candidate.view" },
  { name: "Entrevistas", text: "Disponibilize o link e as orientações ou agende uma entrevista.", path: "entrevistas", permission: "candidate.view" },
  { name: "Testes", text: "Libere as perguntas da vaga e os testes. Acompanhe as respostas e os resultados.", path: "testes", permission: "test.manage" },
  { name: "Admissão", text: "Registre a decisão, libere o envio e confira os documentos admissionais.", path: "documentos", permission: "document.review" },
];

export function RHWorkflowGuide() {
  const session = useSession();
  if (!canUseRHGuide(session.data)) return null;
  return <section className="surface padded rh-workflow-guide" aria-label="Como conduzir o processo seletivo">
    <div className="section-heading"><div><p className="privacy-eyebrow">GUIA DO RH · 7 ETAPAS</p><h2>Conduza cada etapa da seleção</h2><p>Do cadastro à admissão, encontre o próximo passo e as ferramentas para seguir com o processo.</p></div><Link className="button secondary small" to="/app/candidaturas">Ver candidaturas <ArrowRight size={16} aria-hidden="true" /></Link></div>
    <ol className="rh-workflow-steps">{steps.map((step, index) => <li key={step.name}>
      <span className="rh-step-number" aria-hidden="true">{String(index + 1).padStart(2, "0")}</span><div><h3>{step.name}</h3><p>{step.text}</p>
      {session.data?.permissions.includes(step.permission) && <Link to={"/app/" + step.path} aria-label={"Abrir " + step.name}>{["Ver candidatos", "Gerenciar vagas", "Analisar perfis", "Abrir candidaturas", "Ver entrevistas", "Gerenciar testes", "Conferir documentos"][index]} <ArrowRight size={14} aria-hidden="true" /></Link>}</div>
    </li>)}</ol>
    <p className="rh-workflow-note"><CheckCircle2 size={16} aria-hidden="true" /><span>Você controla o avanço: o candidato é notificado e acessa as atividades liberadas pelo RH.</span></p>
  </section>;
}

const phaseDescriptions: Record<string, string> = {
  REGISTER: "O candidato pode completar seus dados básicos. As atividades seguintes dependem de liberação do RH.",
  RECRUITMENT: "O candidato pode anexar o currículo e preencher o perfil profissional.",
  SELECTION: "O candidato pode preencher a ficha externa. O termo de consentimento é apresentado desde o primeiro acesso.",
  FORM: "O candidato pode responder às perguntas e à ficha deste processo pelo link exclusivo gerado pelo RH.",
  INTERVIEW: "O candidato pode acessar os links e os agendamentos de entrevista.",
  TEST: "O candidato pode responder às perguntas da vaga e realizar os testes.",
  ADMISSION: "O candidato avança para a preparação da admissão. A decisão e a liberação dos documentos são feitas separadamente pelo RH.",
};

function phaseFor(stage: Row, index: number) {
  return str(stage.candidate_phase) || (stage.kind === "INTERVIEW" || stage.kind === "TEST" ? str(stage.kind)
    : ["FINALIST", "OFFER", "HIRED"].includes(str(stage.kind)) ? "ADMISSION" : index === 0 ? "RECRUITMENT" : "SELECTION");
}

export function RHProcessControl({ application, onOpenTab }: { application: Row; onOpenTab?: (tab: string) => void }) {
  const session = useSession();
  const client = useQueryClient();
  const vacancy = useQuery({ queryKey: ["vacancy", application.vacancy_id], queryFn: () => api<Row>("/vacancies/" + application.vacancy_id) });
  const [target, setTarget] = useState("");
  const [reason, setReason] = useState("");
  const [override, setOverride] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>();
  const [saved, setSaved] = useState(false);
  const stages = rows(vacancy.data?.stages).filter(stage => !["OFFER", "HIRED"].includes(str(stage.kind)));
  const currentIndex = stages.findIndex(stage => stage.id === application.stage_id);
  const next = stages[currentIndex + 1];
  const selectedId = target || next?.id || str(application.stage_id);
  const selectedIndex = stages.findIndex(stage => stage.id === selectedId);
  const selected = stages[selectedIndex];
  const active = ["ACTIVE", "RESERVE"].includes(str(application.status));
  const canMove = Boolean(session.data?.permissions.includes("candidate.move"));
  const permissions = obj(obj(application.candidate_access).permissions);
  const available = [
    ["resume", "Currículo e perfil"], ["selection_registration", "Ficha externa"], ["consent", "Consentimento"],
    ["interviews", "Entrevistas"], ["questions", "Perguntas da vaga"], ["tests", "Testes"],
  ];
  const internal = application.recruitment_type === "INTERNAL";
  const person = internal ? "colaborador" : "candidato";
  const screening = currentIndex >= 0 && phaseFor(stages[currentIndex], currentIndex) === "SELECTION";
  const approveAndMove = screening && selectedId === next?.id && !override;
  const moveTo = async (stageId: string) => {
    if (busy || !canMove || !active || stageId === application.stage_id) return;
    setBusy(true); setError(undefined); setSaved(false);
    try {
      const updated = await post<Row>("/applications/" + application.id + (approveAndMove ? "/approve-screening" : "/move"), approveAndMove ? { reason, version: application.version } : { stage_id: stageId, reason, override, version: application.version });
      client.setQueryData(["application", application.id], updated);
      setTarget(""); setReason(""); setOverride(false); setSaved(true);
      await Promise.all(["application", "candidate-processes", "vacancy-applications", "dashboard", "rh-applications", "candidate-journey", "applications", "resume-screening"].map(key => client.invalidateQueries({ queryKey: [key] })));
    } catch (err) { setError(err); } finally { setBusy(false); }
  };
  const tools = [
    { tab: "profile", title: "Conferir currículo", text: "Consulte os dados e o currículo antes de registrar o parecer.", permission: "candidate.view" },
    { tab: "selection", title: "Consultar ficha e consentimento", text: "Confira os dados preenchidos e o termo aceito.", permission: "candidate.view" },
    { tab: "activities", title: "Agendar entrevista e atribuir teste", text: "Cadastre a atividade, o responsável, as instruções e o prazo.", permission: "candidate.view" },
    { tab: "evaluations", title: "Avaliar e registrar parecer", text: "Preencha as avaliações necessárias para o avanço.", permission: "candidate.evaluate" },
    { tab: "messages", title: "Conversar com " + person, text: "Envie orientações e acompanhe as respostas desta candidatura.", permission: "message.send" },
    { tab: "checklist", title: "Liberar e conferir documentos", text: "Após a decisão, libere o envio e revise as pendências documentais.", permission: "document.review" },
  ];
  return <section className="surface padded rh-process-control" aria-label="Controle das etapas">
    <div className="section-heading"><div><p className="privacy-eyebrow">ACOMPANHAMENTO · {internal ? "SELEÇÃO INTERNA" : "SELEÇÃO EXTERNA"}</p><h2>Agora: {str(application.stage_name)}</h2><p>{str(application.vacancy_title)}</p></div>
      <Link className="button secondary small" to={"/app/vagas/" + application.vacancy_id}>Ver candidatos desta vaga</Link></div>
    <ErrorBox error={vacancy.error ?? error} />
    {vacancy.isPending && <p role="status">Carregando etapas…</p>}
    {saved && <p className="alert success" role="status">Etapa atualizada. As atividades liberadas já estão disponíveis no painel do {person}. A notificação foi registrada; o envio por e-mail depende da configuração.</p>}
    {active && next && <div className="rh-next-step"><span>PRÓXIMA ETAPA</span><h3>{str(next.name)}</h3><p>{screening ? "Confira o currículo acima. Se estiver apto, registre o motivo e confirme abaixo para aprovar e continuar." : "Conclua as atividades da etapa atual e confirme abaixo para continuar."}</p></div>}
    {!active && <p className="muted">Este processo está encerrado ou na fase de decisão. Consulte o histórico e os documentos nas abas abaixo.</p>}
    {canMove && active && vacancy.data && <form onSubmit={async event => {
      event.preventDefault(); await moveTo(selectedId);
    }}>
      <fieldset className="stage-gate-fields" disabled={busy}>
        <label className="field"><span>{override ? "Justificativa da exceção" : approveAndMove ? "Por que o currículo está apto?" : "Observação do RH (opcional)"}</span><input value={reason} required={override || approveAndMove} minLength={override ? 10 : approveAndMove ? 5 : undefined} maxLength={2000} onChange={event => setReason(event.target.value)} placeholder={approveAndMove ? "Ex.: formação e experiência atendem à vaga" : "Se necessário, registre uma observação"} /></label>
      {selected && <p className="muted">Ao continuar: {phaseDescriptions[phaseFor(selected, selectedIndex)]}</p>}
      <button className="button" disabled={busy || !selected || selectedId === application.stage_id || approveAndMove && reason.trim().length < 5}>{busy ? "Atualizando…" : approveAndMove ? "Aprovar currículo e continuar" : "Continuar para " + str(selected?.name)}</button>
      <details className="rh-simple-details"><summary>Voltar ou escolher outra etapa</summary><p className="muted">Use apenas quando precisar ajustar o andamento desta candidatura.</p>
        <label className="field"><span>Escolher etapa</span><select value={selectedId} onChange={event => { setTarget(event.target.value); setSaved(false); }}>{stages.map(stage => <option key={stage.id} value={stage.id}>{str(stage.name)}{stage.id === application.stage_id ? " (atual)" : ""}</option>)}</select></label>
        {obj(vacancy.data.details).allow_override === true && <label className="check-field"><input type="checkbox" checked={override} onChange={event => setOverride(event.target.checked)} /><span>Autorizar exceção com justificativa (mínimo de 10 caracteres)</span></label>}
      </details>
      </fieldset>
    </form>}
    {!canMove && <p className="muted">A movimentação é feita pelo RH responsável por esta vaga.</p>}
    <details className="rh-simple-details"><summary>Ver todas as etapas e o que já está liberado</summary>
      <ol className="rh-process-stages" aria-label="Etapas desta vaga">{stages.map((stage, index) => <li key={stage.id} className={stage.id === application.stage_id ? "current" : ""} aria-current={stage.id === application.stage_id ? "step" : undefined}><span>{index + 1}</span><strong>{str(stage.name)}</strong></li>)}</ol>
      {Object.keys(permissions).length > 0 && <div className="rh-candidate-permissions"><strong>O {person} já pode acessar:</strong><ul>{available.filter(([key]) => permissions[key] === true).map(([key, name]) => <li key={key}><CheckCircle2 size={14} aria-hidden="true" />{name}</li>)}</ul></div>}
    </details>
    {onOpenTab && <details className="rh-simple-details"><summary>Outras ações do RH</summary><nav className="rh-release-tools" aria-label="Ações do RH nesta candidatura">{tools.filter(tool => session.data?.permissions.includes(tool.permission)).map(tool => <button type="button" key={tool.tab} className="rh-tool-button" onClick={() => onOpenTab(tool.tab)}><strong>{tool.title} <ArrowRight size={15} aria-hidden="true" /></strong><span>{tool.text}</span></button>)}</nav></details>}
  </section>;
}
