import { expect, it, vi } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { MemoryRouter } from "react-router-dom";
import { PlatformConfiguration } from "./PlatformConfiguration";

vi.mock("../lib/session", () => ({ useSession: () => ({ data: { permissions: ["candidate.view"] }, isPending: false }) }));
it("shows the configuration areas without granting administrative access to recruiters", () => {
  render(<MemoryRouter><PlatformConfiguration /></MemoryRouter>);
  expect(screen.getByRole("heading", { name: "Configuração da plataforma" })).toBeVisible();
  expect(screen.getByRole("heading", { name: "Sistema e processos" })).toBeVisible();
  expect(screen.getAllByText("Acesso administrativo necessário")).toHaveLength(4);
  expect(screen.queryByRole("link", { name: /Abrir configurações/ })).not.toBeInTheDocument();
  cleanup();
});
