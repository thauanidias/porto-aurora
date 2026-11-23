import { afterEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { RHProcessControl } from "./RHWorkflow";
import type { Row } from "../lib/api";

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
const stages = [
  { id: "screen", name: "Seleção de currículo", candidate_phase: "SELECTION" },
  { id: "form", name: "Ficha do processo", candidate_phase: "FORM" },
  { id: "interview", name: "Entrevista", candidate_phase: "INTERVIEW" },
];
function setup(type = "EXTERNAL", permissions = ["candidate.move", "candidate.view", "message.send", "document.review"]) {
  const application: Row = { id: "application-1", version: 7, vacancy_id: "vacancy-1", stage_id: "screen", stage_name: "Seleção de currículo", vacancy_title: "Operador", status: "ACTIVE", recruitment_type: type };
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  client.setQueryData(["session"], { user: { kind: "INTERNAL" }, permissions });
  client.setQueryData(["vacancy", "vacancy-1"], { stages, details: {} });
  const openTab = vi.fn();
  const fetchMock = vi.fn(async (_url: string, init?: RequestInit) => new Response(JSON.stringify(init?.method === "POST" ? { ...application, stage_id: "form", version: 8 } : { stages, details: {} })));
  vi.stubGlobal("fetch", fetchMock);
  render(<QueryClientProvider client={client}><MemoryRouter><RHProcessControl application={application} onOpenTab={openTab} /></MemoryRouter></QueryClientProvider>);
  return { client, fetchMock, openTab };
}

it.each(["EXTERNAL", "INTERNAL"])("libera a etapa da candidatura %s somente após confirmação, com controle de versão", async type => {
  const { client, fetchMock } = setup(type);
  expect(fetchMock.mock.calls.filter(([, init]) => init?.method === "POST")).toHaveLength(0);
  fireEvent.change(await screen.findByLabelText("Por que o currículo está apto?"), { target: { value: "Currículo conferido pelo RH" } });
  fireEvent.click(screen.getByRole("button", { name: "Aprovar currículo e continuar" }));
  await screen.findByText(/As atividades liberadas já estão disponíveis/);
  const mutation = fetchMock.mock.calls.find(([, init]) => init?.method === "POST");
  expect(mutation?.[0]).toBe("/api/v1/applications/application-1/approve-screening");
  expect(JSON.parse(String(mutation?.[1]?.body))).toEqual({ version: 7, reason: "Currículo conferido pelo RH" });
  expect(client.getQueryData<Row>(["application", "application-1"])?.version).toBe(8);
  client.clear();
});

it("mantém a etapa quando há pendência e mostra a orientação retornada pelo servidor", async () => {
  const { client, fetchMock } = setup();
  fetchMock.mockImplementation(async (_url, init) => new Response(JSON.stringify(init?.method === "POST" ? { message: "Registre a aprovação do currículo antes de avançar." } : { stages, details: {} }), { status: init?.method === "POST" ? 409 : 200 }));
  fireEvent.change(await screen.findByLabelText("Por que o currículo está apto?"), { target: { value: "Currículo conferido pelo RH" } });
  fireEvent.click(screen.getByRole("button", { name: "Aprovar currículo e continuar" }));
  await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("Registre a aprovação do currículo"));
  expect(client.getQueryData(["application", "application-1"])).toBeUndefined();
  expect(screen.queryByText(/As atividades liberadas já estão disponíveis/)).not.toBeInTheDocument();
  client.clear();
});

it("oferece atalhos para executar as atividades no RH", async () => {
  const { client, openTab } = setup("INTERNAL");
  fireEvent.click(await screen.findByText("Outras ações do RH"));
  fireEvent.click(await screen.findByRole("button", { name: /Conversar com colaborador/ }));
  expect(openTab).toHaveBeenCalledWith("messages");
  fireEvent.click(screen.getByRole("button", { name: /Liberar e conferir documentos/ }));
  expect(openTab).toHaveBeenLastCalledWith("checklist");
  client.clear();
});

it("não oferece liberação para quem só pode consultar", async () => {
  const { client } = setup("INTERNAL", ["candidate.view"]);
  await screen.findByText("A movimentação é feita pelo RH responsável por esta vaga.");
  expect(screen.queryByRole("button", { name: /Aprovar currículo e continuar/ })).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: /Continuar para/ })).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: /Liberar e conferir documentos/ })).not.toBeInTheDocument();
  client.clear();
});
