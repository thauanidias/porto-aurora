import { describe, it, expect, vi, afterEach } from "vitest";
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { SchemaForm, type Schema } from "./SchemaForm";
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});
it("saves a vacancy draft without publishing even when publication is selected", async () => {
  const submit = vi.fn();
  const schema: Schema = { type: "object", properties: { title: { type: "string" }, publish_on_save: { type: "boolean" } } };
  render(<SchemaForm schema={schema} layout="vacancy" initial={{ title: "Teste", publish_on_save: true }} onSubmit={submit} />);
  fireEvent.click(screen.getByRole("button", { name: "Salvar rascunho" }));
  await waitFor(() => expect(submit).toHaveBeenCalledWith({ title: "Teste", publish_on_save: false }));
});

it("keeps regular vacancy save publication behavior", async () => {
  const submit = vi.fn();
  const schema: Schema = { type: "object", properties: { title: { type: "string" }, publish_on_save: { type: "boolean" } } };
  render(<SchemaForm schema={schema} layout="vacancy" initial={{ title: "Teste", publish_on_save: true }} onSubmit={submit} />);
  fireEvent.click(screen.getByRole("button", { name: "Salvar" }));
  await waitFor(() => expect(submit).toHaveBeenCalledWith({ title: "Teste", publish_on_save: true }));
});
it("aplica sugestões somente a campos vazios e preserva alterações no perfil", async () => {
  const schema: Schema = { type: "object", properties: {
    name: { type: "string", title: "Nome" }, phone: { type: "string", title: "Telefone" },
  } };
  const submit = vi.fn();
  const { rerender } = render(<SchemaForm schema={schema} initial={{ name: "Nome existente" }} onSubmit={submit} />);
  fireEvent.change(screen.getByLabelText("Nome"), { target: { value: "Nome revisado" } });
  rerender(<SchemaForm schema={schema} initial={{ name: "Nome existente" }} onSubmit={submit} suggestions={{ name: "Nome do PDF", phone: "91999991234" }} />);
  expect(screen.getByLabelText("Nome")).toHaveValue("Nome revisado");
  await waitFor(() => expect(screen.getByLabelText("Telefone")).toHaveValue("91999991234"));
  fireEvent.click(screen.getByRole("button", { name: "Salvar" }));
  await waitFor(() => expect(submit).toHaveBeenCalledWith({ name: "Nome revisado", phone: "91999991234" }));
});
describe("Certificações", () => {
  it("anexa um PDF à certificação enviada com o perfil", async () => {
    const id = "0d0d551b-bbe7-4d56-a659-9cc5bf00a50a";
    vi.stubGlobal(
      "fetch",
      vi.fn(
        async (_url: string, init?: RequestInit) =>
          new Response(
            JSON.stringify(
              init?.method === "POST"
                ? { id, filename: "certificado.pdf" }
                : {
                    items: [{ id, filename: "certificado.pdf" }],
                    total: 1,
                    page: 1,
                    page_size: 100,
                  },
            ),
            { status: init?.method === "POST" ? 201 : 200 },
          ),
      ),
    );
    const submit = vi.fn();
    const schema: Schema = {
      type: "object",
      properties: {
        profile: {
          type: "object",
          properties: {
            certifications: {
              type: "array",
              title: "Certificações",
              items: {
                type: "object",
                properties: {
                  name: { type: "string", title: "Certificação" },
                  document_id: {
                    anyOf: [{ type: "string" }, { type: "null" }],
                    default: null,
                  },
                },
              },
            },
          },
        },
      },
    };
    render(
      <QueryClientProvider client={new QueryClient()}>
        <SchemaForm schema={schema} onSubmit={submit} />
      </QueryClientProvider>,
    );
    fireEvent.click(
      screen.getByRole("button", { name: "Adicionar certificação" }),
    );
    fireEvent.change(screen.getByLabelText("Certificação"), {
      target: { value: "Operação portuária" },
    });
    expect(screen.getByRole("button", { name: "Selecionar PDF" })).toHaveClass(
      "button",
    );
    fireEvent.change(screen.getByLabelText("PDF do certificado"), {
      target: {
        files: [
          new File(["%PDF-1.4\n%%EOF"], "certificado.pdf", {
            type: "application/pdf",
          }),
        ],
      },
    });
    await screen.findByText("Baixar certificado.pdf");
    expect(
      screen.getByRole("button", { name: "Substituir PDF" }),
    ).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Salvar" }));
    await waitFor(() =>
      expect(submit).toHaveBeenCalledWith({
        profile: {
          certifications: [{ name: "Operação portuária", document_id: id }],
        },
      }),
    );
  });
});
describe("Formulários estruturados", () => {
  it("preserva os dados da vaga ao organizar campos em seções", async () => {
    const submit = vi.fn();
    render(
      <SchemaForm
        layout="vacancy"
        schema={{ type: "object", properties: {
          title: { type: "string" },
          quantity: { type: "integer" },
          publish_on_save: { type: "boolean", default: false },
          details: { type: "object", properties: {
            salary: { type: "number" },
            hide_salary: { type: "boolean", default: true },
            responsibilities: { type: "string" },
            requirements: { type: "string" },
            benefits: { type: "string" },
          } },
        } }}
        initial={{ title: "Analista", quantity: 2, details: { salary: 4000, hide_salary: true, responsibilities: "Atender equipes", requirements: "Ensino médio", benefits: "Vale-alimentação" } }}
        onSubmit={submit}
      />,
    );
    expect(screen.getAllByRole("group").slice(0, 4).map((group) => group.querySelector("legend")?.textContent)).toEqual(["Oportunidade", "Principais atividades", "Requisitos", "Benefícios"]);
    expect(screen.queryByRole("group", { name: "Inscrições" })).not.toBeInTheDocument();
    expect(screen.getByLabelText("Principais atividades")).toHaveValue("Atender equipes");
    fireEvent.change(screen.getByLabelText("Título"), { target: { value: "Analista de RH" } });
    fireEvent.click(screen.getByLabelText("Publicar ao salvar"));
    fireEvent.click(screen.getByRole("button", { name: "Salvar" }));
    await waitFor(() => expect(submit).toHaveBeenCalledWith({
      title: "Analista de RH", quantity: 2, publish_on_save: true,
      details: { salary: 4000, hide_salary: true, responsibilities: "Atender equipes", requirements: "Ensino médio", benefits: "Vale-alimentação" },
    }));
  });

  it("aceita digitar o nome de uma recrutadora do RH", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({
      items: [{ id: "rh-1", name: "Adylane de Sales Oliveira" }],
      total: 1,
      page: 1,
      page_size: 100,
    }), { status: 200 })));
    const submit = vi.fn();
    render(
      <QueryClientProvider client={new QueryClient()}>
        <SchemaForm
          schema={{ type: "object", properties: { recruiter_id: { type: "string" } } }}
          searchableSelects
          onSubmit={submit}
        />
      </QueryClientProvider>,
    );
    await waitFor(() => expect(document.querySelector("datalist option")).not.toBeNull());
    const field = screen.getByRole("combobox", { name: "Recrutador responsável" });
    fireEvent.change(field, { target: { value: "Adylane de Sales Oliveira" } });
    fireEvent.click(screen.getByRole("button", { name: "Salvar" }));
    await waitFor(() => expect(submit).toHaveBeenCalledWith({ recruiter_id: "rh-1" }));
  });

  it("permite digitar para localizar opções válidas da vaga", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response(JSON.stringify({
        items: [
          { id: "setor-1", name: "Almoxarifado" },
          { id: "setor-2", name: "Operação Portuária" },
        ],
        total: 2,
        page: 1,
        page_size: 100,
      }), { status: 200 })),
    );
    const submit = vi.fn();
    render(
      <QueryClientProvider client={new QueryClient()}>
        <SchemaForm
          schema={{ type: "object", properties: {
            org_unit_id: { type: "string" },
            audience: { type: "string", enum: ["EXTERNAL", "INTERNAL"] },
          } }}
          searchableSelects
          onSubmit={submit}
        />
      </QueryClientProvider>,
    );
    expect(screen.queryByRole("listbox", { name: "Centro de custo" })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Mostrar opções de Centro de custo" }));
    await screen.findByRole("option", { name: "Almoxarifado" });
    fireEvent.click(screen.getByRole("button", { name: "Fechar opções de Centro de custo" }));
    expect(screen.queryByRole("listbox", { name: "Centro de custo" })).not.toBeInTheDocument();
    fireEvent.change(screen.getByRole("combobox", { name: "Centro de custo" }), {
      target: { value: "operacao" },
    });
    await screen.findByRole("option", { name: "Operação Portuária" });
    expect(screen.getByRole("option", { name: "Operação Portuária" })).toBeVisible();
    expect(screen.queryByRole("option", { name: "Almoxarifado" })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("option", { name: "Operação Portuária" }));
    expect(screen.getByRole("combobox", { name: "Centro de custo" })).toHaveValue("Operação Portuária");
    expect(screen.queryByRole("listbox", { name: "Centro de custo" })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Salvar" }));
    await waitFor(() => expect(submit).toHaveBeenCalledWith({
      org_unit_id: "setor-2", audience: "EXTERNAL",
    }));
  });

  it("oferece centros de custo ativos e preserva a seleção antiga", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({ items: [
      { id: "legacy", name: "Setor já vinculado", kind: "SECTOR", active: true },
      { id: "other", name: "Outro setor", kind: "SECTOR", active: true },
      { id: "cc", name: "Turno A", kind: "COST_CENTER", active: true },
      { id: "inactive", name: "Centro inativo", kind: "COST_CENTER", active: false },
    ], total: 4, page: 1, page_size: 100 }), { status: 200 })));
    render(<QueryClientProvider client={new QueryClient()}><SchemaForm schema={{ type: "object", properties: { org_unit_id: { type: "string" } } }} initial={{ org_unit_id: "legacy" }} searchableSelects onSubmit={vi.fn()} /></QueryClientProvider>);
    await waitFor(() => expect(screen.getByRole("combobox", { name: "Centro de custo" })).toHaveValue("Setor já vinculado"));
    fireEvent.click(screen.getByRole("button", { name: "Mostrar opções de Centro de custo" }));
    expect(await screen.findByRole("option", { name: "Turno A" })).toBeVisible();
    expect(screen.getByRole("option", { name: "Setor já vinculado" })).toBeVisible();
    expect(screen.queryByRole("option", { name: "Outro setor" })).not.toBeInTheDocument();
    expect(screen.queryByRole("option", { name: "Centro inativo" })).not.toBeInTheDocument();
  });

  it("envia campos, booleanos e listas com seus tipos", async () => {
    const submit = vi.fn();
    const schema: Schema = {
      type: "object",
      properties: {
        name: { type: "string", title: "Nome" },
        quantity: { type: "integer", title: "Quantidade" },
        active: { type: "boolean", title: "Ativo" },
        skills: {
          type: "array",
          title: "Competências",
          items: { type: "string", title: "Competência" },
        },
      },
    };
    render(<SchemaForm schema={schema} onSubmit={submit} />);
    fireEvent.change(screen.getByLabelText("Nome"), {
      target: { value: "Registro real" },
    });
    fireEvent.change(screen.getByLabelText("Quantidade"), {
      target: { value: "3" },
    });
    fireEvent.click(screen.getByLabelText("Ativo"));
    fireEvent.click(
      screen.getByRole("button", { name: "Adicionar competências" }),
    );
    fireEvent.change(screen.getByLabelText("Competência"), {
      target: { value: "Segurança" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Salvar" }));
    await waitFor(() =>
      expect(submit).toHaveBeenCalledWith({
        name: "Registro real",
        quantity: 3,
        active: true,
        skills: ["Segurança"],
      }),
    );
  });
  it("preserva campos aninhados do perfil", async () => {
    const submit = vi.fn();
    const schema: Schema = {
      type: "object",
      properties: {
        profile: {
          type: "object",
          title: "Perfil",
          properties: { city: { type: "string", title: "Cidade" } },
        },
      },
    };
    render(
      <SchemaForm
        schema={schema}
        initial={{ profile: { city: "Belém" } }}
        onSubmit={submit}
      />,
    );
    fireEvent.change(screen.getByLabelText("Cidade"), {
      target: { value: "Barcarena" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Salvar" }));
    await waitFor(() =>
      expect(submit).toHaveBeenCalledWith({ profile: { city: "Barcarena" } }),
    );
  });
});
