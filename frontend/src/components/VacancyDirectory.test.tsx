import { afterEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { api, post } from "../lib/api";
import { VacancyDirectory } from "./VacancyDirectory";

vi.mock("../lib/api", async importOriginal => ({ ...await importOriginal<typeof import("../lib/api")>(), api: vi.fn(), post: vi.fn() }));
afterEach(() => { cleanup(); vi.resetAllMocks(); });

function setup(manager = false, permissions = ["vacancy.edit"]) {
  vi.mocked(api).mockImplementation(async path => (path === "/auth/me" ? { permissions } : { items: [
    { id: "open", title: "Analista", code: "Porto Aurora-1", version: 3, status: "PUBLISHED" },
    { id: "closed", title: "Outra", code: "Porto Aurora-2", version: 2, status: "CLOSED" },
  ], total: 2 }) as never);
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><MemoryRouter><VacancyDirectory manager={manager} /></MemoryRouter></QueryClientProvider>);
}

it("requires confirmation and a reason before closing the chosen vacancy", async () => {
  setup();
  fireEvent.click(await screen.findByRole("button", { name: "Encerrar vaga Analista" }));
  expect(post).not.toHaveBeenCalled();
  expect(screen.queryByRole("button", { name: "Encerrar vaga Outra" })).not.toBeInTheDocument();
  fireEvent.change(screen.getByRole("textbox", { name: /Motivo do encerramento/ }), { target: { value: "Processo concluido" } });
  fireEvent.click(screen.getByRole("button", { name: "Confirmar encerramento" }));
  await waitFor(() => expect(post).toHaveBeenCalledWith("/vacancies/open/status", { status: "CLOSED", reason: "Processo concluido", version: 3 }));
  await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
});

it.each([[true, ["vacancy.edit"]], [false, []]] as const)("hides closing from managers and users without permission", async (manager, permissions) => {
  setup(manager, [...permissions]);
  await screen.findByText("Porto Aurora-1", { exact: false });
  expect(screen.queryByRole("button", { name: "Encerrar vaga Analista" })).not.toBeInTheDocument();
});
