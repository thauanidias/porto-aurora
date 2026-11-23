import { afterEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { RejectionEmail } from "./RejectionEmail";

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
it("permite revisar o retorno e bloqueia novo envio após entrar na fila", async () => {
  let sent = false;
  const fetch = vi.fn(async (_url: string, init?: RequestInit) => {
    if (init?.method === "POST") sent = true;
    return new Response(JSON.stringify({ subject: "Retorno da seleção", body: "Agradecemos sua participação no processo.", status: sent ? "PENDING" : "NOT_REQUESTED", delivery_enabled: true }), { status: 200 });
  });
  vi.stubGlobal("fetch", fetch);
  render(<QueryClientProvider client={new QueryClient()}><RejectionEmail applicationId="app-1" /></QueryClientProvider>);
  const input = await screen.findByLabelText("Mensagem ao candidato");
  fireEvent.change(input, { target: { value: "Mensagem revisada pelo RH para o candidato." } });
  fireEvent.click(screen.getByRole("button", { name: "Enviar retorno por e-mail" }));
  expect(await screen.findByText("E-mail na fila de envio")).toBeVisible();
  expect(screen.queryByRole("button", { name: "Enviar retorno por e-mail" })).not.toBeInTheDocument();
  await waitFor(() => expect(fetch.mock.calls.some(([, init]) => init?.method === "POST" && String(init.body).includes("Mensagem revisada pelo RH"))).toBe(true));
});
