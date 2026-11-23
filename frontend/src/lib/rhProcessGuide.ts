import { type Session } from "./api";
import { isManager } from "./session";

export function canUseRHGuide(session?: Session) {
  return session?.user.kind === "INTERNAL" && !isManager(session) &&
    session.permissions.some(permission => ["vacancy.create", "candidate.move"].includes(permission));
}

export function rhGuideContext(path: string, phase = "") {
  if (/^\/app\/candidaturas\/[^/]+\/?$/.test(path) && phase) {
    const phases: Record<string, { step: number; text: string }> = {
      REGISTER: { step: 0, text: "Confira os dados básicos e o contato antes de liberar o recrutamento." },
      RECRUITMENT: { step: 1, text: "Confira telefone e currículo antes de encaminhar esta candidatura para análise." },
      SELECTION: { step: 2, text: "Analise o currículo e registre aprovação, reprovação ou pendência com justificativa." },
      FORM: { step: 3, text: "Gere o link exclusivo da ficha e acompanhe o preenchimento antes de liberar a entrevista." },
      INTERVIEW: { step: 4, text: "Registre a entrevista e conclua a avaliação antes de encaminhar para o teste." },
      TEST: { step: 5, text: "Acompanhe a realização, corrija as respostas pendentes e confira a nota de aprovação." },
      ADMISSION: { step: 5, text: "Consulte a decisão do RH e as atividades de admissão previstas para esta candidatura." },
    };
    if (phases[phase]) return phases[phase];
  }
  if (/^\/app\/candidatos(?:\/|$)/.test(path)) return { step: 0, text: "Cadastre e confira os dados da pessoa. O histórico de cada vaga permanece separado." };
  if (/^\/app\/vagas(?:\/|$)/.test(path)) return { step: 1, text: "Confira a vaga e acompanhe os candidatos no Kanban. Abra uma candidatura para analisar e movimentar suas etapas." };
  if (/^\/app\/candidaturas(?:-internas)?(?:\/|$)/.test(path)) return { step: 2, text: "Abra a candidatura para conferir a etapa atual, registrar o parecer e acompanhar a ficha. Confirme o avanço após concluir as atividades necessárias." };
  if (/^\/app\/entrevistas(?:\/|$)/.test(path)) return { step: 4, text: "Registre o agendamento, a realização da entrevista e a avaliação correspondente à candidatura." };
  if (/^\/app\/testes(?:\/|$)/.test(path)) return { step: 5, text: "Atribua os testes, acompanhe as tentativas e registre as correções e os resultados." };
  if (/^\/app\/documentos(?:\/|$)/.test(path)) return { step: 2, text: "Consulte os currículos e os documentos permitidos para sua função. Registre a análise na candidatura correspondente." };
  return undefined;
}

