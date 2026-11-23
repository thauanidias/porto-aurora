import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { DeadlineInput } from "./DeadlineInput";

afterEach(cleanup);

describe("Prazo final em português", () => {
  it("exibe dia antes do mês e converte a digitação para o valor local da API", () => {
    const onChange = vi.fn();
    render(<DeadlineInput title="Prazo final" value="2026-09-23T17:30" onChange={onChange} />);
    const input = screen.getByLabelText("Prazo final");
    expect(input).toHaveValue("23/09/2026 17:30");
    fireEvent.change(input, { target: { value: "05/10/2026 09:15" } });
    expect(onChange).toHaveBeenCalledWith("2026-10-05T09:15");
    expect(input).toBeValid();
  });

  it("bloqueia datas inexistentes e aceita ano bissexto e limpeza", () => {
    render(<DeadlineInput title="Prazo final" value="" onChange={vi.fn()} />);
    const input = screen.getByLabelText("Prazo final");
    for (const value of ["31/02/2026 12:00", "29/02/2026 12:00", "23/09/2026 25:00", "23/09"]) {
      fireEvent.change(input, { target: { value } });
      expect(input).toBeInvalid();
    }
    fireEvent.change(input, { target: { value: "29/02/2028 12:00" } });
    expect(input).toBeValid();
    fireEvent.change(input, { target: { value: "" } });
    expect(input).toBeValid();
  });

  it("exibe horários com fuso na hora local e permite selecionar pelo calendário", () => {
    const onChange = vi.fn();
    const value = "2026-09-23T17:30:00+03:00";
    render(<DeadlineInput title="Prazo final" value={value} onChange={onChange} />);
    const date = new Date(value);
    const pad = (n: number) => String(n).padStart(2, "0");
    expect(screen.getByLabelText("Prazo final")).toHaveValue(
      `${pad(date.getDate())}/${pad(date.getMonth() + 1)}/${date.getFullYear()} ${pad(date.getHours())}:${pad(date.getMinutes())}`,
    );
    fireEvent.change(screen.getByLabelText("Selecionar prazo final no calendário"), {
      target: { value: "2026-10-05T09:15" },
    });
    expect(onChange).toHaveBeenCalledWith("2026-10-05T09:15");
  });
});
