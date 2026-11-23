import { afterEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { MemoryRouter } from "react-router-dom";
import { CandidateStageAction, candidateStageDestination } from "./CandidateStageAction";
import type { Row } from "../lib/api";

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
function application(phase: string, permissions: Record<string, boolean>, status = "NOT_SENT"): Row {
  return { id: "own-application", version: 1, candidate_access: { phase, permissions }, process_form_status: status };
}
it.each([["INTERVIEW", "interviews", "/candidato/entrevistas"], ["TEST", "tests", "/candidato/testes"], ["ADMISSION", "admission", "/candidato/documentos"]])("opens the released %s area", (phase, permission, path) => {
  const row = application(phase, { [permission]: true });
  render(<MemoryRouter><CandidateStageAction application={row} compact label="Etapa atual" /></MemoryRouter>);
  expect(screen.getByRole("link", { name: "Etapa atual" })).toHaveAttribute("href", path);
  expect(candidateStageDestination(application(phase, { [permission]: false }))).toBeNull();
});
it("keeps screening and completed forms without an action", () => {
  expect(candidateStageDestination(application("SELECTION", {}))).toBeNull();
  expect(candidateStageDestination(application("FORM", { process_form: true }, "COMPLETED"))).toBeNull();
});
it("opens only this application's form and displays server failures", async () => {
  const fetch = vi.fn(async (_url: string) => new Response(JSON.stringify({ message: "Aguarde a liberação pelo RH." }), { status: 409 }));
  vi.stubGlobal("fetch", fetch);
  render(<MemoryRouter><CandidateStageAction application={application("FORM", { process_form: true })} /></MemoryRouter>);
  fireEvent.click(screen.getByRole("button", { name: "Responder perguntas do RH" }));
  expect(await screen.findByText(/Aguarde a liberação pelo RH/)).toBeVisible();
  expect(fetch.mock.calls[0][0]).toBe("/api/v1/applications/own-application/my-process-form");
});

it("opens the external registration after questions are submitted", () => {
  expect(candidateStageDestination(application("FORM", { process_form: true, selection_registration: true }, "COMPLETED"))?.path).toBe("/candidato/perfil#ficha-externa");
});
