import { afterEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { CareersPage, JobPage } from "./Careers";

const auth = vi.hoisted(() => ({ loggedIn: true }));
vi.mock("../lib/session", () => ({ useSession: () => ({ data: auth.loggedIn ? { user: { kind: "CANDIDATO" } } : undefined, isPending: false }) }));
afterEach(() => { auth.loggedIn = true; cleanup(); vi.unstubAllGlobals(); window.history.replaceState({}, "", "/"); });

it("mostra a contagem singular e apresenta a modalidade da vaga de forma legível", async () => {
  vi.stubGlobal("fetch", vi.fn(async (url: string) => new Response(JSON.stringify(url.includes("/public/vacancies?") ? { items: [{ id: "vaga-1", slug: "operador", title: "Operador", code: "Porto Aurora-01", city: "Barcarena", state: "PA", modality: "PRESENCIAL", contract_type: "CLT" }], total: 1 } : {}), { status: 200 })));
  render(<QueryClientProvider client={new QueryClient()}><MemoryRouter><CareersPage /></MemoryRouter></QueryClientProvider>);
  expect(await screen.findByText("1 oportunidade")).toBeVisible();
  expect(screen.getByRole("link", { name: /Operador.*Ver oportunidade/ })).toHaveTextContent("Presencial");
  expect(screen.getByRole("link", { name: /Operador.*Ver oportunidade/ })).toHaveAttribute("href", "/carreiras/vagas/operador");
});

it("distingue falha de consulta de ausência de vagas", async () => {
  vi.stubGlobal("fetch", vi.fn(async (url: string) => url.includes("/public/vacancies?") ? new Response(JSON.stringify({ message: "Consulta indisponível" }), { status: 503 }) : new Response("{}", { status: 200 })));
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><MemoryRouter><CareersPage /></MemoryRouter></QueryClientProvider>);
  expect(await screen.findByRole("button", { name: "Tentar novamente" })).toBeVisible();
  expect(screen.queryByText("Nenhuma oportunidade disponível neste momento")).not.toBeInTheDocument();
  expect(screen.queryByText("0 oportunidades")).not.toBeInTheDocument();
});

function Destination() { const location = useLocation(); return <p data-testid="destination">{location.pathname + location.search}</p>; }
function jobPage(path: string, existing = false, accepted = true, ready = true) {
  window.history.replaceState({}, "", path);
  vi.stubGlobal("fetch", vi.fn(async (url: string) => new Response(JSON.stringify(url.includes("/public/vacancies/") ? {
    id: "vaga", title: "Estágio de TI", city: "Belém", details: {}, stages: [],
  } : url.includes("/application-readiness") ? { ready, missing: ready ? [] : ["Telefone", "Curriculo"], cv_id: ready ? "cv-novo" : null } : url.includes("/documents?") ? { items: [{ id: "cv-novo", type_name: "CURRICULO", filename: "curriculo.pdf", revision: 1, scan_status: "CLEAN" }] } : url.includes("/privacy/my-consent-receipts") ? { items: accepted ? [{ context: "CADASTRO" }] : [], total: accepted ? 1 : 0, page_size: 25 } : url.includes("/applications?") ? { items: existing ? [{ id: "inscricao-existente" }] : [], total: existing ? 1 : 0 } : { id: "nova-candidatura" }), { status: 200 })));
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><MemoryRouter initialEntries={[path]}><Routes>
    <Route path="/carreiras/vagas/:slug" element={<JobPage />} />
    <Route path="/cadastro" element={<Destination />} />
    <Route path="/candidato/perfil" element={<Destination />} />
    <Route path="/candidato/candidaturas/:id" element={<Destination />} />
  </Routes></MemoryRouter></QueryClientProvider>);
}

it("registra a inscrição antes de liberar o currículo e direciona para recrutamento", async () => {
  jobPage("/carreiras/vagas/estagio?candidatar=1");
  expect(await screen.findByText("Termo de consentimento já aceito no seu cadastro.")).toBeVisible();
  expect(screen.getByRole("combobox", { name: "Currículo para esta vaga" })).toBeEnabled();
  expect(screen.queryByRole("checkbox")).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Confirmar candidatura" }));
  expect(await screen.findByTestId("destination")).toHaveTextContent("/candidato/candidaturas/nova-candidatura");
  const enrollment = vi.mocked(fetch).mock.calls.find(([url, init]) => String(url).endsWith("/applications") && init?.method === "POST");
  expect(JSON.parse(String(enrollment?.[1]?.body))).toMatchObject({ vacancy_id: "vaga", enrollment: true });
  expect(JSON.parse(String(enrollment?.[1]?.body))).not.toHaveProperty("answers");
});

it("reabre a candidatura ao retornar do perfil e seleciona o currículo enviado", async () => {
  jobPage("/carreiras/vagas/estagio?candidatar=1");
  expect(await screen.findByRole("dialog")).toHaveTextContent("Candidatura · Estágio de TI");
  await screen.findByRole("option", { name: "curriculo.pdf · versão 1" });
  expect(screen.getByRole("combobox", { name: "Currículo para esta vaga" })).toHaveValue("cv-novo");
});

it("mostra o acompanhamento em vez de permitir inscrição duplicada", async () => {
  jobPage("/carreiras/vagas/estagio?candidatar=1", true);
  expect(await screen.findByRole("link", { name: "Ver minha candidatura" })).toHaveAttribute("href", "/candidato/candidaturas/inscricao-existente");
  expect(screen.queryByRole("button", { name: "Confirmar candidatura" })).not.toBeInTheDocument();
});

it("direciona o primeiro aceite para o cadastro antes de inscrever", async () => {
  jobPage("/carreiras/vagas/estagio?candidatar=1", false, false);
  expect(await screen.findByRole("link", { name: "Continuar meu cadastro" })).toHaveAttribute("href", expect.stringContaining("/candidato/perfil?next="));
  expect(screen.queryByRole("button", { name: "Confirmar candidatura" })).not.toBeInTheDocument();
});

it("bloqueia a candidatura e lista o que falta no perfil", async () => {
  jobPage("/carreiras/vagas/estagio?candidatar=1", false, true, false);
  expect(await screen.findByRole("link", { name: "Completar Meu perfil" })).toBeVisible();
  expect(screen.getByText("Telefone")).toBeVisible();
  expect(screen.queryByRole("button", { name: "Confirmar candidatura" })).not.toBeInTheDocument();
});


it("sends a connected candidate to their profile preserving the selected job", async () => {
  jobPage("/carreiras/vagas/estagio");
  fireEvent.click(await screen.findByRole("button", { name: "Candidatar-se" }));
  expect(await screen.findByTestId("destination")).toHaveTextContent("/candidato/perfil?next=" + encodeURIComponent("/carreiras/vagas/estagio?candidatar=1"));
});

it("sends a visitor to registration preserving the selected job", async () => {
  auth.loggedIn = false;
  jobPage("/carreiras/vagas/estagio");
  fireEvent.click(await screen.findByRole("button", { name: "Candidatar-se" }));
  expect(await screen.findByTestId("destination")).toHaveTextContent("/cadastro?next=" + encodeURIComponent("/carreiras/vagas/estagio?candidatar=1"));
});
