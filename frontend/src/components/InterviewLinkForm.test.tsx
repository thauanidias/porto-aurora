import { afterEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { InterviewLinkForm } from "./InterviewLinkForm";

afterEach(cleanup);
const fill = (name: string, value: string) => fireEvent.change(screen.getByLabelText(name), { target: { value } });
const submit = () => fireEvent.click(screen.getByRole("button", { name: "Salvar link e legenda" }));

it("bloqueia campos vazios e mostra mensagens em português sem chamar a API", () => {
  const save = vi.fn();
  render(<InterviewLinkForm onSubmit={save} />);
  submit();
  expect(save).not.toHaveBeenCalled();
  expect(screen.getByText("Informe o link da entrevista.")).toBeVisible();
  expect(screen.getByText("Escreva uma legenda com pelo menos 3 caracteres.")).toBeVisible();
  expect(screen.getByLabelText("Link da entrevista")).toHaveFocus();
});

it.each(["javascript:alert(1)", "https://user:pass@example.com", "endereço inválido"])("rejeita endereço inválido %s", url => {
  const save = vi.fn();
  render(<InterviewLinkForm onSubmit={save} />);
  fill("Link da entrevista", url);
  fill("Legenda e orientações", "Entrevista às 10h.");
  submit();
  expect(save).not.toHaveBeenCalled();
  expect(screen.getByText(/Informe um link válido/)).toBeVisible();
});

it("salva valores sem espaços nas extremidades", async () => {
  const save = vi.fn().mockResolvedValue(undefined);
  render(<InterviewLinkForm onSubmit={save} />);
  fill("Título do link", "  Entrevista com o Gestor  ");
  fill("Link da entrevista", "https://example.com/entrevista");
  fill("Legenda e orientações", "  Dia 20, às 10h.  ");
  submit();
  await waitFor(() => expect(save).toHaveBeenCalledWith({ title: "Entrevista com o Gestor", url: "https://example.com/entrevista", description: "Dia 20, às 10h." }));
});

it("preserva os dados e exibe uma única mensagem quando o salvamento falha", async () => {
  const save = vi.fn().mockRejectedValue(new Error("Falha ao salvar. Tente novamente."));
  render(<InterviewLinkForm onSubmit={save} />);
  fill("Link da entrevista", "https://example.com/entrevista");
  fill("Legenda e orientações", "Dia 20, às 10h.");
  submit();
  await screen.findByText("Falha ao salvar. Tente novamente.");
  expect(screen.getAllByRole("alert")).toHaveLength(1);
  expect(screen.getByLabelText("Legenda e orientações")).toHaveValue("Dia 20, às 10h.");
  expect(screen.getByRole("button", { name: "Salvar link e legenda" })).toBeEnabled();
});
