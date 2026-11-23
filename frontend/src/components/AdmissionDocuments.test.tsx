import { afterEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { AdmissionDocuments } from "./AdmissionDocuments";

vi.mock("../lib/session", () => ({ useSession: () => ({ data: { permissions: ["document.review"] } }) }));

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

it("permite corrigir um documento recusado e preserva o acesso ao arquivo anterior", async () => {
  const checklist = { internal_account: false, eligible: true, approved: true, can_upload: true,
    can_approve: false, has_profile: true, items: [
      { type_name: "ADM_RG", title: "RG", group: "Candidato", description: "", document: {
        id: "rg", filename: "rg.pdf", status: "REJECTED", comment: "Envie todas as páginas.", revision: 1,
      } },
    ] };
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify(checklist))));
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><MemoryRouter><AdmissionDocuments /></MemoryRouter></QueryClientProvider>);
  expect(await screen.findByRole("button", { name: "Enviar correção" })).toBeEnabled();
  expect(screen.getByText("Retorno do RH: Envie todas as páginas.")).toBeVisible();
  expect(screen.getByRole("button", { name: "Baixar" })).toBeEnabled();
  fireEvent.change(screen.getByLabelText("Enviar RG"), { target: { files: [new File(["%PDF-1.4"], "corrigido.pdf", { type: "application/pdf" })] } });
  expect(await screen.findByRole("button", { name: "Confirmar envio definitivo" })).toBeEnabled();
  client.clear();
});

it("distingue documentos em análise dos não enviados", async () => {
  const checklist = { internal_account: true, eligible: false, approved: false, can_upload: true, can_approve: false, has_profile: true,
    items: [
      { type_name: "ADM_RG", title: "RG", group: "Candidato", description: "", document: { id: "rg", filename: "rg.pdf", status: "PENDING", revision: 1 } },
      { type_name: "ADM_CPF", title: "CPF", group: "Candidato", description: "", document: null },
    ],
  };
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify(checklist))));
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><MemoryRouter><AdmissionDocuments candidateId="person-1" /></MemoryRouter></QueryClientProvider>);
  const visual = await screen.findByRole("region", { name: "Checklist de documentos enviados" });
  const entries = within(visual).getAllByRole("listitem");
  expect(entries[0]).toHaveClass("sent");
  expect(entries[0]).toHaveTextContent("RGAguardando análise");
  expect(entries[1]).toHaveClass("missing");
  expect(entries[1]).toHaveTextContent("CPFNão enviado");
  expect(within(entries[1]).getByRole("button", { name: "Aceito: CPF" })).toBeDisabled();
  expect(within(entries[1]).getByRole("button", { name: "Não aceito: CPF" })).toBeDisabled();
  expect(screen.getByText("1 de 2 itens enviados")).toBeVisible();
  expect(screen.queryByRole("button", { name: "Baixar" })).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Visualizar arquivos e ações" }));
  expect(screen.getAllByRole("button", { name: "Baixar" })[0]).toBeVisible();
  client.clear();
});

it("mostra apenas visualizar e baixar após aceite e devolve documentos pendentes com motivo", async () => {
  const document = { id: "rg", version: 3, filename: "rg.pdf", status: "PENDING", comment: "" };
  const checklist = { internal_account: true, can_upload: true, approved: true, has_profile: true, can_approve: false,
    items: [{ type_name: "ADM_RG", title: "RG", group: "Candidato", description: "", document }] };
  const fetchMock = vi.fn(async (_url: string, init?: RequestInit) => {
    if (init?.method === "PUT") {
      const body = JSON.parse(String(init.body));
      Object.assign(document, { status: body.status, comment: body.comment, version: document.version + 1 });
      return new Response(JSON.stringify(document));
    }
    return new Response(JSON.stringify(checklist));
  });
  vi.stubGlobal("fetch", fetchMock);
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><MemoryRouter><AdmissionDocuments candidateId="person-1" /></MemoryRouter></QueryClientProvider>);
  const visual = await screen.findByRole("region", { name: "Checklist de documentos enviados" });
  fireEvent.click(within(visual).getByRole("button", { name: "Aceito: RG" }));
  await waitFor(() => expect(within(visual).getByRole("listitem")).toHaveClass("review-approved"));
  expect(fetchMock.mock.calls.find(([, init]) => init?.method === "PUT")?.[0]).toBe("/api/v1/documents/rg/review");
  expect(within(visual).queryByRole("button", { name: "Aceito: RG" })).not.toBeInTheDocument();
  expect(within(visual).queryByRole("button", { name: "Não aceito: RG" })).not.toBeInTheDocument();
  expect(within(visual).getByRole("button", { name: "Visualizar: RG" })).toBeVisible();
  expect(within(visual).getByRole("button", { name: "Baixar: RG" })).toBeVisible();
  document.status = "PENDING";
  await client.invalidateQueries({ queryKey: ["documents"] });
  fireEvent.click(await within(visual).findByRole("button", { name: "Não aceito: RG" }));
  const dialog = screen.getByRole("dialog", { name: "Devolver documento para correção" });
  const confirm = within(dialog).getByRole("button", { name: "Não aceitar e devolver" });
  expect(confirm).toBeDisabled();
  fireEvent.change(within(dialog).getByLabelText("O que precisa ser corrigido?"), { target: { value: "Envie frente e verso em PDF legível." } });
  fireEvent.click(confirm);
  await waitFor(() => expect(within(visual).getByRole("listitem")).toHaveClass("review-rejected"));
  expect(within(visual).getByText(/Envie frente e verso/)).toBeVisible();
  const mutation = fetchMock.mock.calls.filter(([, init]) => init?.method === "PUT").at(-1);
  expect(JSON.parse(String(mutation?.[1]?.body))).toEqual({ version: 4, status: "REJECTED", comment: "Envie frente e verso em PDF legível." });
  client.clear();
});

it("mostra a lista bloqueada e libera o envio apenas com autorização da etapa", async () => {
  const checklist = {
    eligible: false, approved: false, can_upload: false,
    internal_account: false, has_profile: true, can_approve: false,
    items: [
      { type_name: "ADM_RG", title: "RG", description: "A CNH não substitui o RG.", group: "Candidato", document: null },
      { type_name: "ADM_DEP_CPF", title: "CPF dos dependentes", description: "", group: "Dependentes", document: null },
    ],
  };
  const fetchMock = vi.fn(async () => new Response(JSON.stringify(checklist)));
  vi.stubGlobal("fetch", fetchMock);
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><MemoryRouter><AdmissionDocuments /></MemoryRouter></QueryClientProvider>);
  await waitFor(() => expect(client.getQueryData(["documents", "admission-checklist", "me"])).toBeDefined());
  expect(screen.queryByRole("heading", { name: "Documentos admissionais" })).not.toBeInTheDocument();
  const file = new File(["%PDF-1.4"], "rg.pdf", { type: "application/pdf" });
  expect(screen.queryByRole("button", { name: "Confirmar envio definitivo" })).not.toBeInTheDocument();

  client.setQueryData(["documents", "admission-checklist", "me"], { ...checklist, eligible: true });
  await waitFor(() => expect(screen.queryByRole("heading", { name: "Documentos admissionais" })).not.toBeInTheDocument());
  client.setQueryData(["documents", "admission-checklist", "me"], { ...checklist, eligible: true, approved: true, can_upload: true });
  await waitFor(() => expect(screen.getAllByRole("button", { name: "Inserir arquivo" })[0]).toBeEnabled());
  fireEvent.change(screen.getByLabelText("Enviar RG"), { target: { files: [file] } });
  const confirm = await screen.findByRole("button", { name: "Confirmar envio definitivo" });
  expect(confirm).toBeEnabled();

  client.setQueryData(["documents", "admission-checklist", "me"], checklist);
  await waitFor(() => expect(screen.queryByRole("button", { name: "Confirmar envio definitivo" })).not.toBeInTheDocument());
  expect(fetchMock).toHaveBeenCalledTimes(1);
  client.clear();
});
