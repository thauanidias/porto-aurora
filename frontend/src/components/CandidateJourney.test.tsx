import { afterEach, expect, it, vi } from "vitest";
import { act, cleanup, render, screen, waitFor } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { CandidateJourneyBanner, StageGate } from "./CandidateJourney";
import { ApplicationQuestions } from "./CandidateQuestions";
import type { CandidateJourney } from "../lib/candidateJourney";

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

function journey(enabled: boolean): CandidateJourney {
  const section = { enabled, title: "Atividade", path: "perfil", reason: "Etapa" };
  return { phase: enabled ? "SELECTION" : "REGISTER", processes: [], sections: {
    basic_profile: section, resume: section, professional_profile: section, questions: section,
    selection_registration: section, consent: section, sensitive_profile: section, messages: section,
    interviews: { ...section, enabled: false }, tests: { ...section, enabled: false }, admission: { ...section, enabled: false },
  } };
}

it("mantém os campos invisíveis até a liberação pelo RH", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify(journey(false)))));
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><StageGate section="selection_registration" title="Ficha externa">
    <label>Nome do dependente<input /></label><button>Salvar ficha</button>
  </StageGate></QueryClientProvider>);
  await waitFor(() => expect(client.getQueryState(["candidate-journey"])?.status).toBe("success"));
  expect(screen.queryByLabelText("Nome do dependente")).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Salvar ficha" })).not.toBeInTheDocument();
  await act(async () => { client.setQueryData(["candidate-journey"], journey(true)); });
  await waitFor(() => expect(screen.getByLabelText("Nome do dependente")).toBeEnabled());
  expect(screen.getByRole("button", { name: "Salvar ficha" })).toBeEnabled();
  expect(screen.queryByText("Liberado: Ficha externa")).not.toBeInTheDocument();
  client.clear();
});

it("não bloqueia controles do RH pela etapa do candidato", () => {
  const fetchMock = vi.fn();
  vi.stubGlobal("fetch", fetchMock);
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  client.setQueryData(["session"], { user: { kind: "INTERNAL" }, permissions: ["document.review"] });
  render(<QueryClientProvider client={client}><StageGate section="admission" title="Documentos" allowed={false}>
    <button>Inserir documento pelo RH</button>
  </StageGate></QueryClientProvider>);
  expect(screen.getByRole("button", { name: "Inserir documento pelo RH" })).toBeEnabled();
  expect(screen.queryByText("Controles disponíveis para o RH.")).not.toBeInTheDocument();
  expect(fetchMock).not.toHaveBeenCalled();
  client.clear();
});

it("mostra a etapa liberada e direciona à candidatura correta", async () => {
  const data = journey(true);
  data.processes = [{ id: "application-1", vacancy_title: "Operador", stage_name: "Seleção curricular",
    phase: "SELECTION", phase_label: "Seleção de currículo", rank: 2, status: "ACTIVE", active: true,
    permissions: Object.fromEntries(Object.entries(data.sections).map(([key, value]) => [key, value.enabled])) as CandidateJourney["processes"][number]["permissions"],
  }];
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify(data))));
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><MemoryRouter><CandidateJourneyBanner /></MemoryRouter></QueryClientProvider>);
  await screen.findByRole("heading", { name: "Seleção de currículo" });
  expect(screen.getByRole("link", { name: "Acompanhar candidatura" })).toHaveAttribute("href", "/candidato");
  expect(screen.getAllByText("Aguardando RH")).toHaveLength(2);
  client.clear();
});

it("mantém as perguntas de outra candidatura bloqueadas mesmo com perfil global liberado", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify(journey(true)))));
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><MemoryRouter><ApplicationQuestions application={{ id: "other", version: 1,
    candidate_access: { permissions: { questions: false } }, selection_questions: [{ key: "interest", label: "Por que deseja participar?", kind: "TEXT" }],
  }} /></MemoryRouter></QueryClientProvider>);
  await waitFor(() => expect(client.getQueryState(["candidate-journey"])?.status).toBe("success"));
  expect(screen.queryByLabelText("Por que deseja participar?")).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Enviar respostas" })).not.toBeInTheDocument();
  client.clear();
});

it("aguarda a liberação explícita do RH para documentos após os testes", async () => {
  const data = journey(true);
  data.phase = "ADMISSION";
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify(data))));
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><MemoryRouter><CandidateJourneyBanner /></MemoryRouter></QueryClientProvider>);
  await screen.findByText("Aguardando liberação da admissão");
  expect(screen.queryByText("Etapa liberada: Admissão")).not.toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Acompanhar candidatura" })).toHaveAttribute("href", "/candidato");
  client.clear();
});
