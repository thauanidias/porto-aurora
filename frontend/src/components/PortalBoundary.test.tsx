import { afterEach, describe, expect, it } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { portal, type PortalArea } from "../lib/portal";
import { PortalBoundary } from "./PortalBoundary";

afterEach(() => { cleanup(); portal.area = "LOCAL"; portal.publicUrl = ""; });

function open(area: PortalArea, path: string) {
  portal.area = area;
  render(<MemoryRouter initialEntries={[path]}><PortalBoundary>
    <Routes><Route path="*" element={<h1>Conteúdo permitido</h1>} /></Routes>
  </PortalBoundary></MemoryRouter>);
}

describe("Isolamento dos portais", () => {
  it.each(["/app", "/app/vagas", "/gestor", "/entrar-rh", "/entrar-gestor", "/cadastro-gestor"])("bloqueia %s no portal público", path => {
    open("CANDIDATO", path);
    expect(screen.getByRole("heading")).toHaveTextContent("Página não encontrada");
  });
  it.each([["RH", "/entrar-gestor"], ["GESTOR", "/entrar-rh"], ["GESTOR", "/app/administracao"]] as const)("bloqueia navegação entre perfis: %s %s", (area, path) => {
    open(area, path);
    expect(screen.getByRole("heading")).toHaveTextContent("Página não encontrada");
  });
  it.each([["RH", "/app"], ["GESTOR", "/gestor"], ["CANDIDATO", "/entrar"], ["LOCAL", "/entrar-rh"]] as const)("permite a área correta: %s %s", (area, path) => {
    open(area, path);
    expect(screen.getByRole("heading")).toHaveTextContent("Conteúdo permitido");
  });
});
