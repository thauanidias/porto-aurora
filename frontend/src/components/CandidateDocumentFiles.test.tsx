import { afterEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { download } from "../lib/api";
import { CandidateDocumentFiles } from "./CandidateDocumentFiles";

vi.mock("../lib/api", async original => ({ ...await original<typeof import("../lib/api")>(), download: vi.fn().mockResolvedValue(undefined) }));
afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.clearAllMocks(); });
it("lists all uploaded document types and downloads the selected file", async () => {
  const fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify({ items: [
    { id: "resume", filename: "curriculo.pdf", type_name: "CURRICULO", mime: "application/pdf", scan_status: "CLEAN", size: 1024, revision: 1 },
    { id: "identity", filename: "rg.pdf", type_name: "ADM_RG", mime: "application/pdf", scan_status: "PENDING", size: 1024, revision: 1 },
  ], total: 2 }), { status: 200 }));
  vi.stubGlobal("fetch", fetch);
  render(<QueryClientProvider client={new QueryClient()}><CandidateDocumentFiles candidateId="candidate-1" /></QueryClientProvider>);
  fireEvent.click(await screen.findByRole("button", { name: "Baixar curriculo.pdf" }));
  expect(download).toHaveBeenCalledWith("/documents/resume/download", "curriculo.pdf");
  expect(screen.getByRole("button", { name: "Baixar rg.pdf" })).toBeDisabled();
  expect(fetch.mock.calls[0][0]).toContain("candidate_id=candidate-1&include_photo=true");
});
