import { afterEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ReleaseAdmissionDocuments } from "./ReleaseAdmissionDocuments";

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

it("bloqueia antes da aprovação e libera os documentos do candidato correto pelo RH", async () => {
  let checklist = { eligible: false, can_approve: true, approved: false, items: [] };
  const requests: string[] = [];
  const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
    if (init?.method === "POST") {
      requests.push(url);
      checklist = { ...checklist, approved: true };
      return new Response(JSON.stringify({ approved: true }));
    }
    return new Response(JSON.stringify(checklist));
  });
  vi.stubGlobal("fetch", fetchMock);
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  client.setQueryData(["session"], { user: { kind: "INTERNAL" }, permissions: ["document.review"] });
  render(<QueryClientProvider client={client}><ReleaseAdmissionDocuments candidateId="candidate-test" /></QueryClientProvider>);
  const button = screen.getByRole("button", { name: "Liberar documentos admissionais" });
  await waitFor(() => expect(button).toBeEnabled());
  fireEvent.click(button);
  await waitFor(() => expect(requests).toEqual(["/api/v1/candidates/candidate-test/approve-document-uploads"]));
  await waitFor(() => expect(screen.queryByRole("button", { name: "Liberar documentos admissionais" })).not.toBeInTheDocument());
  client.clear();
});

it("não mostra a liberação para uma conta sem permissão", () => {
  const fetchMock = vi.fn();
  vi.stubGlobal("fetch", fetchMock);
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  client.setQueryData(["session"], { user: { kind: "INTERNAL" }, permissions: ["candidate.view"] });
  render(<QueryClientProvider client={client}><ReleaseAdmissionDocuments candidateId="candidate-test" /></QueryClientProvider>);
  expect(screen.queryByRole("button", { name: "Liberar documentos admissionais" })).not.toBeInTheDocument();
  expect(fetchMock).not.toHaveBeenCalled();
  client.clear();
});
