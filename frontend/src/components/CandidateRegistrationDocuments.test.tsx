import { afterEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { CandidateRegistrationDocuments } from "./CandidateRegistrationDocuments";

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

function setup() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><MemoryRouter><CandidateRegistrationDocuments /></MemoryRouter></QueryClientProvider>);
  return client;
}

it("consulta a ficha salva e o termo realmente aceito, sem editar nem reenviar dados", async () => {
  const fetchMock = vi.fn(async (url: string) => {
    if (url.endsWith("/journey")) return new Response(JSON.stringify({ sections: { selection_registration: { enabled: true } } }));
    if (url.includes("my-consent-receipts?page_number=1")) return new Response(JSON.stringify({ items: [{ id: "other", context: "CANDIDATURA" }], total: 26, page_size: 25 }));
    if (url.includes("my-consent-receipts?page_number=2")) return new Response(JSON.stringify({ items: [{ id: "receipt-test", context: "CADASTRO", protocol: "TEST-123", document_code: "FORM-PPO-RH-002.09", created_at: "2026-10-09T12:00:00Z" }], total: 26, page_size: 25 }));
    if (url.endsWith("/schema")) return new Response(JSON.stringify({
      type: "object", properties: {
        desired_position: { type: "string", title: "Cargo pretendido" },
        personal: { $ref: "#/$defs/Personal", title: "Dados pessoais" },
        dependents: { type: "array", title: "Dependentes", items: { $ref: "#/$defs/Dependent" } },
      }, $defs: {
        Personal: { type: "object", properties: { name: { type: "string", title: "Nome completo" }, birth_date: { anyOf: [{ type: "string", format: "date" }, { type: "null" }], title: "Data de nascimento" } } },
        Dependent: { type: "object", properties: { name: { type: "string", title: "Nome do dependente" } } },
      },
    }));
    if (url.endsWith("/selection-registration")) return new Response(JSON.stringify({
      data: { desired_position: "Operador de teste", personal: { name: "Pessoa de Teste", birth_date: "1990-01-02" }, dependents: [{ name: "Dependente de Teste" }] },
      saved_at: "2026-10-09T12:00:00Z", confirmed_at: null,
    }));
    if (url.endsWith("/receipt-test")) return new Response(JSON.stringify({
      id: "receipt-test", name: "Pessoa de Teste", email: "pessoa@example.com", protocol: "TEST-123",
      created_at: "2026-10-09T12:00:00Z", document_snapshot: { paragraphs: ["Texto histórico do termo aceito neste teste."] },
    }));
    throw new Error("Requisição inesperada: " + url);
  });
  vi.stubGlobal("fetch", fetchMock);
  const client = setup();
  fireEvent.click(await screen.findByRole("button", { name: "Visualizar ficha preenchida" }));
  const formDialog = await screen.findByRole("dialog", { name: "Ficha de inscrição preenchida" });
  expect(await within(formDialog).findByText("Pessoa de Teste")).toBeVisible();
  expect(within(formDialog).getByText("02/01/1990")).toBeVisible();
  expect(within(formDialog).getByText("Dependente de Teste")).toBeVisible();
  expect(formDialog.querySelector("input, textarea, select")).toBeNull();
  fireEvent.click(within(formDialog).getByRole("button", { name: "Fechar" }));
  fireEvent.click(await screen.findByRole("button", { name: "Visualizar termo" }));
  const consentDialog = await screen.findByRole("dialog", { name: "Termo de consentimento aceito" });
  expect(await within(consentDialog).findByText("Texto histórico do termo aceito neste teste.")).toBeVisible();
  expect(screen.queryByRole("button", { name: "Enviar documento" })).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Salvar ficha de inscrição" })).not.toBeInTheDocument();
  expect(fetchMock.mock.calls.every(([url]) => !url.includes("/documents?"))).toBe(true);
  client.clear();
});

it("orienta a completar em Meu perfil quando ainda não há termo ou ficha salva", async () => {
  vi.stubGlobal("fetch", vi.fn(async (url: string) => new Response(JSON.stringify(url.endsWith("/journey") ? { sections: { selection_registration: { enabled: true } } } : url.includes("my-consent-receipts") ? { items: [], total: 0, page_size: 25 } : { data: null, saved_at: null, confirmed_at: null }))));
  const client = setup();
  expect(await screen.findByText("Você ainda não salvou sua ficha de inscrição.")).toBeVisible();
  expect(await screen.findByText("Você ainda não registrou o aceite do termo.")).toBeVisible();
  expect(screen.getByRole("link", { name: "Preencher em Meu perfil" })).toHaveAttribute("href", "/candidato/perfil");
  expect(screen.queryByRole("button", { name: "Visualizar ficha preenchida" })).not.toBeInTheDocument();
  client.clear();
});
