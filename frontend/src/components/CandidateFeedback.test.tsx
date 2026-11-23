import { expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { CandidateFeedbackButton } from "./CandidateFeedback";

it("sends candidate feedback with the selected application and confirms receipt", async () => {
  const fetchMock = vi.fn(async (_url: string, options?: RequestInit) => new Response(JSON.stringify(options?.method === "POST" ? { id: "feedback" } : { items: [{ id: "application", vacancy_title: "Estagiário de TI" }], total: 1 }), { status: 200 }));
  vi.stubGlobal("fetch", fetchMock);
  const client = new QueryClient();
  const view = render(<QueryClientProvider client={client}><CandidateFeedbackButton /></QueryClientProvider>);
  fireEvent.click(screen.getByRole("button", { name: "Enviar feedback" }));
  fireEvent.change(await screen.findByLabelText("Seu feedback"), { target: { value: "Gostei das orientações recebidas durante o processo." } });
  fireEvent.click(screen.getByRole("button", { name: "Enviar feedback ao RH" }));
  expect(await screen.findByRole("status")).toHaveTextContent("Seu feedback foi enviado ao RH");
  const request = fetchMock.mock.calls.find(([url]) => url.endsWith("/candidate-feedback"));
  expect(JSON.parse(String(request?.[1]?.body))).toEqual({ application_id: "application", message: "Gostei das orientações recebidas durante o processo.", rating: null });
  view.unmount(); client.clear(); vi.unstubAllGlobals();
});
