import { afterEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { InternalCareersPage } from "./InternalCareers";

const session = vi.hoisted(() => ({ data: undefined as undefined | { permissions: string[] }, isPending: false }));
vi.mock("../lib/session", () => ({ useSession: () => session }));
afterEach(() => { cleanup(); vi.unstubAllGlobals(); session.data = undefined; });
function renderPortal() {
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><MemoryRouter><InternalCareersPage /></MemoryRouter></QueryClientProvider>);
}
it("shows published internal vacancies to visitors before login", async () => {
  const fetch = vi.fn(async () => new Response(JSON.stringify({ items: [{ id: "1", slug: "analista", title: "Analista", quantity: 1 }], total: 1 }), { status: 200 }));
  vi.stubGlobal("fetch", fetch);
  renderPortal();
  expect(screen.getByRole("link", { name: "Fazer inscrição de colaborador" })).toHaveAttribute("href", "/cadastro-colaborador");
  expect(screen.getByRole("link", { name: "Entrar na área do colaborador" })).toHaveAttribute("href", "/entrar-colaborador");
  expect(screen.getByRole("link", { name: "Entrar na área dos gestores" })).toHaveAttribute("href", "/entrar-gestor");
  expect(screen.queryByRole("link", { name: "Área do colaborador" })).not.toBeInTheDocument();
  expect(screen.getByRole("link", { name: /Site do terminal/ })).toHaveAttribute("href", "https://www.portoaurora.example/");
  expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("Novas possibilidades.");
  expect(await screen.findByRole("link", { name: "Ver vaga Analista" })).toHaveAttribute("href", "/oportunidades-internas/analista");
  expect(screen.getByRole("link", { name: "Ver vaga Analista" })).toHaveClass("job-row");
  expect(screen.queryByText("Acesso de colaborador necessário")).not.toBeInTheDocument();
  expect(fetch.mock.calls.some(args => String((args as unknown[])[0]).includes("/public/internal-vacancies"))).toBe(true);
});
it("loads only the internal endpoint and links each vacancy to its internal detail", async () => {
  session.data = { permissions: ["internal.view"] };
  const fetch = vi.fn(async () => new Response(JSON.stringify({ items: [{ id: "1", slug: "analista", title: "Analista", city: "Barcarena", quantity: 1, modality: "PRESENCIAL", deadline: "2026-12-01T12:00:00Z" }], total: 1, page_size: 25 }), { status: 200 }));
  vi.stubGlobal("fetch", fetch); renderPortal();
  expect(screen.getByRole("link", { name: /Minha ficha interna/ })).toHaveAttribute("href", "/candidato/perfil#ficha-interna");
  expect(await screen.findByRole("link", { name: "Ver vaga Analista" })).toHaveAttribute("href", "/oportunidades-internas/analista");
  fireEvent.change(screen.getByRole("textbox", { name: "Buscar vagas internas" }), { target: { value: "Analista" } });
  await waitFor(() => expect(fetch.mock.calls.some(args => String((args as unknown[])[0]).includes("/public/internal-vacancies?q=Analista"))).toBe(true));
  expect(fetch.mock.calls.every(args => !String((args as unknown[])[0]).includes("/public/vacancies"))).toBe(true);
});
