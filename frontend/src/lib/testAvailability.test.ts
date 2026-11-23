import { describe, expect, it } from "vitest";
import { testAvailability } from "./testAvailability";
const base = {id: "test", version: 1, opens_at: "2026-09-01T12:00Z", due_at: "2026-09-30T12:00Z", snapshot: {attempts_allowed: 1}, attempts: []};
describe("Botão de realização do teste", () => {
  it("respeita abertura, encerramento e limite de tentativas", () => {
    expect(testAvailability(base, Date.parse("2026-08-01"))).toContain("abertura");
    expect(testAvailability(base, Date.parse("2026-10-01"))).toContain("encerrado");
    expect(testAvailability({...base, attempts: [{status: "SUBMITTED"}]}, Date.parse("2026-09-15"))).toContain("concluídas");
    expect(testAvailability({...base, attempts: [{status: "STARTED"}]}, Date.parse("2026-09-15"))).toBe("");
    expect(testAvailability(base, Date.parse("2026-09-15"))).toBe("");
  });
});
