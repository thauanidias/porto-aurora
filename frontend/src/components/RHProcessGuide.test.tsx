import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Layout } from "./Layout";
import { canUseRHGuide, rhGuideContext } from "../lib/rhProcessGuide";
import { type Session } from "../lib/api";

const state = vi.hoisted(() => ({ session: undefined as Session | undefined }));
vi.mock("../lib/session", async importOriginal => ({ ...await importOriginal<typeof import("../lib/session")>(), useSession: () => ({ data: state.session, isPending: false }) }));
vi.mock("./Brand", () => ({ Brand: () => <span>Porto Aurora Talentos</span> }));
vi.mock("../lib/candidateActions", () => ({ useCandidateActions: () => ({ data: [] }) }));
vi.mock("../lib/candidateJourney", () => ({ useCandidateJourney: () => ({ data: undefined }) }));

function session(permissions: string[], kind = "INTERNAL"): Session {
  return { user: { id: "rh-user-1", name: "Equipe RH", email: "rh@example.com", kind }, permissions };
}
function mount(candidate = false) {
  return render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><MemoryRouter initialEntries={["/app/candidaturas"]}><Layout candidate={candidate} /></MemoryRouter></QueryClientProvider>);
}
beforeEach(() => {
  localStorage.clear();
  vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({ items: [], unread: 0 }), { status: 200 })));
});
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

it("direciona a ajuda para a etapa atual da candidatura", () => {
  expect(rhGuideContext("/app/candidaturas/processo-1", "FORM")?.step).toBe(3);
  expect(rhGuideContext("/app/candidaturas/processo-1", "INTERVIEW")?.step).toBe(4);
  expect(rhGuideContext("/app/candidaturas/processo-1", "TEST")?.step).toBe(5);
});

it("mostra zero mensagens não lidas no menu do RH", async () => {
  state.session = session(["candidate.view", "message.send"]);
  mount();
  expect(await screen.findByLabelText("0 mensagens não lidas")).toHaveTextContent("0");
});

it("apresenta o guia na primeira visita do RH, permite reabrir e guarda o fechamento por usuário", async () => {
  state.session = session(["candidate.move", "candidate.view", "vacancy.view"]);
  const first = mount();
  expect(first.container.querySelector(".rh-workspace")).toBeInTheDocument();
  expect(document.body).toHaveClass("rh-workspace-document");
  expect(await screen.findByRole("dialog", { name: "Como funciona o sistema" })).toBeVisible();
  expect(screen.getByRole("heading", { name: "Explore o sistema na prática" })).toBeVisible();
  fireEvent.click(screen.getByRole("button", { name: /03.*Decida a triagem/ }));
  expect(screen.getByRole("heading", { name: "Escolha quem continua" })).toBeVisible();
  expect(screen.getByRole("progressbar")).toHaveAttribute("aria-valuenow", "3");
  fireEvent.click(screen.getByRole("button", { name: "Próximo passo" }));
  expect(screen.getByRole("heading", { name: "O RH conduz; a pessoa responde" })).toBeVisible();
  fireEvent.click(screen.getByRole("button", { name: "Fluxo seletivo" }));
  expect(screen.getByRole("heading", { name: "Cadastro" })).toBeVisible();
  fireEvent.click(screen.getByRole("button", { name: "Fechar guia" }));
  expect(localStorage.getItem("rh-process-guide-v1:rh-user-1")).toBe("seen");
  fireEvent.click(screen.getByRole("button", { name: "Como funciona o sistema" }));
  fireEvent.click(screen.getByRole("button", { name: "Fluxo seletivo" }));
  fireEvent.click(screen.getByRole("button", { name: /5.*Entrevista/ }));
  expect(screen.getByRole("heading", { name: "Entrevista" })).toBeVisible();
  fireEvent.click(screen.getByRole("button", { name: "Fechar guia" }));
  first.unmount();
  expect(document.body).not.toHaveClass("rh-workspace-document");
  mount();
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Como usar esta etapa" }));
  expect(await screen.findByRole("heading", { name: "Seleção de currículo" })).toBeVisible();
});

it("permite buscar áreas e salva a conferência pessoal sem alterar configurações", async () => {
  state.session = session(["candidate.move", "candidate.view", "vacancy.view"]);
  mount();
  await screen.findByRole("dialog", { name: "Como funciona o sistema" });
  fireEvent.click(screen.getByRole("button", { name: "Áreas do sistema" }));
  fireEvent.change(screen.getByLabelText("Buscar área do sistema"), { target: { value: "administracao" } });
  expect(screen.getByText("Administração e acessos")).toBeInTheDocument();
  expect(screen.queryByRole("link", { name: "Acessar Administração e acessos" })).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Antes de começar" }));
  fireEvent.click(screen.getAllByRole("checkbox")[0]);
  expect(screen.getByText("1 de 7 itens conferidos")).toBeVisible();
  fireEvent.click(screen.getByRole("button", { name: "Fechar guia" }));
  fireEvent.click(screen.getByRole("button", { name: "Como funciona o sistema" }));
  fireEvent.click(screen.getByRole("button", { name: "Antes de começar" }));
  expect(screen.getByText("1 de 7 itens conferidos")).toBeVisible();
});

it.each([
  { name: "gestor", permissions: ["request.create", "candidate.view", "interview.manage"], kind: "INTERNAL", candidate: false },
  { name: "candidato", permissions: [], kind: "CANDIDATO", candidate: true },
  { name: "auditor", permissions: ["candidate.view", "audit.view"], kind: "INTERNAL", candidate: false },
  { name: "entrevistador", permissions: ["candidate.view", "candidate.evaluate"], kind: "INTERNAL", candidate: false },
])("oculta botão, guia inicial e ajuda contextual para $name", ({ permissions, kind, candidate }) => {
  state.session = session(permissions, kind);
  mount(candidate);
  if (candidate || permissions.includes("request.create")) expect(document.body).not.toHaveClass("rh-workspace-document");
  expect(canUseRHGuide(state.session)).toBe(false);
  expect(screen.queryByRole("button", { name: "Como funciona o sistema" })).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Como usar esta etapa" })).not.toBeInTheDocument();
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
});
