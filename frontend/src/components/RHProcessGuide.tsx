import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link, useLocation } from "react-router-dom";
import { ArrowLeft, ArrowRight, BookOpen, CircleHelp, ClipboardCheck } from "lucide-react";
import { api, obj, str, type Row, type Session } from "../lib/api";
import { canUseRHGuide, rhGuideContext } from "../lib/rhProcessGuide";
import { Modal } from "./ui";
import { RHGoLive } from "./RHGoLive";

const steps = [
  { name: "Cadastro", purpose: "Reunir os dados pessoais e profissionais da pessoa candidata.", action: "Em Candidatos, cadastre a pessoa se sua função permitir, ou consulte o perfil existente. Confira nome, e-mail, telefone, escolaridade e experiência. Na candidatura, acompanhe o envio do currículo quando o recrutamento for liberado.", condition: "Confira os dados básicos, principalmente nome e contato. Um cadastro não inscreve nem faz a pessoa avançar automaticamente.", next: "Recrutamento", path: "/app/candidatos", permission: "candidate.view" },
  { name: "Recrutamento", purpose: "Divulgar a oportunidade e reunir pessoas interessadas na vaga correta.", action: "Cadastre ou selecione a vaga, confira requisitos, quantidade e prazo. Acompanhe as inscrições e registre a origem de cada candidatura, como WhatsApp, Instagram, LinkedIn ou indicação.", condition: "No fluxo completo, o candidato deve ter telefone e currículo disponível antes da análise. O RH confirma a mudança de etapa.", next: "Seleção de currículo", path: "/app/vagas", permission: "vacancy.view" },
  { name: "Seleção de currículo", purpose: "Verificar se a formação e a experiência atendem aos requisitos da vaga.", action: "Na Triagem de currículos da vaga, visualize o PDF, confira o perfil e o ranking. Use Apto e avançar ou Não apto para esta vaga e confirme a decisão.", condition: "O currículo precisa estar aprovado para avançar no fluxo completo. Um parecer reprovado ou pendente bloqueia o avanço. Para encerrar a candidatura, use Registrar decisão → Não selecionada.", next: "Perguntas e ficha externa", path: "/app/candidaturas", permission: "candidate.view" },
  { name: "Perguntas e ficha externa", purpose: "Obter as respostas de triagem e informações complementares desta oportunidade.", action: "Na candidatura, avance para esta etapa e clique em Gerar link da ficha. Copie o link exclusivo ou marque o envio por e-mail, se disponível. Acompanhe a situação e consulte as respostas antes de prosseguir.", condition: "A ficha deve estar preenchida. Link disponibilizado e preenchimento pendente ainda não concluem a etapa. O link vale sete dias; gerar outro invalida o anterior.", next: "Entrevista", path: "/app/candidaturas", permission: "candidate.view" },
  { name: "Entrevista", purpose: "Conhecer as experiências, habilidades, comunicação e compatibilidade com a função.", action: "Em Entrevistas e testes da candidatura, agende a conversa com data, horário, modalidade e responsável. Registre realização, cancelamento ou não comparecimento. Na aba Avaliações, atribua e preencha a ficha correspondente.", condition: "No fluxo completo, as avaliações devem estar concluídas com parecer favorável ao avanço. Agendar a entrevista, sozinho, não conclui a avaliação.", next: "Teste", path: "/app/entrevistas", permission: "candidate.view" },
  { name: "Teste", purpose: "Avaliar os conhecimentos e as habilidades exigidos para a função.", action: "Cadastre e atribua o teste à candidatura, com instruções, questões, prazo e nota de aprovação. Acompanhe a realização e corrija as respostas que exigem avaliação humana, registrando nota e comentário.", condition: "Para sair de uma etapa de teste obrigatória, os testes atribuídos precisam estar corrigidos e atender à nota configurada. O resultado pode ser aprovado, reprovado ou pendente.", next: "Decisão do RH, finalistas e demais etapas da vaga", path: "/app/testes", permission: "test.manage" },
];

export function RHGuideContext({ onOpen }: { onOpen: (step: number) => void }) {
  const location = useLocation();
  const applicationId = location.pathname.match(/^\/app\/candidaturas\/([^/]+)\/?$/)?.[1];
  const application = useQuery({ queryKey: ["application", applicationId], queryFn: () => api<Row>("/applications/" + applicationId), enabled: Boolean(applicationId) });
  const context = rhGuideContext(location.pathname, str(obj(application.data?.candidate_access).phase));
  if (!context) return null;
  return <aside className="rh-guide-context" aria-label="Orientação para esta tela"><CircleHelp size={19} aria-hidden="true" /><p>{Boolean(application.data?.stage_name) && <strong>Etapa atual: {str(application.data?.stage_name)}. </strong>}{context.text}</p><button className="text-button" onClick={() => onOpen(context.step)}>Como usar esta etapa</button></aside>;
}

export function RHProcessGuide({ open, onOpenChange, initialStep, session }: { open: boolean; onOpenChange: (open: boolean) => void; initialStep?: number; session: Session }) {
  const [current, setCurrent] = useState(initialStep ?? 0);
  const [section, setSection] = useState<"overview" | "areas" | "process" | "launch" | "routine">(initialStep === undefined ? "overview" : "process");
  if (!canUseRHGuide(session)) return null;
  const step = steps[current];
  return <Modal open={open} onOpenChange={onOpenChange} title="Como funciona o sistema">
    <div className="rh-process-guide"><div className="rh-guide-welcome"><BookOpen size={26} aria-hidden="true" /><div><strong>Seu guia interativo do Porto Aurora Talentos</strong><p>Da publicação da vaga à admissão: descubra onde clicar, o que conferir e como liberar cada atividade.</p></div></div>
      <nav className="rh-go-live-nav" aria-label="Seções do guia">{([{ id: "overview", name: "Passeio interativo" }, { id: "areas", name: "Áreas do sistema" }, { id: "process", name: "Fluxo seletivo" }, { id: "launch", name: "Antes de começar" }, { id: "routine", name: "Rotina e dúvidas" }] as const).map(item => <button key={item.id} aria-pressed={section === item.id} className={section === item.id ? "active" : ""} onClick={() => setSection(item.id)}>{item.name}</button>)}</nav>
      {section !== "process" && <RHGoLive section={section} session={session} onClose={() => onOpenChange(false)} onProcess={() => { setCurrent(0); setSection("process"); }} />}
      {section === "process" && <>
      <nav className="rh-guide-step-list" aria-label="Etapas do guia">{steps.map((item, index) => <button key={item.name} aria-pressed={current === index} className={current === index ? "active" : ""} onClick={() => setCurrent(index)}><span>{index + 1}</span>{item.name}</button>)}</nav>
      <section className="rh-guide-step" aria-live="polite"><p className="privacy-eyebrow">ETAPA {current + 1} DE 6</p><h2>{step.name}</h2><p>{step.purpose}</p><dl><dt>O que fazer</dt><dd>{step.action}</dd><dt>Antes de avançar</dt><dd>{step.condition}</dd><dt>Próxima etapa</dt><dd>{step.next}</dd></dl>
        {session.permissions.includes(step.permission) && <Link className="button secondary small" to={step.path} onClick={() => onOpenChange(false)}>Acessar {step.name}<ArrowRight size={15} aria-hidden="true" /></Link>}
      </section>
      <div className="rh-guide-rules"><ClipboardCheck size={20} aria-hidden="true" /><div><strong>Como acompanhar e movimentar</strong><p>Abra a vaga e consulte Etapas da seleção. No cartão, use Ver o que o candidato fez e Liberar próxima etapa; arrastar pela alça para a direita também abre a confirmação. Se houver alguma pendência, o sistema informa o que precisa ser corrigido. Registrar um parecer não faz a pessoa avançar.</p><p>As etapas e atividades obrigatórias seguem as regras configuradas para a vaga. As ações disponíveis dependem das permissões da sua função.</p><p>Ao preencher a quantidade de aprovados, as demais candidaturas ativas ou em reserva são encerradas como não selecionadas e os retornos por e-mail são preparados. O envio de e-mails precisa estar configurado.</p></div></div>
      <footer className="rh-guide-footer"><button className="button secondary" disabled={current === 0} onClick={() => setCurrent(current - 1)}><ArrowLeft size={16} aria-hidden="true" />Anterior</button><button className="text-button" onClick={() => onOpenChange(false)}>Fechar guia</button><button className="button" onClick={() => current === steps.length - 1 ? onOpenChange(false) : setCurrent(current + 1)}>{current === steps.length - 1 ? "Concluir guia" : "Próxima etapa"}{current < steps.length - 1 && <ArrowRight size={16} aria-hidden="true" />}</button></footer>
      </>}
      {section !== "process" && <footer className="rh-guide-footer"><span className="muted">Guia exclusivo para o RH</span><button className="button secondary" onClick={() => onOpenChange(false)}>Fechar guia</button></footer>}
    </div>
  </Modal>;
}
