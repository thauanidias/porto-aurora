import { afterEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { SchemaForm } from "./SchemaForm";
import { withFormChoices } from "../lib/formChoices";

afterEach(cleanup);
it("filters suggestions and also saves a custom answer", async () => {
  const save = vi.fn(async (_data: Record<string, unknown>) => {});
  render(<QueryClientProvider client={new QueryClient()}><SchemaForm schema={withFormChoices({ type: "object", properties: { education: { type: "string", title: "Escolaridade" } } })} searchableSelects onSubmit={save} submitLabel="Salvar" /></QueryClientProvider>);
  const field = screen.getByRole("combobox", { name: "Escolaridade" });
  fireEvent.change(field, { target: { value: "medio completo" } });
  expect(screen.getByRole("option", { name: "Ensino médio completo" })).toBeVisible();
  expect(screen.queryByRole("option", { name: "Ensino superior completo" })).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("option", { name: "Ensino médio completo" }));
  expect(field).toHaveValue("Ensino médio completo");
  fireEvent.change(field, { target: { value: "Técnico em Informática, cursando" } });
  fireEvent.click(screen.getByRole("button", { name: "Salvar" }));
  await waitFor(() => expect(save).toHaveBeenCalledWith({ education: "Técnico em Informática, cursando" }));
});
