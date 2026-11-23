import { afterEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { CandidateStageActivity } from "./CandidateStageActivity";

vi.mock("../lib/session", () => ({ useSession: () => ({ data: { permissions: ["candidate.view"] } }) }));
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

function setup(form: Record<string, unknown>, tasks: Record<string, unknown> = {}) {
  const application = { id: "app-activity", version: 1, candidate: { name: "Pessoa Teste" }, stage_name: "Ficha do processo", candidate_access: { phase: "FORM" } };
  const fetchMock = vi.fn(async (url: string) => new Response(JSON.stringify(url.endsWith("/stage-task-status") ? tasks : url.endsWith("/process-form") ? form : { ...application, history: [] }), { status: 200 }));
  vi.stubGlobal("fetch", fetchMock);
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><MemoryRouter><CandidateStageActivity application={application} /></MemoryRouter></QueryClientProvider>);
  return { client, fetchMock };
}

it("loads the current candidature only when opened and shows actual submitted status", async () => {
  const { client, fetchMock } = setup({ status: "COMPLETED", registration: { name: "Pessoa Teste" }, answers: { availability: "Manhã" } });
  expect(fetchMock.mock.calls.every(([url]) => url.endsWith("/stage-task-status"))).toBe(true);
  fireEvent.click(screen.getByRole("button", { name: "Ver o que o candidato fez" }));
  expect(await screen.findByText("Respostas enviadas")).toBeVisible();
  expect(await screen.findByText("Manhã")).toBeVisible();
  expect(fetchMock.mock.calls.every(([url]) => url.includes("/applications/app-activity"))).toBe(true);
  expect(screen.getByRole("link", { name: /Abrir dados e arquivos completos/ })).toHaveAttribute("href", "/app/candidaturas/app-activity?aba=selection");
  client.clear();
});

it("shows signed forms green and unanswered questions red with evidence buttons", async () => {
  const { client } = setup({ status: "SENT" }, { status: "PENDING", completed: 1, pending: 1, tasks: [
    { key: "registration", title: "Ficha externa assinada", status: "COMPLETED", detail: "Ficha assinada e recebida", tab: "selection" },
    { key: "questions", title: "Perguntas da vaga", status: "PENDING", detail: "Respostas ainda não enviadas", tab: "selection" },
  ] });
  fireEvent.click(screen.getByRole("button", { name: /Ver o que o candidato fez/ }));
  expect((await screen.findByText("Ficha externa assinada")).closest("article")).toHaveClass("task-completed");
  expect(screen.getByText("Perguntas da vaga").closest("article")).toHaveClass("task-pending");
  expect(screen.getByRole("button", { name: /Visualizar ficha assinada/ })).toBeVisible();
  client.clear();
});

it("shows incomplete work as pending and respects restricted personal answers", async () => {
  const { client } = setup({ status: "PENDING", restricted: true });
  fireEvent.click(screen.getByRole("button", { name: "Ver o que o candidato fez" }));
  expect(await screen.findByText("Em preenchimento")).toBeVisible();
  expect(screen.getByText(/As respostas pessoais exigem permissão específica/)).toBeVisible();
  expect(screen.queryByText("Respostas enviadas")).not.toBeInTheDocument();
  client.clear();
});
