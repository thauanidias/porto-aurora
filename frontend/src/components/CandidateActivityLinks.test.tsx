import { afterEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { RHActivityLinks, CandidateActivityLinks } from "./CandidateActivityLinks";
import type { CandidateJourney } from "../lib/candidateJourney";

vi.mock("../lib/session", () => ({ useSession: () => ({ data: { permissions: ["candidate.move"] } }) }));
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

const activity = { id: "link-1", version: 1, application_id: "application-1", kind: "TEST", title: "Teste de conhecimentos",
  description: "Conclua o teste até amanhã e siga as orientações.", url: "https://example.com/test", active: true, stage_unlocked: false, can_manage: true, vacancy_title: "Operador" };
function renderWithClient(element: React.ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}>{element}</QueryClientProvider>);
  return client;
}
function mockApi(unlocked = false) {
  const data: CandidateJourney = { phase: "TEST", processes: [], sections: {
    tests: { enabled: true, title: "Testes", path: "testes", reason: "" },
  } as CandidateJourney["sections"] };
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => new Response(JSON.stringify(
    url.includes("/journey") ? data : init?.method ? activity : url.includes("/applications?")
      ? { items: [{ id: "application-1", version: 1, vacancy_title: "Operador", stage_name: "Recrutamento" }], total: 1 }
      : { items: [{ ...activity, stage_unlocked: unlocked, ...(!unlocked ? { url: undefined } : {}) }], total: 1 }
  ), { status: 200 })));
}

it("cadastra o link com descrição na candidatura escolhida", async () => {
  mockApi();
  const client = renderWithClient(<RHActivityLinks candidateId="candidate-1" />);
  const title = await screen.findByLabelText("Título da atividade");
  fireEvent.change(title, { target: { value: "Teste externo" } });
  fireEvent.change(screen.getByLabelText("Tipo de atividade"), { target: { value: "TEST" } });
  fireEvent.change(screen.getByLabelText("Link de acesso"), { target: { value: "https://example.com/exam" } });
  fireEvent.change(screen.getByLabelText("Descrição e orientações"), { target: { value: "Responda às questões até sexta-feira." } });
  fireEvent.click(screen.getByRole("button", { name: "Disponibilizar link" }));
  await screen.findByText("Link salvo. O candidato receberá um aviso e poderá acessar quando a etapa estiver liberada.");
  const request = vi.mocked(fetch).mock.calls.find(([, init]) => init?.method === "POST");
  expect(JSON.parse(String(request?.[1]?.body))).toEqual({ application_id: "application-1", kind: "TEST", title: "Teste externo", url: "https://example.com/exam", description: "Responda às questões até sexta-feira." });
  client.clear();
});

it("mantém título e descrição visíveis com acesso bloqueado por candidatura", async () => {
  mockApi();
  const client = renderWithClient(<CandidateActivityLinks kind="TEST" />);
  await screen.findByRole("heading", { name: "Teste de conhecimentos" });
  expect(screen.getByText(activity.description)).toBeVisible();
  expect(screen.getByRole("button", { name: "Acessar teste" })).toBeDisabled();
  expect(screen.queryByRole("link", { name: "Acessar teste" })).not.toBeInTheDocument();
  client.clear();
});

it("oferece o link liberado pelo RH com abertura em nova aba", async () => {
  mockApi(true);
  const client = renderWithClient(<CandidateActivityLinks kind="TEST" />);
  const link = await screen.findByRole("link", { name: "Acessar teste" });
  expect(link).toHaveAttribute("href", activity.url);
  expect(link).toHaveAttribute("target", "_blank");
  expect(link).toHaveAttribute("rel", "noopener noreferrer");
  client.clear();
});
