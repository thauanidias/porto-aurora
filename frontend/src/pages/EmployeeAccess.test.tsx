import { afterEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { LoginPage } from "./Auth";
import { ManagerRegisterPage } from "./ManagerAccess";

vi.mock("../components/Brand", () => ({ Brand: () => <span>Porto Aurora</span> }));
vi.mock("../components/TestMailbox", () => ({ TestMailbox: () => null }));
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

it("registers with name email password and verification code only", async () => {
  const fetch = vi.fn().mockImplementation(async (url: string) => new Response(JSON.stringify(url.endsWith("/register-employee") ? { registration_id: "registration-test", resend_after: 60 } : { completion_token: "verified-proof" }), { status: 200 }));
  vi.stubGlobal("fetch", fetch);
  render(<MemoryRouter><ManagerRegisterPage employee /></MemoryRouter>);
  fireEvent.change(screen.getByLabelText("Nome completo"), { target: { value: "Colaborador Teste" } });
  fireEvent.change(screen.getByLabelText("E-mail pessoal ou corporativo"), { target: { value: "colaborador@portoaurora.example" } });
  fireEvent.change(screen.getByLabelText("Senha"), { target: { value: "Ep42!?" } });
  expect(screen.queryByLabelText("Setor ou departamento")).not.toBeInTheDocument();
  expect(screen.queryByLabelText(/Usuário de rede/)).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Enviar código de verificação" }));
  expect(await screen.findByRole("heading", { name: "Confirme seu e-mail pessoal ou corporativo" })).toBeInTheDocument();
  expect(screen.queryByRole("link", { name: "Entrar com usuário de rede" })).not.toBeInTheDocument();
  expect(fetch.mock.calls[0][0]).toBe("/api/v1/auth/register-employee");
  expect(JSON.parse(fetch.mock.calls[0][1].body)).toEqual({ name: "Colaborador Teste", email: "colaborador@portoaurora.example" });
  expect(screen.getByRole("button", { name: /Reenviar código em/ })).toBeDisabled();
  fireEvent.change(screen.getByLabelText(/Código de verificação/), { target: { value: "123456" } });
  fireEvent.click(screen.getByRole("button", { name: "Confirmar código e concluir cadastro" }));
  expect(await screen.findByRole("heading", { name: "Cadastro concluído" })).toBeInTheDocument();
  expect(fetch.mock.calls[1][0]).toBe("/api/v1/auth/employee-email-code/confirm");
  expect(JSON.parse(fetch.mock.calls[1][1].body)).toEqual({ registration_id: "registration-test", code: "123456" });
  expect(JSON.parse(fetch.mock.calls[2][1].body)).toEqual({ password: "Ep42!?", completion_token: "verified-proof" });
  expect(screen.getByRole("link", { name: "Entrar como colaborador" })).toHaveAttribute("href", "/entrar-colaborador");
});

it("logs employees in with corporate email and their portal password", async () => {
  const fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify({ access_token: "test" }), { status: 200 }));
  vi.stubGlobal("fetch", fetch);
  render(<QueryClientProvider client={new QueryClient()}><MemoryRouter initialEntries={["/entrar-colaborador"]}><Routes><Route path="/entrar-colaborador" element={<LoginPage employee />} /><Route path="/oportunidades-internas" element={<p>Portal interno</p>} /></Routes></MemoryRouter></QueryClientProvider>);
  fireEvent.change(screen.getByLabelText("E-mail pessoal ou corporativo"), { target: { value: "colaborador@portoaurora.example" } });
  fireEvent.change(screen.getByLabelText("Senha"), { target: { value: "Ep42!?" } });
  fireEvent.click(screen.getByRole("button", { name: "Entrar" }));
  await waitFor(() => expect(fetch).toHaveBeenCalled());
  expect(JSON.parse(fetch.mock.calls[0][1].body)).toEqual({ email: "colaborador@portoaurora.example", password: "Ep42!?", source: "LOCAL", area: "CANDIDATO" });
  expect(await screen.findByText("Portal interno")).toBeInTheDocument();
});
