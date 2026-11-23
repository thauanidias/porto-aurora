import { afterEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { api } from "../lib/api";
import { CandidateConsentPrompt } from "./CandidateConsentPrompt";

vi.mock("../lib/session", () => ({ useSession: () => ({ data: { user: { id: "candidate-1", kind: "CANDIDATE", name: "Maria", email: "maria@example.com" } } }) }));
vi.mock("../lib/api", async importOriginal => ({ ...await importOriginal<typeof import("../lib/api")>(), api: vi.fn() }));
vi.mock("./ConsentTerm", () => ({ ConsentTerm: ({ onAccept }: { onAccept: (receipt: unknown) => void }) => <button onClick={() => onAccept({ id: "receipt-1", context: "CADASTRO" })}>Aceitar este documento</button> }));
afterEach(() => { cleanup(); vi.resetAllMocks(); });

function show() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><CandidateConsentPrompt><p>Perfil liberado para preenchimento</p></CandidateConsentPrompt></QueryClientProvider>);
  return client;
}

it("opens on entry without registration consent and closes after acceptance", async () => {
  vi.mocked(api).mockResolvedValue({ items: [], total: 0, page_size: 25 });
  const client = show();
  expect(await screen.findByRole("region", { name: "Aceite obrigatório do termo de consentimento" })).toBeVisible();
  expect(screen.queryByText("Perfil liberado para preenchimento")).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Fechar" })).not.toBeInTheDocument();
  vi.mocked(api).mockResolvedValue({ items: [{ id: "receipt-1", context: "CADASTRO" }], total: 1, page_size: 25 });
  fireEvent.click(screen.getByRole("button", { name: "Aceitar este documento" }));
  expect(await screen.findByText("Perfil liberado para preenchimento")).toBeVisible();
  expect(client.getQueryData(["consent-receipts", "entry", "candidate-1"])).toMatchObject({ id: "receipt-1" });
});

it("checks later pages before prompting someone who already accepted", async () => {
  vi.mocked(api)
    .mockResolvedValueOnce({ items: [{ id: "application", context: "CANDIDATURA" }], total: 2, page_size: 1 })
    .mockResolvedValueOnce({ items: [{ id: "registration", context: "CADASTRO" }], total: 2, page_size: 1 });
  const client = show();
  await waitFor(() => expect(client.getQueryData(["consent-receipts", "entry", "candidate-1"])).toMatchObject({ id: "registration" }));
  expect(screen.getByText("Perfil liberado para preenchimento")).toBeVisible();
});

it("does not treat a failed lookup as missing consent", async () => {
  vi.mocked(api).mockRejectedValue(new Error("Falha de conexão"));
  const client = show();
  await waitFor(() => expect(client.getQueryState(["consent-receipts", "entry", "candidate-1"])?.status).toBe("error"));
  expect(screen.queryByText("Perfil liberado para preenchimento")).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Tentar novamente" })).toBeVisible();
});
