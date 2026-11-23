import { expect, it } from "vitest";
import { availableCandidateActions } from "./candidateActions";
import type { Collection } from "./api";

const list = (items: Record<string, unknown>[]) => ({ items: items.map(item => ({ id: "row", version: 1, ...item })), total: items.length } as Collection);
const now = Date.parse("2026-10-01T12:00:00Z");
const test = { id: "test", opens_at: "2026-09-30T12:00Z", due_at: "2026-10-02T12:00Z", snapshot: { attempts_allowed: 1 }, attempts: [] };

it("shows only currently executable releases and upcoming commitments", () => {
  const result = availableCandidateActions(list([test, { ...test, id: "future", opens_at: "2026-10-02T12:00Z" }]), list([{ id: "interview", starts_at: "2026-10-02T12:00Z" }]), { id: "admission", version: 1, can_upload: true, items: [{ id: "doc", document: null }] }, list([{ id: "offer", status: "SENT", expires_at: "2026-10-02T12:00Z" }]), now);
  expect(result.map(item => [item.path, item.count])).toEqual([["testes", 1], ["entrevistas", 1], ["documentos", 1], ["ofertas", 1]]);
});

it("removes finished, expired, locked and past actions", () => {
  expect(availableCandidateActions(list([{ ...test, attempts: [{ id: "attempt", status: "SUBMITTED" }] }, { ...test, id: "expired", due_at: "2026-09-30T12:00Z" }]), list([{ id: "past", starts_at: "2026-09-30T12:00Z" }]), { id: "admission", version: 1, can_upload: false, items: [{ id: "doc", document: null }] }, list([{ id: "offer", status: "ACCEPTED", expires_at: "2026-10-02T12:00Z" }]), now)).toEqual([]);
  expect(availableCandidateActions(list([]), list([]), { id: "admission", version: 1, can_upload: true, items: [{ id: "doc", document: { id: "file" } }] }, list([]), now)).toEqual([]);
});

it("conta os links externos liberados e ignora os que aguardam etapa", () => {
  const links = [{ id: "link", version: 1, kind: "TEST", stage_unlocked: true }, { id: "interview", version: 1, kind: "INTERVIEW", stage_unlocked: true }, { id: "blocked", version: 1, kind: "TEST", stage_unlocked: false }];
  const result = availableCandidateActions(list([]), list([]), { id: "admission", version: 1 }, list([]), now, links);
  expect(result.map(item => [item.path, item.count])).toEqual([["testes", 1], ["entrevistas", 1]]);
});

it("hides counters for completed external tests and interviews", () => {
  const links = [
    { id: "test-done", version: 1, kind: "TEST", stage_unlocked: true, completed_at: "2026-10-01T11:00:00Z" },
    { id: "interview-done", version: 1, kind: "INTERVIEW", stage_unlocked: true, completed: true },
    { id: "test-pending", version: 1, kind: "TEST", stage_unlocked: true },
  ];
  const result = availableCandidateActions(list([]), list([]), { id: "admission", version: 1 }, list([]), now, links);
  expect(result.map(item => [item.path, item.count])).toEqual([["testes", 1]]);
});
