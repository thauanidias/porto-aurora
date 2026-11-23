import { afterEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { SelectionRegistration } from "./SelectionRegistration";

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

it("preserva o preenchimento ao recolher e salva novamente com a versão atual", async () => {
  let version = 0;
  const submissions: Record<string, unknown>[] = [];
  const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
    if (url.endsWith("/schema")) return new Response(JSON.stringify({
      type: "object", properties: {
        desired_position: { type: "string", title: "Cargo pretendido", default: "" },
        personal: { type: "object", properties: {
          name: { type: "string", title: "Nome completo", default: "" },
          email: { type: "string", title: "E-mail", default: "" },
        } },
      },
    }));
    if (init?.method === "PUT") {
      const body = JSON.parse(String(init.body));
      submissions.push(body);
      expect(body.version).toBe(version);
      return new Response(JSON.stringify({ data: body.data, version: ++version, saved_at: "2026-10-09", confirmed_at: null }));
    }
    return new Response(JSON.stringify({ data: null, version: 0, saved_at: null, confirmed_at: null }));
  });
  vi.stubGlobal("fetch", fetchMock);
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><SelectionRegistration identity={{ name: "Pessoa de Teste", email: "pessoa@example.com" }} /></QueryClientProvider>);
  await screen.findByRole("combobox", { name: "Cargo pretendido" });
  expect(screen.getByLabelText("Nome completo")).toHaveValue("Pessoa de Teste");
  fireEvent.change(screen.getByRole("combobox", { name: "Cargo pretendido" }), { target: { value: "Operador" } });
  fireEvent.click(screen.getByRole("button", { name: "Recolher ficha" }));
  fireEvent.click(screen.getByRole("button", { name: "Abrir ficha de inscrição" }));
  expect(screen.getByRole("combobox", { name: "Cargo pretendido" })).toHaveValue("Operador");
  fireEvent.click(screen.getByRole("button", { name: "Salvar ficha e assinatura" }));
  await waitFor(() => expect(submissions).toHaveLength(1));
  await screen.findByRole("status");
  fireEvent.change(screen.getByRole("combobox", { name: "Cargo pretendido" }), { target: { value: "Analista" } });
  fireEvent.click(screen.getByRole("button", { name: "Salvar ficha e assinatura" }));
  await waitFor(() => expect(submissions).toHaveLength(2));
  expect(submissions[1]).toMatchObject({ version: 1, data: { desired_position: "Analista" } });
  client.clear();
});
