import { afterEach, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { CandidateVacancies } from "./CandidateVacancies";

const session = vi.hoisted(() => ({ data: { permissions: [] as string[] }, isPending: false }));
vi.mock("../lib/session", () => ({ useSession: () => session }));
afterEach(() => { cleanup(); vi.unstubAllGlobals(); session.data.permissions = []; });
it.each([true, false])("uses the matching vacancy audience for internal=%s", async internal => {
  session.data.permissions = internal ? ["internal.view"] : [];
  const fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify({ items: [{ id: "1", title: "Analista", slug: "analista" }], total: 1 }), { status: 200 }));
  vi.stubGlobal("fetch", fetch);
  render(<QueryClientProvider client={new QueryClient()}><MemoryRouter><CandidateVacancies /></MemoryRouter></QueryClientProvider>);
  const link = await screen.findByRole("link", { name: "Ver detalhes da vaga: Analista" });
  expect(link).toHaveAttribute("href", (internal ? "/oportunidades-internas/" : "/carreiras/vagas/") + "analista");
  expect(fetch.mock.calls[0][0]).toContain(internal ? "/internal/vacancies" : "/public/vacancies");
});
