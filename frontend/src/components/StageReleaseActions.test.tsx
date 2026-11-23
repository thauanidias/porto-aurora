import { afterEach, expect, it, vi } from "vitest";
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { createRef } from "react";
import "@testing-library/jest-dom/vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { StageReleaseActions } from "./StageReleaseActions";

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
function setup(type = "EXTERNAL", phase = "SELECTION", canMove = true) {
  const stages = [{ id: "screen", version: 1, name: "Triagem", candidate_phase: "SELECTION" }, { id: "form", version: 1, name: "Ficha do processo", candidate_phase: "FORM" }, { id: "interview", version: 1, name: "Entrevista", candidate_phase: "INTERVIEW" }];
  const application = { id: "app-1", version: 5, vacancy_id: "job-1", stage_id: phase === "FORM" ? "form" : "screen", stage_name: phase === "FORM" ? "Ficha do processo" : "Triagem", candidate: { name: "Pessoa Teste" }, recruitment_type: type, status: "ACTIVE", candidate_access: { phase, permissions: { resume: true, process_form: phase === "FORM" } } };
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  client.setQueryData(["session"], { user: { kind: "INTERNAL" }, permissions: canMove ? ["candidate.view", "candidate.move"] : ["candidate.view"] });
  const fetchMock = vi.fn(async (_url: string, init?: RequestInit) => new Response(JSON.stringify(init?.method === "POST" ? { ...application, version: 6, link: "http://localhost/ficha#token=demo" } : { status: "NOT_SENT" })));
  vi.stubGlobal("fetch", fetchMock);
  const advanceRef = createRef<{ open: () => void }>();
  render(<QueryClientProvider client={client}><MemoryRouter><StageReleaseActions application={application} stages={stages} advanceRef={advanceRef} /></MemoryRouter></QueryClientProvider>);
  return { client, fetchMock, advanceRef };
}

it("opens the same confirmation on drag without saving immediately", () => {
  const { client, fetchMock, advanceRef } = setup();
  act(() => advanceRef.current?.open());
  expect(screen.getByRole("dialog")).toBeVisible();
  expect(fetchMock).not.toHaveBeenCalled();
  client.clear();
});

it("does not open a drag confirmation without move permission", () => {
  const { client, advanceRef } = setup("EXTERNAL", "SELECTION", false);
  act(() => advanceRef.current?.open());
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  client.clear();
});

it.each(["EXTERNAL", "INTERNAL"])("confirma aprovação e liberação para %s com versão e justificativa", async type => {
  const { client, fetchMock } = setup(type);
  fireEvent.click(screen.getByRole("button", { name: "Aprovar currículo e avançar" }));
  const confirm = screen.getByRole("button", { name: "Confirmar liberação" });
  expect(confirm).toBeDisabled();
  fireEvent.change(screen.getByLabelText("Justificativa da aprovação do currículo"), { target: { value: "Currículo atende aos requisitos da vaga" } });
  fireEvent.click(confirm);
  await screen.findByRole("status");
  expect(fetchMock.mock.calls[0][0]).toBe("/api/v1/applications/app-1/approve-screening");
  expect(JSON.parse(String(fetchMock.mock.calls[0][1]?.body))).toEqual({ version: 5, reason: "Currículo atende aos requisitos da vaga" });
  expect(screen.getByRole("status")).toHaveTextContent(type === "INTERNAL" ? "colaborador" : "candidato");
  client.clear();
});

it("gera link da ficha somente quando a atividade está liberada", async () => {
  const { client, fetchMock } = setup("INTERNAL", "FORM");
  fireEvent.click(screen.getByRole("button", { name: "Ver atividades e liberações" }));
  expect(screen.getByText("Painel do colaborador")).toBeVisible();
  fireEvent.click(await screen.findByRole("button", { name: "Gerar link da ficha" }));
  expect(await screen.findByLabelText("Link da ficha · válido por 7 dias")).toHaveValue("http://localhost/ficha#token=demo");
  const mutation = fetchMock.mock.calls.find(([, init]) => init?.method === "POST");
  expect(mutation?.[0]).toBe("/api/v1/applications/app-1/process-form");
  expect(JSON.parse(String(mutation?.[1]?.body))).toEqual({ version: 5, send_email: false });
  client.clear();
});

it("preserva o bloqueio informado pelo servidor", async () => {
  const { client, fetchMock } = setup("EXTERNAL", "FORM");
  fetchMock.mockImplementation(async () => new Response(JSON.stringify({ message: "Aguarde o preenchimento da ficha." }), { status: 409 }));
  fireEvent.click(screen.getByRole("button", { name: "Liberar próxima etapa" }));
  fireEvent.click(screen.getByRole("button", { name: "Confirmar liberação" }));
  await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("Aguarde o preenchimento da ficha."));
  expect(screen.getByRole("dialog")).toBeVisible();
  client.clear();
});

it("não oferece liberação sem permissão do RH", () => {
  const { client } = setup("EXTERNAL", "SELECTION", false);
  expect(screen.queryByRole("button", { name: /Aprovar currículo|Liberar próxima etapa/ })).not.toBeInTheDocument();
  client.clear();
});
