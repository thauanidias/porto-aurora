import { afterEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { PublicProcessForm } from "./PublicProcessForm";

vi.mock("./Careers", () => ({ PublicHeader: () => <header>Porto Aurora</header> }));
afterEach(() => { cleanup(); vi.unstubAllGlobals(); window.history.replaceState(null, "", "/"); });
it("envia a ficha e as respostas pelo token exclusivo sem acesso ao painel administrativo", async () => {
  const token = "a".repeat(64);
  window.history.replaceState(null, "", "/ficha-selecao#token=" + token);
  const fetch = vi.fn(async (url: string) => new Response(JSON.stringify(url.endsWith("/lookup") ? {
    vacancy_title: "Operador", notice: "Aviso desta oportunidade", status: "SENT", questions: [{ key: "motivation", label: "Por que deseja participar?", kind: "TEXT", required: true }, { key: "travel", label: "Tem disponibilidade para viajar?", kind: "BOOLEAN", required: true }],
    schema: { type: "object", properties: { name: { type: "string", title: "Nome completo" }, email: { type: "string", title: "E-mail" } }, required: ["name", "email"] },
  } : { status: "COMPLETED", registration_released: true }), { status: 200 }));
  vi.stubGlobal("fetch", fetch);
  render(<QueryClientProvider client={new QueryClient()}><PublicProcessForm /></QueryClientProvider>);
  fireEvent.change(await screen.findByLabelText("Por que deseja participar?"), { target: { value: "Tenho experiência na função." } });
  expect(screen.queryByLabelText("Nome completo")).not.toBeInTheDocument();
  expect(screen.queryByLabelText("E-mail")).not.toBeInTheDocument();
  expect(screen.getByLabelText("Tem disponibilidade para viajar?")).toHaveValue("");
  fireEvent.click(screen.getByRole("checkbox", { name: /Li o aviso de privacidade/ }));
  fireEvent.click(screen.getByRole("button", { name: "Enviar respostas ao RH" }));
  expect(await screen.findByText("Responda: Tem disponibilidade para viajar?")).toBeVisible();
  expect(fetch.mock.calls.some(([url]) => url.endsWith("/submit"))).toBe(false);
  fireEvent.change(screen.getByLabelText("Tem disponibilidade para viajar?"), { target: { value: "false" } });
  fireEvent.click(screen.getByRole("button", { name: "Enviar respostas ao RH" }));
  expect(await screen.findByText("Respostas recebidas!")).toBeVisible();
  expect(screen.getByRole("link", { name: "Preencher ficha externa" })).toHaveAttribute("href", "/candidato/perfil#ficha-externa");
  await waitFor(() => expect(fetch.mock.calls.some(([url]) => url.endsWith("/submit"))).toBe(true));
});
