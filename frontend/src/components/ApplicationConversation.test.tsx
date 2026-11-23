import { afterEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ApplicationConversation } from "./ApplicationConversation";

vi.mock("../lib/session", () => ({ useSession: () => ({ data: { user: { id: "owner", kind: "CANDIDATO" }, permissions: [] } }) }));
afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks(); });

it("envia resposta vinculada à candidatura e preserva o texto quando o envio falha", async () => {
  vi.spyOn(document, "visibilityState", "get").mockReturnValue("visible");
  let failed = true;
  const fetch = vi.fn(async (_url: string, init?: RequestInit) => new Response(JSON.stringify(_url.endsWith("/read") ? { read: true } : init?.method === "POST"
    ? failed ? { message: "Envio indisponível" } : { id: "message" }
    : { items: [{ id: "rh", sender_id: "recruiter", sender_name: "Equipe RH", body: "Olá, candidato", created_at: "2026-10-01T10:00:00Z" }], total: 1 }), { status: init?.method === "POST" && failed && !_url.endsWith("/read") ? 503 : 200 }));
  vi.stubGlobal("fetch", fetch);
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><ApplicationConversation applicationId="application" /></QueryClientProvider>);
  expect(await screen.findByText("Olá, candidato")).toBeVisible();
  await waitFor(() => expect(fetch.mock.calls.some(([url]) => url.endsWith("/messages/read"))).toBe(true));
  const input = screen.getByLabelText("Mensagem para o RH");
  fireEvent.change(input, { target: { value: "Minha dúvida" } });
  fireEvent.click(screen.getByRole("button", { name: "Enviar mensagem" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Envio indisponível");
  expect(input).toHaveValue("Minha dúvida");
  failed = false;
  fireEvent.click(screen.getByRole("button", { name: "Enviar mensagem" }));
  await waitFor(() => expect(input).toHaveValue(""));
  const sent = fetch.mock.calls.filter(([url, init]) => init?.method === "POST" && !url.endsWith("/read"));
  expect(sent[1][0]).toBe("/api/v1/applications/application/messages");
  expect(JSON.parse(sent[1][1]!.body as string)).toEqual({ subject: "Conversa com o RH", body: "Minha dúvida", visibility: "CANDIDATE" });
});

it("recebe novas mensagens automaticamente sem perder o rascunho", async () => {
  let received = false;
  const fetch = vi.fn(async () => new Response(JSON.stringify({ items: received ? [{ id: "new", sender_id: "recruiter", sender_name: "RH", body: "Nova orientação do RH", created_at: "2026-11-06T13:00:00Z" }] : [], total: received ? 1 : 0 })));
  vi.stubGlobal("fetch", fetch);
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const view = render(<QueryClientProvider client={client}><ApplicationConversation applicationId="application" /></QueryClientProvider>);
  expect(await screen.findByText("Vamos iniciar a conversa?")).toBeVisible();
  fireEvent.change(screen.getByLabelText("Mensagem para o RH"), { target: { value: "Rascunho ainda não enviado" } });
  received = true;
  expect(await screen.findByText("Nova orientação do RH", {}, { timeout: 4000 })).toBeVisible();
  expect(screen.getByLabelText("Mensagem para o RH")).toHaveValue("Rascunho ainda não enviado");
  view.unmount(); client.clear();
});
