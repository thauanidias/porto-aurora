import { afterEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { api, post } from "../lib/api";
import { ManagerAccessPage } from "./ManagerAccess";

vi.mock("../lib/api", async original => ({ ...await original<typeof import("../lib/api")>(), api: vi.fn(), post: vi.fn() }));
afterEach(() => { cleanup(); vi.resetAllMocks(); });

it("registers a manager in its own area with a fixed manager role", async () => {
  vi.mocked(api).mockImplementation(async path => ({ items: path.startsWith("/org") ? [{ id: "sector", name: "TI", active: true }] : [], total: 0, page: 1, page_size: 25 }) as never);
  render(<QueryClientProvider client={new QueryClient()}><MemoryRouter><ManagerAccessPage /></MemoryRouter></QueryClientProvider>);
  expect(screen.getByRole("link", { name: /Solicitações de vagas/ })).toHaveAttribute("href", "/app/solicitacoes");
  fireEvent.click(screen.getByRole("button", { name: "Cadastrar gestor" }));
  fireEvent.change(screen.getByRole("textbox", { name: "Nome completo" }), { target: { value: "Gestor Teste" } });
  fireEvent.change(screen.getByRole("textbox", { name: "E-mail corporativo" }), { target: { value: "gestor@portoaurora.example" } });
  await screen.findByRole("option", { name: "TI" });
  fireEvent.change(screen.getByRole("combobox"), { target: { value: "sector" } });
  fireEvent.change(screen.getByLabelText("Senha inicial"), { target: { value: "Tg@123" } });
  fireEvent.click(screen.getByRole("dialog").querySelector('button[type="submit"]') ?? screen.getAllByRole("button", { name: "Cadastrar gestor" }).at(-1)!);
  await waitFor(() => expect(post).toHaveBeenCalledWith("/users", { name: "Gestor Teste", email: "gestor@portoaurora.example", password: "Tg@123", org_unit_id: "sector", auth_source: "LOCAL", roles: ["GESTOR"] }));
});
