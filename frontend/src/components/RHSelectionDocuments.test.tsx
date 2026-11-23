import { afterEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { download } from "../lib/api";
import { RHSelectionDocuments } from "./RHSelectionDocuments";

vi.mock("../lib/api", async original => ({ ...await original<typeof import("../lib/api")>(), download: vi.fn().mockResolvedValue(undefined) }));
afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.clearAllMocks(); });
function show(receipts: unknown[]) {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ receipts, registration: { data: { name: "Ficha não deve aparecer" } } }), { status: 200 })));
  render(<QueryClientProvider client={new QueryClient()}><RHSelectionDocuments candidate={{ id: "person-1", version: 1 }} /></QueryClientProvider>);
}
it("shows the registration area and downloads the accepted receipt", async () => {
  show([{ id: "receipt-1", document_code: "FORM-PPO-RH-002.09", protocol: "PROTO-1", created_at: "2026-10-15T12:00:00Z" }]);
  fireEvent.click(await screen.findByRole("button", { name: "Baixar termo de consentimento" }));
  expect(download).toHaveBeenCalledWith("/privacy/consent-receipts/receipt-1/document", "termo-PROTO-1.docx");
  expect(screen.getByRole("heading", { name: "Ficha de inscrição para seleção externa" })).toBeVisible();
  expect(screen.queryByText("Ficha não deve aparecer")).not.toBeInTheDocument();
});
it("keeps download unavailable until the candidate accepts the term", async () => {
  show([]);
  expect(await screen.findByRole("button", { name: "Baixar termo de consentimento" })).toBeDisabled();
  expect(download).not.toHaveBeenCalled();
});

it("separates the external form from the consent screen", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ receipts: [], registration: { data: null } }))));
  render(<QueryClientProvider client={new QueryClient()}><RHSelectionDocuments candidate={{ id: "person-1", version: 1 }} view="registration" /></QueryClientProvider>);
  expect(await screen.findByRole("heading", { name: "Ficha de inscrição para seleção externa" })).toBeVisible();
  expect(screen.queryByRole("heading", { name: "Termo de consentimento de dados" })).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Baixar termo de consentimento" })).not.toBeInTheDocument();
});

it("shows the complete form and enables the original signed workbook", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ receipts: [], registration: {
    data: { personal: { name: "Pessoa de Teste" }, declaration: { signature_image: "data:image/png;base64,AAA=" } },
    confirmed_at: "2026-10-28T18:00:00Z", signature_record: { protocol: "TESTE-ASSINATURA" },
  }, schema: { type: "object", properties: { personal: { type: "object", title: "Dados pessoais", properties: { name: { type: "string", title: "Nome completo" } } }, declaration: { type: "object", title: "Assinatura", properties: { signature_image: { type: "string", format: "signature", title: "Assinatura eletrônica" } } } } } }))));
  render(<QueryClientProvider client={new QueryClient()}><RHSelectionDocuments candidate={{ id: "person-1", version: 1 }} /></QueryClientProvider>);
  expect(await screen.findByText("Pessoa de Teste")).toBeVisible();
  expect(screen.getByRole("img", { name: "Assinatura eletrônica do candidato" })).toBeVisible();
  const button = screen.getByRole("button", { name: "Baixar ficha original assinada" });
  expect(button).toBeEnabled();
  fireEvent.click(button);
  expect(download).toHaveBeenCalledWith("/candidates/person-1/selection-registration.xlsx", "FORM-PPO-RH-002.02-person-1.xlsx");
});

