import { afterEach, expect, it, vi } from "vitest";
import { cleanup, render, screen, within, waitFor } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { MemoryRouter } from "react-router-dom";
import { CandidateCompatibility, CompatibilityRanking } from "./CandidateCompatibility";
import type { Row } from "../lib/api";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent } from "@testing-library/react";

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
function candidate(id: string, percentage: number | null, status = "ACTIVE"): Row {
  return { id, version: 1, status, candidate: { name: id }, stage_name: "Seleção",
    compatibility: { percentage, status: percentage === null ? "NOT_CONFIGURED" : "CALCULATED" } };
}

it("ordena candidatos ativos por compatibilidade, preservando zero e pendências", () => {
  const client = new QueryClient({ defaultOptions: { queries: { enabled: false, retry: false } } });
  render(<QueryClientProvider client={client}><MemoryRouter><CompatibilityRanking total={5} applications={[
    candidate("Zero", 0), candidate("Pendente", null), candidate("Mais compatível", 90),
    candidate("Intermediário", 50), candidate("Encerrado", 100, "REJECTED"),
  ]} /></MemoryRouter></QueryClientProvider>);
  const rows = screen.getAllByRole("row").slice(1);
  expect(rows.map(row => within(row).getByRole("link", { name: /Mais compatível|Intermediário|Zero|Pendente/ }).textContent)).toEqual([
    "Mais compatível", "Intermediário", "Zero", "Pendente",
  ]);
  expect(screen.getByText("0% de compatibilidade")).toBeVisible();
  expect(screen.queryByText("Encerrado")).not.toBeInTheDocument();
});

it("explica porcentagem provisória e critérios sem dados", () => {
  const row = candidate("Exemplo", 50);
  row.compatibility = { percentage: 50, status: "PENDING", model_version: 2, pending_components: ["RH"],
    items: [{ key: "experience", name: "Experiência", weight: 100, value: null }], knockout: true };
  render(<CandidateCompatibility row={row} details />);
  expect(screen.getByText("Resultado provisório · faltam informações")).toBeVisible();
  expect(screen.getByText("Requisito obrigatório precisa de revisão pelo RH.")).toBeVisible();
  expect(screen.getByText("Não informado — verificar com o candidato")).toBeInTheDocument();
});

it("não classifica ausência de evidência como baixa compatibilidade e filtra resultados", () => {
  const client = new QueryClient({ defaultOptions: { queries: { enabled: false, retry: false } } });
  const unknown = candidate("Sem evidência", null);
  unknown.compatibility = { curriculum: { percentage: null, status: "PENDING", items: [] } };
  render(<QueryClientProvider client={client}><MemoryRouter><CompatibilityRanking total={3} applications={[
    candidate("Baixa aderência", 30), candidate("Alta aderência", 85), unknown,
  ]} /></MemoryRouter></QueryClientProvider>);
  fireEvent.change(screen.getByLabelText("Resultado"), { target: { value: "review" } });
  expect(screen.getByRole("link", { name: "Baixa aderência" })).toBeVisible();
  expect(screen.queryByRole("link", { name: "Sem evidência" })).not.toBeInTheDocument();
  expect(screen.queryByRole("link", { name: "Alta aderência" })).not.toBeInTheDocument();
});

it("mostra o perfil e exige confirmação para aprovar apenas a etapa", async () => {
  const client = new QueryClient({ defaultOptions: { queries: { enabled: false, retry: false } } });
  client.setQueryData(["session"], { user: { id: "rh", name: "RH" }, permissions: ["candidate.move", "candidate.select"] });
  const request = vi.fn(async () => new Response(JSON.stringify({ id: "review", status: "APPROVED" }), { status: 201 }));
  vi.stubGlobal("fetch", request);
  const row = candidate("Pessoa Exemplo", 85);
  row.candidate = { name: "Pessoa Exemplo", profile: { skills: ["Python"], education: [{ course: "Sistemas de Informação", institution: "Instituição Exemplo" }], experiences: [{ company: "Empresa Exemplo", position: "Desenvolvimento" }] } };
  render(<QueryClientProvider client={client}><MemoryRouter><CompatibilityRanking applications={[row]} total={1} /></MemoryRouter></QueryClientProvider>);
  expect(screen.getByText("Python")).toBeVisible();
  expect(screen.getByText("Desenvolvimento")).toBeVisible();
  fireEvent.click(screen.getByRole("button", { name: "Aprovar etapa" }));
  expect(request).not.toHaveBeenCalled();
  fireEvent.change(screen.getByLabelText("Justificativa da aprovação"), { target: { value: "Perfil atende aos requisitos da etapa." } });
  fireEvent.click(screen.getByRole("button", { name: "Confirmar aprovação da etapa" }));
  await waitFor(() => expect(request).toHaveBeenCalled());
  const [url, options] = request.mock.calls[0] as unknown as [string, RequestInit];
  expect(url).toContain("/stage-reviews");
  expect(JSON.parse(String(options.body))).toMatchObject({ status: "APPROVED", version: 1 });
  expect(url).not.toContain("/decision");
});
