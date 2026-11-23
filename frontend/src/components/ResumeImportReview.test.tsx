import {afterEach, expect, it, vi} from "vitest";
import {cleanup, fireEvent, render, screen, waitFor} from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import {ResumeImportReview} from "./ResumeImportReview";

vi.mock("../pages/Resources", () => ({RecordDetail: ({value}: {value: unknown}) => <pre>{JSON.stringify(value)}</pre>}));
afterEach(() => {cleanup();vi.unstubAllGlobals();});

it("does not persist until the candidate explicitly reviews and confirms", async () => {
  const fetcher = vi.fn(async () => new Response(JSON.stringify({candidate: {id: "person", version: 2}, personal: {data: {}, version: 1}})));
  vi.stubGlobal("fetch", fetcher);
  const saved = vi.fn();
  render(<ResumeImportReview ready getSnapshot={() => ({candidate: {name: "Nome revisado", profile: {skills: ["Excel"]}, version: 1}, personal: {}, personal_version: 0})} onSaved={saved} />);
  expect(fetcher).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole("button", {name: "Revisar e salvar dados importados"}));
  const confirm = screen.getByRole("button", {name: "Confirmar e salvar perfil"});
  expect(confirm).toBeDisabled();
  expect(fetcher).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole("checkbox"));
  fireEvent.click(confirm);
  await waitFor(() => expect(saved).toHaveBeenCalledOnce());
  const [url, request] = fetcher.mock.calls[0] as unknown as [string, RequestInit];
  expect(url).toContain("confirm-resume-import");
  expect(JSON.parse(String(request.body))).toMatchObject({confirmed: true, candidate: {name: "Nome revisado"}});
});
