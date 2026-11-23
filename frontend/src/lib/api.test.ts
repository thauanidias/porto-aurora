import { afterEach, describe, expect, it, vi } from "vitest";
import { download, setToken } from "./api";

afterEach(() => { vi.restoreAllMocks(); vi.unstubAllGlobals(); setToken(""); });
describe("Botões de download", () => {
  it("renova a sessão expirada e baixa o arquivo com o novo token", async () => {
    setToken("expired");
    const fetch = vi.fn()
      .mockResolvedValueOnce(new Response("{}", {status: 401}))
      .mockResolvedValueOnce(new Response(JSON.stringify({access_token: "renewed"})))
      .mockResolvedValueOnce(new Response("pdf data"));
    vi.stubGlobal("fetch", fetch);
    vi.stubGlobal("URL", {createObjectURL: vi.fn(() => "blob:test"), revokeObjectURL: vi.fn()});
    const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
    await download("/offers/test/pdf", "oferta.pdf");
    expect(fetch.mock.calls.map(([path]) => path)).toEqual([
      "/api/v1/offers/test/pdf", "/api/v1/auth/refresh", "/api/v1/offers/test/pdf",
    ]);
    expect(fetch.mock.calls[2][1].headers.get("Authorization")).toBe("Bearer renewed");
    expect(click).toHaveBeenCalledOnce();
  });
  it("mostra um erro legível quando o servidor não responde com JSON", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("Bad gateway", {status: 502})));
    await expect(download("/documents/test/download", "cv.pdf")).rejects.toThrow("Não foi possível concluir a operação.");
  });
  it("mostra erro de conexão sem disparar o download", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));
    await expect(download("/reports/vacancies", "vagas.csv")).rejects.toThrow("Verifique sua conexão");
  });
});
