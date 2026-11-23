import { useQuery } from "@tanstack/react-query";
import { api, rows, type Collection, type Row } from "./api";
import { testAvailability } from "./testAvailability";

export type CandidateAction = { path: string; title: string; description: string; count: number };

export function availableCandidateActions(tests: Collection, interviews: Collection, admission: Row, offers: Collection, now: number, activityLinks: Row[] = []): CandidateAction[] {
  const actions: CandidateAction[] = [
    { path: "testes", title: "Testes liberados", description: "Há testes disponíveis para iniciar ou continuar.", count: tests.items.filter(test => !testAvailability(test, now)).length + activityLinks.filter(link => link.kind === "TEST" && link.stage_unlocked === true && !link.completed_at && link.completed !== true).length },
    { path: "entrevistas", title: "Entrevistas liberadas", description: "Confira os links, as orientações e os detalhes da sua entrevista.", count: interviews.items.filter(interview => interview.stage_unlocked !== false && new Date(String(interview.starts_at)).getTime() > now).length + activityLinks.filter(link => link.kind === "INTERVIEW" && link.stage_unlocked === true && !link.completed_at && link.completed !== true).length },
    { path: "documentos", title: "Envio de documentos liberado", description: "O RH liberou esta área. Confira os documentos aplicáveis ao seu caso.", count: admission.can_upload && rows(admission.items).some(item => !item.document) ? 1 : 0 },
    { path: "ofertas", title: "Carta oferta disponível", description: "Consulte as condições e registre sua resposta.", count: offers.items.filter(offer => offer.status === "SENT" && new Date(String(offer.expires_at)).getTime() > now).length },
  ];
  return actions.filter(action => action.count > 0);
}

export function useCandidateActions(enabled = true) {
  return useQuery({
    queryKey: ["candidate-actions"],
    enabled,
    refetchInterval: 15000,
    queryFn: async () => {
      const [tests, interviews, admission, offers, links] = await Promise.all([
        api<Collection>("/test-assignments"), api<Collection>("/interviews/me"),
        api<Row>("/documents/admission-checklist"), api<Collection>("/offers"),
        api<Collection>("/candidate-activity-links"),
      ]);
      return availableCandidateActions(tests, interviews, admission, offers, Date.now(), links.items);
    },
  });
}
