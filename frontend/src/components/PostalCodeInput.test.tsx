import "@testing-library/jest-dom/vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { useState } from "react";
import { afterEach, expect, it, vi } from "vitest";
import { PostalCodeInput } from "./PostalCodeInput";
import { api } from "../lib/api";
vi.mock("../lib/api", () => ({ api: vi.fn() }));
afterEach(cleanup);

it("consulta o CEP completo e retorna os dados de endereço", async () => {
  vi.mocked(api).mockResolvedValue({ neighborhood: "Centro", city: "Barcarena", state: "PA" });
  const apply = vi.fn();
  function Form() { const [value, setValue] = useState(""); return <PostalCodeInput title="CEP" value={value} onChange={setValue} onAddress={apply} />; }
  render(<Form />);
  fireEvent.change(screen.getByLabelText("CEP"), { target: { value: "68445000" } });
  await waitFor(() => expect(apply).toHaveBeenCalledWith({ neighborhood: "Centro", city: "Barcarena", state: "PA" }));
  expect(screen.getByLabelText("CEP")).toHaveValue("68445-000");
});

it("mantém o preenchimento manual quando a consulta falha", async () => {
  vi.mocked(api).mockRejectedValue(new Error("offline"));
  const apply = vi.fn();
  function Form() { const [value, setValue] = useState(""); return <PostalCodeInput title="CEP" value={value} onChange={setValue} onAddress={apply} />; }
  render(<Form />);
  fireEvent.change(screen.getByLabelText("CEP"), { target: { value: "66000000" } });
  expect(await screen.findByText(/Preencha os campos manualmente/)).toBeInTheDocument();
  expect(apply).not.toHaveBeenCalled();
});
