import { afterEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { download } from "../lib/api";
import { RHConsentDownload } from "./RHConsentDownload";

vi.mock("../lib/session", () => ({ useSession: () => ({ data: { user: { kind: "INTERNAL" }, permissions: ["candidate.view"] } }) }));
vi.mock("../lib/api", async original => ({ ...await original<typeof import("../lib/api")>(), download: vi.fn().mockResolvedValue(undefined) }));
afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.clearAllMocks(); });

function show(result: object) {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify(result))));
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><RHConsentDownload candidateId="person-1" /></QueryClientProvider>);
}

it("downloads the consent document independently of the external form", async () => {
  show({ available: true, receipt_id: "receipt-1", protocol: "ACEITE-1" });
  const button = await screen.findByRole("button", { name: "Baixar termo de consentimento" });
  await screen.findByTitle("Termo original em Word com assinatura e comprovante");
  expect(button).toBeEnabled();
  fireEvent.click(button);
  expect(download).toHaveBeenCalledWith("/privacy/consent-receipts/receipt-1/document", "termo-consentimento-ACEITE-1.docx");
});

it("keeps the button unavailable before consent is accepted", async () => {
  show({ available: false, receipt_id: null, protocol: null });
  expect(await screen.findByRole("button", { name: "Baixar termo de consentimento" })).toBeDisabled();
  expect(download).not.toHaveBeenCalled();
});
