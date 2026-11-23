import { describe, expect, it } from "vitest";
import { safeReturnPath, registrationReturnPath } from "./returnPath";

describe("Retorno após autenticação", () => {
  it("mantém a vaga guardada quando o cadastro começa pelo perfil", () => {
    const path = "/convite?candidatar=1#token=convite-de-teste";
    const profile = "/candidato/perfil?candidatura=1&next=" + encodeURIComponent(path);
    window.history.replaceState({}, "", "/cadastro?next=" + encodeURIComponent(profile));
    sessionStorage.clear();
    expect(registrationReturnPath()).toBe(path);
    window.history.replaceState({}, "", "/");
    sessionStorage.clear();
  });
  it("preserva o endereço local da vaga e rejeita destinos externos", () => {
    expect(safeReturnPath("/carreiras/vagas/operador")).toBe("/carreiras/vagas/operador");
    for (const path of ["https://example.com", "//example.com", "/\\example.com", "/\n/example.com"]) {
      expect(safeReturnPath(path)).toBeUndefined();
    }
  });
});
