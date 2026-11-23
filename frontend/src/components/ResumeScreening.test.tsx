import { afterEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { ResumeScreening } from "./ResumeScreening";

vi.mock("./ResumePreview", () => ({ default: () => <div aria-label="Páginas do currículo">PDF em visualização</div> }));

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
function setup(permissions = ["candidate.view", "candidate.move", "candidate.select", "message.send"]) {
  let rejected = false;
  let advanced = false;
  const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
    if (init?.method === "POST") { rejected = url.endsWith("/decision"); advanced = url.endsWith("/approve-screening"); return new Response(JSON.stringify({ stage_name: "Ficha do processo" })); }
    if (url.includes("/documents?")) return new Response(JSON.stringify({ items: [] }));
    if (url.endsWith("/rejection-email")) return new Response(JSON.stringify({ delivery_enabled: true, test_mode: true, subject: "Retorno da seleção", body: "Agradecemos sua participação. Não seguiremos com sua candidatura nesta vaga." }));
    if (url.endsWith("/documents/cv-1/download")) {
      const response = new Response("%PDF-1.7 test", { headers: { "Content-Type": "application/pdf" } });
      response.blob = vi.fn().mockResolvedValue({ arrayBuffer: async () => new TextEncoder().encode("%PDF-1.7 test").buffer });
      return response;
    }
    const showRejected = url.includes("status=REJECTED");
    const items = (rejected || advanced) && !showRejected ? [] : [{ id: "application-1", version: 4, candidate_id: "candidate-1", candidate: { name: "Pessoa Teste", profile: {} }, stage_name: "Seleção de currículo", status: showRejected ? "REJECTED" : "ACTIVE", cv_id: "cv-1", recruitment_type: "INTERNAL", compatibility: { percentage: 85, status: "CALCULATED" }, compatibility_rank: 1 }];
    return new Response(JSON.stringify({ items, total: items.length, page: 1, page_size: 25 }));
  });
  vi.stubGlobal("fetch", fetchMock);
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  client.setQueryData(["session"], { user: { kind: "INTERNAL" }, permissions });
  render(<QueryClientProvider client={client}><MemoryRouter><ResumeScreening vacancyId="vacancy-1" stages={[]} /></MemoryRouter></QueryClientProvider>);
  return { client, fetchMock };
}

it("exige justificativa e confirmação antes de encerrar somente a candidatura escolhida", async () => {
  const { client, fetchMock } = setup();
  fireEvent.click(await screen.findByRole("button", { name: "Não apto para esta vaga" }));
  const dialog = screen.getByRole("dialog", { name: "Não apto para esta vaga" });
  const confirm = within(dialog).getByRole("button", { name: "Confirmar não apto e enviar retorno" });
  expect(confirm).toBeDisabled();
  expect(fetchMock.mock.calls.some(([, init]) => init?.method === "POST")).toBe(false);
  fireEvent.change(within(dialog).getByLabelText("Justificativa profissional"), { target: { value: "Experiência exigida para a função não comprovada" } });
  await waitFor(() => expect(confirm).toBeEnabled());
  fireEvent.click(confirm);
  await screen.findByText("Candidatura encerrada nesta vaga. E-mail de retorno colocado na fila de envio. O cadastro e o currículo foram preservados.");
  const call = fetchMock.mock.calls.find(([, init]) => init?.method === "POST");
  expect(call?.[0]).toBe("/api/v1/applications/application-1/decision");
  expect(JSON.parse(String(call?.[1]?.body))).toEqual({ decision: "REJECTED", reason: "Experiência exigida para a função não comprovada", version: 4, send_rejection_email: true });
  await screen.findByText("Nenhum currículo nesta visualização");
  fireEvent.change(screen.getByLabelText("Quais currículos mostrar?"), { target: { value: "REJECTED" } });
  await screen.findByRole("heading", { name: "Pessoa Teste" });
  expect(screen.queryByRole("button", { name: "Não apto para esta vaga" })).not.toBeInTheDocument();
  client.clear();
});

it("abre o currículo na própria tela sem iniciar download", async () => {
  const { client, fetchMock } = setup();
  fireEvent.click(await screen.findByRole("button", { name: "Visualizar currículo" }));
  const dialog = await screen.findByRole("dialog", { name: "Currículo · Pessoa Teste" });
  expect(await within(dialog).findByText("PDF em visualização")).toBeVisible();
  expect(fetchMock.mock.calls.some(([url]) => url.endsWith("/documents/cv-1/download"))).toBe(true);
  expect(document.querySelector("a[download]")).toBeNull();
  client.clear();
});

it("aprova e avança retirando a pessoa da triagem", async () => {
  const { client, fetchMock } = setup();
  expect(await screen.findByText("85% de compatibilidade")).toBeVisible();
  expect(screen.getByText("1º no ranking")).toBeVisible();
  fireEvent.click(await screen.findByRole("button", { name: "Apto e avançar" }));
  fireEvent.change(screen.getByLabelText("Justificativa profissional"), { target: { value: "Formação e experiência atendem aos requisitos" } });
  fireEvent.click(screen.getByRole("button", { name: "Confirmar apto e avançar" }));
  await screen.findByText(/Triagem aprovada/);
  const call = fetchMock.mock.calls.find(([, init]) => init?.method === "POST");
  expect(call?.[0]).toBe("/api/v1/applications/application-1/approve-screening");
  expect(JSON.parse(String(call?.[1]?.body))).toEqual({ version: 4, reason: "Formação e experiência atendem aos requisitos" });
  await screen.findByText("Nenhum currículo nesta visualização");
  client.clear();
});

it("mantém consulta disponível sem oferecer decisões a quem não tem permissão", async () => {
  const { client } = setup(["candidate.view"]);
  await screen.findByRole("heading", { name: "Pessoa Teste" });
  expect(screen.getByRole("button", { name: "Visualizar currículo" })).toBeEnabled();
  expect(screen.queryByRole("button", { name: "Apto e avançar" })).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Não apto para esta vaga" })).not.toBeInTheDocument();
  client.clear();
});
