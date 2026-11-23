import { afterEach, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { getDocument } from "pdfjs-dist";
import ResumePreview from "./ResumePreview";

vi.mock("pdfjs-dist", () => ({ GlobalWorkerOptions: {}, getDocument: vi.fn() }));
afterEach(() => { cleanup(); vi.restoreAllMocks(); });

it("mostra todas as páginas sem iframe, barra de ferramentas ou miniaturas", async () => {
  vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue({} as CanvasRenderingContext2D);
  const destroy = vi.fn().mockResolvedValue(undefined);
  const page = { getViewport: () => ({ width: 800, height: 1100 }), render: () => ({ promise: Promise.resolve() }), getTextContent: async () => ({ items: [{ str: "Experiência profissional fictícia" }] }), cleanup: vi.fn() };
  vi.mocked(getDocument).mockReturnValue({ promise: Promise.resolve({ numPages: 2, getPage: async () => page }), destroy } as unknown as ReturnType<typeof getDocument>);
  const data = new Uint8Array([37, 80, 68, 70]);
  const { container, unmount } = render(<ResumePreview data={data} />);
  expect(await screen.findByRole("img", { name: /página 2 de 2.*Experiência profissional fictícia/ })).toBeVisible();
  expect(container.querySelectorAll("canvas")).toHaveLength(2);
  expect(container.querySelector("iframe")).toBeNull();
  expect(getDocument).toHaveBeenCalledWith({ data });
  unmount();
  expect(destroy).toHaveBeenCalled();
});

it("informa falha de leitura sem deixar o carregamento preso", async () => {
  vi.mocked(getDocument).mockReturnValue({ promise: Promise.reject(new Error("Arquivo não pôde ser lido.")), destroy: vi.fn().mockResolvedValue(undefined) } as unknown as ReturnType<typeof getDocument>);
  render(<ResumePreview data={new Uint8Array([0])} />);
  expect(await screen.findByRole("alert")).toHaveTextContent("Arquivo não pôde ser lido.");
  expect(screen.queryByRole("status")).not.toBeInTheDocument();
});
