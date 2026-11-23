import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { LocationChoice } from "./LocationChoice";
import { SchemaForm } from "./SchemaForm";
import localities from "../data/localities.json";

afterEach(cleanup);

describe("Localidades da vaga", () => {
  it("pesquisa sem acentos e envia cidade e UF, limpando a cidade ao trocar o estado", async () => {
    const submit = vi.fn();
    render(<SchemaForm layout="vacancy" schema={{ type: "object", properties: {
      city: { type: "string" }, state: { type: "string" },
    } }} initial={{ state: "PA", city: "Barcarena" }} onSubmit={submit} />);
    expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
    expect(screen.getByRole("searchbox", { name: "Buscar Cidade" })).toHaveValue("Barcarena");
    fireEvent.click(screen.getByRole("button", { name: "Mostrar opções de Cidade" }));
    expect(screen.getByRole("listbox", { name: "Cidade" })).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Fechar opções de Cidade" }));
    fireEvent.click(screen.getByRole("button", { name: "Mostrar opções de Estado" }));
    expect(screen.getByRole("listbox", { name: "Estado" }).querySelectorAll("option")).toHaveLength(28);
    fireEvent.click(screen.getByRole("button", { name: "Fechar opções de Estado" }));
    fireEvent.change(screen.getByRole("searchbox", { name: "Buscar Cidade" }), { target: { value: "belem" } });
    const city = screen.getByRole("option", { name: "Belém" }) as HTMLOptionElement;
    fireEvent.change(screen.getByRole("listbox", { name: "Cidade" }), { target: { value: city.value } });
    expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
    expect(screen.getByRole("searchbox", { name: "Buscar Cidade" })).toHaveValue("Belém");
    fireEvent.click(screen.getByRole("button", { name: "Salvar" }));
    await waitFor(() => expect(submit).toHaveBeenLastCalledWith({ city: "Belém", state: "PA" }));
    fireEvent.change(screen.getByRole("searchbox", { name: "Buscar Estado" }), { target: { value: "sao paulo" } });
    expect(screen.getByRole("option", { name: "São Paulo (SP)" })).toBeVisible();
    fireEvent.change(screen.getByRole("listbox", { name: "Estado" }), { target: { value: "SP" } });
    expect(screen.queryByRole("option", { name: "Belém" })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Salvar" }));
    await waitFor(() => expect(submit).toHaveBeenLastCalledWith({ city: "", state: "SP" }));
  });

  it("permite buscar em todos os estados e identifica a UF da cidade escolhida", () => {
    const change = vi.fn();
    render(<LocationChoice field="city" city="" state="" onChange={change} />);
    expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
    fireEvent.focus(screen.getByRole("searchbox"));
    expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
    fireEvent.change(screen.getByRole("searchbox"), { target: { value: "barcarena" } });
    const option = screen.getByRole("option", { name: "Barcarena" }) as HTMLOptionElement;
    fireEvent.change(screen.getByRole("listbox"), { target: { value: option.value } });
    expect(change).toHaveBeenCalledWith("Barcarena", "PA");
    expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
    fireEvent.change(screen.getByRole("searchbox"), { target: { value: "cidade inexistente xyz" } });
    expect(screen.getByRole("status")).toHaveTextContent("Nenhum resultado");
    fireEvent.change(screen.getByRole("searchbox"), { target: { value: "" } });
    expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
    expect(localities.states).toHaveLength(27);
    expect(localities.cities.every((city) => localities.states.some((state) => state.code === city.state))).toBe(true);
  });
});
