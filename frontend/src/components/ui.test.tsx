import { describe, it, expect } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { ErrorBox, DataTable } from "./ui";
import { ApiError } from "../lib/api";

describe("Retorno operacional", () => {
  it("exibe erro de validação e código de atendimento", () => {
    render(
      <ErrorBox
        error={
          new ApiError(
            "Revise os campos.",
            422,
            [{ field: "email", message: "Inválido" }],
            "request-123",
          )
        }
      />,
    );
    expect(screen.getByRole("alert")).toHaveTextContent("Revise os campos.");
    expect(screen.getByRole("alert")).toHaveTextContent("request-123");
  });
  it("ordena os registros sem alterar a fonte", () => {
    const data = [
      { id: "b", version: 1, name: "Bruno" },
      { id: "a", version: 1, name: "Ana" },
    ];
    render(<DataTable data={data} columns={["name"]} />);
    fireEvent.click(screen.getByRole("button", { name: "Nome" }));
    expect(screen.getAllByRole("row")[1]).toHaveTextContent("Ana");
    expect(data[0].name).toBe("Bruno");
  });
});
