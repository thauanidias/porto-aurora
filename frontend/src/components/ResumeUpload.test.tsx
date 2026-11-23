import { afterEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ResumeUpload } from "./ResumeUpload";

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

function show(onSuggestions = vi.fn()) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><ResumeUpload onSuggestions={onSuggestions} onBusyChange={vi.fn()} /></QueryClientProvider>);
  return onSuggestions;
}

it("reads an attached resume without another upload or saving the profile", async () => {
  const fetcher = vi.fn(async (input: RequestInfo | URL) => new Response(JSON.stringify(String(input).endsWith("profile-import") ? {status: "COMPLETED", result: {
    suggestions: { profile: { skills: ["Excel"] } }, engine: "local-ai", text: "Excel", missing: ["Formação"], uncertain: ["2020 - 2022"], message: "Revise",
  }} : { items: [{ id: "cv-1", filename: "curriculo.pdf", scan_status: "CLEAN", size: 1000 }], total: 1 })));
  vi.stubGlobal("fetch", fetcher);
  const suggested = show();
  fireEvent.click(await screen.findByRole("button", { name: "Preencher perfil com este currículo" }));
  await waitFor(() => expect(suggested).toHaveBeenCalledWith({ profile: { skills: ["Excel"] } }));
  expect(screen.getByText(/Informações não localizadas: Formação/)).toBeVisible();
  expect(screen.getByText(/Leitura concluída/)).toBeVisible();
  expect(screen.getByText("2020 - 2022")).toBeInTheDocument();
  expect(fetcher.mock.calls.every(([url]) => !String(url).includes("/candidates/me"))).toBe(true);
  expect(fetcher.mock.calls.filter(([url]) => String(url).endsWith("/documents"))).toHaveLength(0);
});

it("shows a retryable local service failure without applying data", async () => {
  vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => String(input).endsWith("profile-import")
    ? new Response(JSON.stringify({ message: "A IA local está indisponível. Preencha manualmente." }), { status: 503 })
    : new Response(JSON.stringify({ items: [{ id: "cv-1", filename: "curriculo.pdf", scan_status: "CLEAN" }] }))));
  const suggested = show();
  const button = await screen.findByRole("button", { name: "Preencher perfil com este currículo" });
  fireEvent.click(button);
  expect(await screen.findByText("A IA local está indisponível. Preencha manualmente.")).toBeVisible();
  expect(button).toBeEnabled();
  expect(suggested).not.toHaveBeenCalled();
});
