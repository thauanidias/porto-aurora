import { afterEach, expect, it, vi } from "vitest";
import { api, post } from "./api";
import { enrollSelectedVacancy } from "./enrollSelectedVacancy";

vi.mock("./api", () => ({ api: vi.fn(), post: vi.fn() }));
afterEach(() => vi.resetAllMocks());

it("enrolls in the selected job with the validated resume", async () => {
  vi.mocked(api).mockResolvedValueOnce({ id: "selected" }).mockResolvedValueOnce({ items: [] }).mockResolvedValueOnce({ ready: true, missing: [], cv_id: "cv" });
  vi.mocked(post).mockResolvedValue({ id: "application" });
  expect(await enrollSelectedVacancy("/carreiras/vagas/analista?candidatar=1&utm_source=portal")).toEqual({ id: "application" });
  expect(api).toHaveBeenNthCalledWith(1, "/public/vacancies/analista");
  expect(post).toHaveBeenCalledWith("/applications", { vacancy_id: "selected", enrollment: true, cv_id: "cv", utm: { utm_source: "portal" } });
});

it("reports missing profile fields without submitting an application", async () => {
  vi.mocked(api).mockResolvedValueOnce({ id: "selected" }).mockResolvedValueOnce({ items: [] }).mockResolvedValueOnce({ ready: false, missing: ["Telefone"], cv_id: null });
  await expect(enrollSelectedVacancy("/carreiras/vagas/analista")).rejects.toThrow("Telefone");
  expect(post).not.toHaveBeenCalled();
});

it("opens the existing application without creating a duplicate", async () => {
  vi.mocked(api).mockResolvedValueOnce({ id: "selected" }).mockResolvedValueOnce({ items: [{ id: "existing" }] });
  expect(await enrollSelectedVacancy("/carreiras/vagas/analista")).toEqual({ id: "existing" });
  expect(post).not.toHaveBeenCalled();
});

it("rejects a return address that is not a portal vacancy", async () => {
  await expect(enrollSelectedVacancy("//example.com/job")).rejects.toThrow();
  expect(api).not.toHaveBeenCalled();
});
