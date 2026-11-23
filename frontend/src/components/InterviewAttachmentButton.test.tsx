import { afterEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { InterviewAttachmentButton } from "./InterviewAttachmentButton";

const session = vi.hoisted(() => ({ data: { permissions: ["candidate.move"] } }));
vi.mock("../lib/session", () => ({ useSession: () => session }));
afterEach(() => { cleanup(); vi.unstubAllGlobals(); session.data.permissions = ["candidate.move"]; });
function mount(phase: string, status = "ACTIVE") {
  return render(<QueryClientProvider client={new QueryClient()}><InterviewAttachmentButton application={{ id: "application-1", version: 1, vacancy_title: "Analista", status, candidate_access: { phase } }} /></QueryClientProvider>);
}
it.each(["TEST", "INTERVIEW"])("attaches the interview and description to the correct application in %s", async phase => {
  const fetch = vi.fn().mockResolvedValue(new Response("{}", { status: 201 }));
  vi.stubGlobal("fetch", fetch); mount(phase);
  fireEvent.click(screen.getByRole("button", { name: "Anexar link da entrevista" }));
  fireEvent.change(screen.getByLabelText("Link da entrevista"), { target: { value: "https://example.com/interview" } });
  fireEvent.change(screen.getByLabelText("Legenda e orientações"), { target: { value: "Compareça às 10h e reserve 30 minutos." } });
  fireEvent.click(screen.getByRole("button", { name: "Salvar link e legenda" }));
  expect(await screen.findByRole("status")).toHaveTextContent("Link da entrevista salvo.");
  expect(fetch.mock.calls[0][0]).toBe("/api/v1/candidate-activity-links");
  expect(JSON.parse(fetch.mock.calls[0][1].body)).toMatchObject({ application_id: "application-1", kind: "INTERVIEW", description: "Compareça às 10h e reserve 30 minutos." });
});
it("hides the shortcut before the eligible stages, after rejection and without RH permission", () => {
  mount("RECRUITMENT"); expect(screen.queryByRole("button")).not.toBeInTheDocument(); cleanup();
  mount("TEST", "REJECTED"); expect(screen.queryByRole("button")).not.toBeInTheDocument(); cleanup();
  session.data.permissions = []; mount("TEST"); expect(screen.queryByRole("button")).not.toBeInTheDocument();
});
