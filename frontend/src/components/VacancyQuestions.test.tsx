import { afterEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { VacancyQuestions } from "./VacancyQuestions";

vi.mock("../lib/session", () => ({ useSession: () => ({ data: { permissions: ["vacancy.edit"] } }) }));
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
it("lets RH create a required yes/no question without technical fields", async () => {
  const fetch = vi.fn(async (_url: string, init?: RequestInit) => new Response(JSON.stringify(init?.method === "PUT" ? { id: "vacancy", version: 3 } : { id: "vacancy", version: 2, details: { questions: [] } }), { status: 200 }));
  vi.stubGlobal("fetch", fetch);
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><VacancyQuestions vacancyId="vacancy" /></QueryClientProvider>);
  fireEvent.click(screen.getByRole("button", { name: "Configurar perguntas" }));
  fireEvent.click(await screen.findByRole("button", { name: "Adicionar pergunta" }));
  fireEvent.change(screen.getByLabelText("Pergunta 1"), { target: { value: "Pode trabalhar pela manhã?" } });
  fireEvent.change(screen.getByLabelText("Tipo da pergunta 1"), { target: { value: "BOOLEAN" } });
  fireEvent.click(screen.getByRole("button", { name: "Salvar perguntas" }));
  await waitFor(() => expect(fetch.mock.calls.some(([url, init]) => url === "/api/v1/vacancies/vacancy/questions" && init?.method === "PUT")).toBe(true));
  const request = fetch.mock.calls.find(([, init]) => init?.method === "PUT")!;
  const body = JSON.parse(request[1]!.body as string);
  expect(body.version).toBe(2);
  expect(body.questions[0]).toMatchObject({ label: "Pode trabalhar pela manhã?", kind: "BOOLEAN", required: true, options: [] });
  expect(body.questions[0].key).toMatch(/^q_/);
});
