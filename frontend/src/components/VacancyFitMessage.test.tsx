import { afterEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { VacancyFitMessage } from "./VacancyFitMessage";

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
function setup(compatibility: Record<string, unknown>, permissions: string[] = []) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  client.setQueryData(["session"], { user: { kind: "INTERNAL" }, permissions });
  render(<QueryClientProvider client={client}><MemoryRouter><VacancyFitMessage application={{ id: "application-1", version: 1, vacancy_id: "vacancy-1", vacancy_title: "Assistente de Logística", compatibility }} /></MemoryRouter></QueryClientProvider>);
  return client;
}
it.each([85, 0])("mostra o percentual real de %s sem confundir com decisão do RH", value => {
  const client = setup({ status: "CALCULATED", percentage: value });
  expect(screen.getByText(`${value}% de compatibilidade`)).toBeVisible();
  expect(screen.getByRole("progressbar")).toHaveAttribute("value", String(value));
  expect(screen.getByText(/A decisão de apto ou não apto continua com o RH/)).toBeVisible();
  client.clear();
});
it("não inventa um percentual quando faltam critérios", () => {
  const client = setup({ status: "NOT_CONFIGURED", percentage: null }, ["score.manage"]);
  expect(screen.getAllByText("Sem nota disponível")[0]).toBeVisible();
  expect(screen.queryByRole("progressbar")).not.toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Configurar critérios da vaga" })).toHaveAttribute("href", "/app/vagas/vacancy-1?tab=scoring");
  expect(screen.queryByRole("button", { name: "Atualizar compatibilidade" })).not.toBeInTheDocument();
  client.clear();
});
it("atualiza a análise somente quando o RH solicita", async () => {
  const fetchMock = vi.fn().mockResolvedValue(new Response("{}"));
  vi.stubGlobal("fetch", fetchMock);
  const client = setup({ status: "OUTDATED", percentage: null }, ["score.manage"]);
  expect(fetchMock).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole("button", { name: "Atualizar compatibilidade" }));
  await waitFor(() => expect(fetchMock).toHaveBeenCalledWith("/api/v1/applications/application-1/curriculum-analysis", expect.objectContaining({ method: "POST" })));
  client.clear();
});
