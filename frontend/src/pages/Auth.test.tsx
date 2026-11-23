import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ConfirmPage, LoginPage, RecoverPage } from "./Auth";
vi.mock("../components/TestMailbox", () => ({ TestMailbox: () => null }));

afterEach(() => { cleanup(); vi.unstubAllGlobals(); window.history.replaceState(null, "", "/"); });

it("RH enters with local email and password", async () => {
  const fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify({ message: "Usuário de rede ou senha inválidos." }), { status: 401 }));
  vi.stubGlobal("fetch", fetch);
  render(<QueryClientProvider client={new QueryClient()}><MemoryRouter><LoginPage internal /></MemoryRouter></QueryClientProvider>);
  expect(screen.getByLabelText("E-mail")).toHaveAttribute("type", "email");
  expect(screen.queryByRole("link", { name: "Esqueci minha senha" })).not.toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("E-mail"), { target: { value: "admin@example.invalid" } });
  fireEvent.change(screen.getByLabelText("Senha"), { target: { value: "local-password" } });
  fireEvent.click(screen.getByRole("button", { name: "Entrar" }));
  await waitFor(() => expect(fetch.mock.calls.some(([url]) => url === "/api/v1/auth/login")).toBe(true));
  const request = fetch.mock.calls.find(([url]) => url === "/api/v1/auth/login")!;
  expect(JSON.parse(request[1].body)).toEqual({ email: "admin@example.invalid", password: "local-password", source: "LOCAL", area: "RH" });
});

describe("Acesso temporário", () => {
  it("confirma o link sem pedir ou enviar uma nova senha", async () => {
    window.history.replaceState(null, "", "/confirmar#token=temporary-access-test-token&purpose=MAGIC");
    const fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify({
      access_token: "test-access", user: { kind: "CANDIDATO" },
    }), { status: 200 }));
    vi.stubGlobal("fetch", fetch);
    render(<QueryClientProvider client={new QueryClient()}><MemoryRouter><ConfirmPage /></MemoryRouter></QueryClientProvider>);
    expect(screen.queryByLabelText("Nova senha")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Confirmar e acessar" }));
    await waitFor(() => expect(fetch).toHaveBeenCalled());
    expect(fetch.mock.calls[0][0]).toBe("/api/v1/auth/consume-link");
    expect(JSON.parse(fetch.mock.calls[0][1].body)).toEqual({
      token: "temporary-access-test-token", password: null,
    });
    await waitFor(() => expect(window.location.hash).toBe(""));
  });
});

describe("Redefinir senha", () => {
  it("accepts six characters including letters numbers and symbols", () => {
    window.history.replaceState(null, "", "/confirmar#token=temporary-access-test-token&purpose=SETUP");
    render(<QueryClientProvider client={new QueryClient()}><MemoryRouter><ConfirmPage /></MemoryRouter></QueryClientProvider>);
    const password = screen.getByLabelText("Crie sua senha");
    expect(password).toHaveAttribute("minlength", "6");
    expect(password).toHaveAttribute("maxlength", "6");
    fireEvent.change(password, { target: { value: "012345" } });
    expect(password).toBeValid();
    fireEvent.change(password, { target: { value: "Ab1!x?" } });
    expect(password).toBeValid();
  });
  it("solicita o link de redefinição para o e-mail informado", async () => {
    const fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify({
      message: "Se houver cadastro, você receberá as instruções de acesso.",
    }), { status: 200 }));
    vi.stubGlobal("fetch", fetch);
    render(<MemoryRouter><RecoverPage /></MemoryRouter>);
    fireEvent.change(screen.getByLabelText("E-mail"), { target: { value: "candidato@example.com" } });
    fireEvent.click(screen.getByRole("button", { name: "Enviar link para redefinir senha" }));
    expect(screen.getByRole("button", { name: "Enviando…" })).toBeDisabled();
    expect(await screen.findByRole("status")).toHaveTextContent("Se houver cadastro");
    expect(fetch.mock.calls[0][0]).toBe("/api/v1/auth/request-link");
    expect(JSON.parse(fetch.mock.calls[0][1].body)).toEqual({
      email: "candidato@example.com", purpose: "RESET",
    });
  });

  it("informa a indisponibilidade de e-mail sem anunciar sucesso", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({
      message: "O acesso por e-mail não está disponível. Contate o RH.",
      code: "EMAIL_DISABLED",
    }), { status: 503 })));
    render(<MemoryRouter><RecoverPage /></MemoryRouter>);
    fireEvent.change(screen.getByLabelText("E-mail"), { target: { value: "candidato@example.com" } });
    fireEvent.click(screen.getByRole("button", { name: "Enviar link para redefinir senha" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Contate o RH");
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Enviar link para redefinir senha" })).toBeEnabled();
  });
});
