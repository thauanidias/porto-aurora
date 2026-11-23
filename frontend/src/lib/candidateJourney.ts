import { useQuery } from "@tanstack/react-query";
import { api } from "./api";

export type JourneySection = "basic_profile" | "resume" | "professional_profile" | "questions" | "selection_registration" | "consent" | "sensitive_profile" | "interviews" | "tests" | "admission" | "messages";
export type JourneyAccess = { enabled: boolean; title: string; path: string; reason: string };
export type JourneyProcess = { id: string; vacancy_title: string; stage_name: string; phase: string; phase_label: string; rank: number; status: string; active: boolean; permissions: Record<JourneySection, boolean> };
export type CandidateJourney = { phase: string; sections: Record<JourneySection, JourneyAccess>; processes: JourneyProcess[] };
export function useCandidateJourney(enabled = true) {
  return useQuery({ queryKey: ["candidate-journey"], enabled,
    queryFn: () => api<CandidateJourney>("/candidates/me/journey"),
    refetchInterval: 15000,
  });
}
export const phaseLabels: Record<string, string> = {
  REGISTER: "Cadastro", RECRUITMENT: "Recrutamento", SELECTION: "Seleção de currículo", FORM: "Perguntas e ficha externa",
  INTERVIEW: "Entrevistas", TEST: "Testes", ADMISSION: "Admissão",
};
export const phaseRanks: Record<string, number> = { REGISTER: 0, RECRUITMENT: 1, SELECTION: 2, FORM: 2, INTERVIEW: 3, TEST: 4, ADMISSION: 5 };
